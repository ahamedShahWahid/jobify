# CLAUDE.md — api (`jobify_api` FastAPI service)

Load-bearing invariants for the HTTP layer (`api/src/jobify_api`): app factory, middleware, auth, routes (resumes, feed, jobs, applications, recruiter, admin, DSR, employer/invite). Auto-loaded when working under `api/`. Repo overview + universal conventions are in the root `CLAUDE.md`; domain/db invariants in `core/CLAUDE.md`.

> Each section names its paired design doc in `docs/superpowers/specs/` (the **why** + full reserved-slug tables). Below = rules that cause a bug if violated and aren't obvious from the code.

## App wiring (`jobify_api.app_factory`)

`create_app()` builds a fresh app per call (test isolation), owning three `app.state` things: `settings`; `db_engine` + `db_sessionmaker` (single async engine, sets `search_path=jobify` via asyncpg `server_settings` so model code does **not** repeat `schema="jobify"`; disposed on `shutdown` — **don't create your own engine in module scope**); `storage` (a `Storage` protocol impl, currently `LocalFileStorage`). Routes read these via `Depends` (`get_session` in `jobify_api.dependencies`, `get_storage`); tests swap via `app.dependency_overrides`.

## Middleware — pure ASGI, not BaseHTTPMiddleware

`RequestIdMiddleware` is pure ASGI on purpose: `BaseHTTPMiddleware` wraps the app in an `anyio` task group → asyncpg raises `Future attached to a different loop`. **New middleware must be pure-ASGI.** Request id = uuid4; client `X-Request-Id` honored only if a valid uuid4, else replaced; on every response (incl. errors) as the only log correlation handle. `CORSMiddleware` mounted **after** `RequestIdMiddleware` (outermost). Origins from `JOBIFY_CORS_ALLOW_ORIGINS` (default `http://localhost:8080`); no cookies → `allow_credentials` off. Only web needs it (mobile sends no `Origin`).

## Error handling — RFC 7807 problem+json

`jobify_api.middleware.error_handler`: `HTTPException` + unhandled `Exception` flow through `_problem()` → `application/problem+json` with `request_id`. The unhandled path re-attaches `X-Request-Id` (`ServerErrorMiddleware` sits outside `RequestIdMiddleware`). `HTTPException.detail` is user-visible — a user-facing string, not a debug aid.

## Don't reuse models as response schemas

SQLAlchemy models are never response models. Define `*Read`/`*Create`/`*Update` Pydantic v2 in the route module (`ResumeRead` with `ConfigDict(from_attributes=True)`).

## Auth + JWT invariants

- `current_user` **re-fetches the user row every call** — a user soft-deleted 30s ago is locked out within the access TTL (≤10 min), not the refresh TTL. Don't cache.
- **Sign-in always provisions `role=APPLICANT`.** Tests needing recruiter/admin create the row via `session` + `mint_access_token` (no "sign in as recruiter"; canonical `tests/integration/test_resumes_auth.py`).
- 401 slugs deliberately generic — `invalid_access_token` never differentiates signature vs claim (timing-oracle countermeasure). Don't add specific slugs.
- **Refresh rotates every use;** re-presenting a rotated token → full family revocation via `_revoke_family`. The bulk UPDATE relies on Postgres READ COMMITTED + EvalPlanQual — don't switch to a row-at-a-time loop.
- JWT: ≥32-byte secret, HS256, issuer `jobify-api`, `jti` required. 30s `iat` skew checked manually (PyJWT leeway would relax `exp` too).

## Resume route invariants — error ladder

`jobify_api.routes.resumes` enforces this order; each layer assumes the previous passed — **don't reorder:**

1. **401** Bearer parse + JWT + user re-fetch (`current_user`). Slugs `missing_bearer_token`/`invalid_access_token`/`user_not_found`.
2. **403** `not_an_applicant` — `require_applicant` (`jobify_api.auth.dependencies`, the ONE shared applicant guard — seven inline copies drifted and two lost the `deleted_at` filter, letting DSR-tombstoned applicants through; don't re-inline it) rejects recruiter/admin **before any applicant-row read**.
3. **500** `applicant_missing` — defense in depth (unreachable; `_upsert_identity` provisions the row at sign-in). Logs `applicant.row-missing-for-applicant-role`.
4. **415** content-type whitelist (`JOBIFY_ALLOWED_RESUME_CONTENT_TYPES`). **413** size cap (`JOBIFY_MAX_UPLOAD_BYTES`, 10 MiB).
5. **404** `resume not found` (GET) — **uniform** across unknown-id AND owned-by-another (single JOIN). Distinguishing leaks existence. Keep uniform.

Applicant id is **never** from the URL — from `current_user.id`. Prefix `/v1/applicants/me` (`me` literal). Storage key set **after** DB flush (`resumes/{resume.id}{ext}`); ext from `_CONTENT_TYPE_TO_EXT` off the validated content-type — never the filename. Parse dispatch is fire-and-forget post-commit (see `worker/CLAUDE.md` → Parse worker).

## Applicant profile + preferences — spec `2026-07-01-resume-review-preferences-design.md`

- **The `applicant_preferences` row is eagerly created at signup** (`AuthService._upsert_identity`, like consent seeding). GET/PATCH `/v1/applicants/me/preferences` treat a missing live row as an invariant violation — `_require_preferences_row` logs + raises 500 `applicant_preferences_missing`. Never auto-create on read.
- **Two disjoint rescore-trigger sets:** `_MATCHING_FIELDS = {years_experience}` (profile PATCH) vs `_PREFERENCES_MATCHING_FIELDS = {locations, expected_ctc}` (preferences PATCH). **`desired_role` is deliberately NOT a trigger** — capture-only; scoring never reads it (see `core/CLAUDE.md`). Don't "fix" that.
- **Partial-update contract** (both PATCHes): only `model_fields_set` keys are applied; explicit null clears `desired_role`/`expected_ctc`; `locations` is non-nullable (empty list clears). The setattr-from-fields-set loop is safe ONLY because `extra="forbid"` closes the field set — removing it opens mass assignment.
- `applicant_preferences` is PII → DSR-wired: exported (ALL rows, list — export convention has no `deleted_at` filter) + hard-deleted in `deleter.py`; pinned in `test_dsr_coverage.py` + `test_builder_signature.py`.

## Feed + job detail — spec `2026-05-20-p2.3-feed-and-job-detail-design.md`

- **`/v1/feed`** filters `surfaced_at IS NOT NULL` AND `jobs.status='open'` AND both sides `deleted_at IS NULL`; uses `ix_matches_applicant_surfaced (applicant_id, total_score DESC) WHERE ...` for seek + order.
- **Cursor = opaque base64 `{score, match_id}`** (no server state); compare `(total_score, id) < (cursor...)`; malformed → `400 invalid_cursor`. **Peek-one+1:** `LIMIT limit+1`, trim, set `next_cursor` if the extra was present. **Weak ETag** `W/"<sha256(applicant_id + max(updated_at) + count)>"`.
- **`/v1/jobs/{id}` returns the match unconditionally** when a row exists (ignores `surfaced_at`) — a pasted URL shows the score. **Uniform 404** across unknown/closed/soft-deleted. All applicant routes use the shared `require_applicant` guard (see Resume route invariants).
- **Shared route plumbing:** response shapes (`JobRead`, `EmployerRead`, `JobDetail*`) live in `jobify_api.routes.schemas` (a leaf module — hosting them in `feed.py` forced a mid-file import split to dodge the cycle); cursor base64+JSON encode/decode + `make_weak_etag` live in `jobify_api.pagination` with typed per-module wrappers. New list routes reuse both.

## Applications + saved jobs — spec `2026-05-20-p3.0-applications-and-saved-jobs-design.md`

- **Re-apply after withdraw UPDATEs the same row** to `status='applied'` (partial-UNIQUE on `(applicant_id, job_id) WHERE deleted_at IS NULL`). Withdrawal changes status, not soft-delete; refreshes `created_at`, keeps row id (cursor `{created_at, application_id}` stays valid).
- **PATCH only `applied → withdrawn`** (`{"status":"withdrawn"}`); else `400 invalid_transition`. Re-withdraw = **200 no-op**. Uniform 404 across unknown/other-user.
- **Save: `POST` idempotent create, `DELETE` idempotent soft-delete (204 always).** Re-save after unsave = fresh row; re-save of a live row returns it (200).
- **Saved-list keeps closed jobs** (no `status='open'` filter) so the applicant sees the role closed. Apply + save at *creation* enforce `status='open'` (404 for closed/deleted).

## Recruiter routes — spec `2026-05-28-recruiter-jobs-crud-design.md`

- **`POST /v1/employers` is the ONLY role-elevation path** — employer + `employer_users(role='owner')` + bounded `UPDATE users.role` APPLICANT→RECRUITER (WHERE includes `role=APPLICANT`, never demotes ADMIN, no-op for RECRUITER). One-way.
- **Employer name dedup** via partial-UNIQUE `ix_employers_name_norm_live` → 409 `employer_name_taken`. **Unique-violation walks `__cause__`:** raw `asyncpg.UniqueViolationError` at `e.orig.__cause__`; route does `cause = getattr(orig, "__cause__", None) or orig` then `type(cause).__name__ == "UniqueViolationError"` (avoids importing asyncpg). `await session.rollback()` on both branches.
- **`_load_recruiter_job(job_id, user, session)` is canonical** for PATCH/DELETE/applicants — `_require_recruiter` first (403 before id lookup), joins `EmployerUser` for ownership, filters soft-deleted, uniform 404. **Reuse, don't re-implement.** `DELETE` returns 404 on the second call (not 204).
- **`PATCH` re-embeds ONLY when a content field changes** — `_EMBED_TRIGGERING_FIELDS = {title, description, locations, min_exp_years, max_exp_years, ctc_min, ctc_max}`. Status-only PATCH does NOT dispatch `embed_job`. Status via Pydantic `Literal["open","closed"]` → 422 on unknown. `embed_job` import is **deferred inside the route fn** (module-level triggers `Settings()` at collection); dispatch in broad-except `embed.dispatch-failed`.
- **`/v1/jobs/me` MUST be declared BEFORE `/v1/jobs/{job_id}`** (FastAPI matches in order; NOTE comment — don't reorder). Counts via `func.count(distinct(case(...)))` to emulate `COUNT(... FILTER)` in one GROUP BY: `applicant_count` = `status='applied' AND deleted_at IS NULL`; `surfaced_match_count` = `surfaced_at IS NOT NULL AND deleted_at IS NULL`. `?status` is `Literal["open","closed"]` — fail closed; an untyped param silently bypassed the open-only default for any junk value. Cursor query served by `ix_jobs_employer_posted_at_live (employer_id, posted_at DESC, id DESC)` (0019; replaced the redundant-prefix `ix_jobs_employer_id_live`).
- **`GET /v1/jobs/{id}/applicants` is PII-audited** (`job.applicants_listed` audit row + `recruiter.applicants-listed` structlog) — it exposes names + emails, same disclosure class as the resume download. Any new recruiter endpoint exposing applicant PII must audit.
- **Recruiter resume download:** `Content-Disposition` built via `_content_disposition_attachment()` (RFC 6266 — the filename is applicant-controlled; raw interpolation let quotes/CRLF break the header). Blob read happens AFTER the audit commit (connection released during storage I/O).
- **`JobRead.employer_verified` is required** — build every `JobRead` via `JobRead.from_job_and_employer(job, employer)` (only legit constructor; callers with only `Job` must fetch the employer). Unverified employers' jobs still surface in `/v1/feed`.
- **`GET /v1/jobs/{id}/applicants`** uses `Applicant.full_name` for `display_name` (User has none); joins `Application → Applicant → User`. **`GET /v1/applications/{id}/resume`** = recruiter download: caller must be RECRUITER at the owning employer; single JOIN (`Application → Job → EmployerUser → Resume[outer]`), any leg fails → uniform 404; latest via `ORDER BY Resume.created_at DESC`. Emits `recruiter.resume-accessed` structlog + `audit_log()`.

## Admin moderation — spec `2026-05-29-admin-moderation-design.md`

- **`/v1/admin/*` gated by `_require_admin` after `current_user`** → 401 → `_require_admin` → 403 `not_an_admin` → DB. No admin-resource lookups before the role check.
- **Suspended users get 401 `user_suspended`** (not 403) — distinct slug for a suspension message; Flutter signs out cleanly on any non-`invalid_access_token` 401.
- **`suspended_at` AND `suspension_reason` clear together** on unsuspend (tooling reads `reason IS NOT NULL` as "suspended").
- `admin.user.suspended` writes a row **every call** (re-suspend reason = evidence); `unsuspended` is no-op-on-noop. Suspending self → 400 `cannot_suspend_self`.
- **`jobify-grant-admin <email>` bootstraps** (no grant route — chicken-and-egg). The audit-log viewer doesn't self-audit its query.
- **Employer verification review** (`GET /v1/admin/employers?status=`, `POST .../{id}/verify`, `POST .../{id}/reject {reason}`; migration 0020). The tri-state is **DERIVED, not stored** — `verified_at` set → verified; else `rejected_at` set → rejected; else pending. Verify/reject are mutually exclusive (each clears the other's timestamp + `rejection_reason`), so re-verifying a rejected employer just works; setting `verified_at` also flips the `employer_verified` trust badge in `/v1/feed`. `AdminEmployerRead.reviewed_at`/`reason` are derived (no review table — `audit_logs` `admin.employer.{verified,rejected}` is the history). Writes an audit row every call (re-review = evidence), like suspend.

## DSR export — spec `2026-05-29-dsr-export-design.md`

- **Sync HTTP, JSON envelope.** `POST /v1/me/dsr/export` → `application/json`, `Content-Disposition: attachment`, `Cache-Control: no-store`.
- **`refresh_tokens` are NEVER exported** (session secrets); a `redactions` entry documents it.
- **Defensive column denylist** in `jobify/dsr/__init__.py` (`_REDACTED_COLUMN_NAMES` + `_REDACTED_COLUMN_SUFFIXES`) strips `*_secret`/`password_hash`/`*_password`/`access_token`/etc from EVERY row. Zero such columns today — **adding a sensitive column to `db/models.py` → extend the denylist** (`test_row_to_dict_drops_redacted_columns` pins it).
- `audit_history` = `actor_user_id = self.id` only (v0). **Two audit rows:** `user.dsr_export_requested` (flushed BEFORE assembly) + `user.dsr_export_completed` (after, with `section_counts`). Recruiters/admins get different (mostly empty) envelopes.

## DSR delete — spec `2026-05-29-dsr-delete-design.md`

- **Soft-delete + scrub, NOT hard-delete the User row** — hard-delete CASCADE-wipes applications/matches (lose analytics + eval substrate). Tombstone `users` + `applicants` with PII scrubbed; hard-delete the truly-PII tables around them.
- **Migration 0015 made `applicants.full_name` + `applicants.locations` nullable** for scrubbing (`applicants.locations` has since been DROPPED by 0021 — locations now live on `applicant_preferences`, which DSR hard-deletes). New PII column on applicants/users/resumes → decide nullability + tombstone, update `delete_user_data` + a migration.
- **Application-layer deletion graph** (`jobify_api.dsr.deleter.delete_user_data`), not FK CASCADE — walks the graph for correct counts + order-sensitive blob-delete-before-scrub.
- **Atomic txn** (handler does explicit `await session.commit()` at success) — partial deletion is worse than none. Re-signup works (email-collision filters `deleted_at IS NULL`). Confirmation token in **body** not query: `DELETE /v1/me/dsr` `{"confirmation": "DELETE_MY_ACCOUNT"}`.
- Sole-owner employer → a `warnings` entry (employer stays). Blob deletion best-effort (`dsr.blob-delete-failed`, no rollback).
- **No HTTP idempotency** — later calls 401 `user_not_found` (tombstone soft-deleted); clients treat as "done". The 401-after-delete test uses `concurrent_async_client` (real pool forces a refetch past the identity map).

## Employer team management (R4) — spec `2026-06-06-recruiter-employer-experience-design.md` §5

- **Role is DERIVED from membership, never set directly.** `jobify/employers/membership.py`: `flip_to_recruiter` (any join → APPLICANT→RECRUITER, never ADMIN) + `maybe_demote_to_applicant` (zero live memberships left → RECRUITER→APPLICANT) are the only `users.role` writers in this flow. `current_user` re-fetches per request → a removed recruiter loses access within the access-TTL (no token revocation). **Any new join/leave path must call these.**
- **RBAC helpers (`jobify_api.auth.dependencies`):** `_require_employer_member` (uniform 404 if no live link — don't leak existence), `_require_employer_owner` (404 if not a member, then 403 `not_an_owner`). Owner mutates members/invites; any member reads. Called BEFORE any resource lookup.
- **Last-owner guard is lock-based:** `_count_live_owners(..., lock=True)` does `SELECT … FOR UPDATE` on owner rows (aggregates can't carry FOR UPDATE — lock rows, count in Python), used in the demote/remove guards — else two concurrent owner removals both pass `<=1` → zero owners. Membership inserts (`add_member`, `accept_invite`) catch the `ix_employer_users_pair_live` `IntegrityError → 409 already_a_member` (mirrors `create_employer`).
- **Invites:** `POST …/invites` outboxes a `Notification` (kind `employer_invite`) ONLY when the email maps to an existing user (`notifications.user_id` NOT NULL); brand-new invitees discover via `GET /v1/me/invites`; SES deferred. Invitee routes (`jobify_api.routes.invites`) authorize by `invite.email == current_user.email` (NOT membership); lazy expiry (`pending`→`expired` on read/accept, 410); accept verifies the employer is live; decline reuses the `revoked` status. Slugs: `employer.{member_added,member_role_changed,member_removed,invite_created,invite_accepted,invite_revoked}`.
- **`employer_invites.email` is PII** → DSR export adds `received_invites`/`sent_invites`, delete erases invites where `email==user.email OR accepted_user_id==user.id`. **Any new PII *table* must be added to `jobify/dsr/__init__.py` + `deleter.py` + the `test_user_export_top_level_fields` pin.** No self-leave endpoint yet (direct-add is one-way; removing yourself needs another owner).
