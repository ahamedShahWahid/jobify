# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this repo is

Jobify (Jobify) — an early-stage placement platform.

- **Backend — uv workspace (3 packages, all from repo root):**
  - `core/` — `jobify` domain package. DB models + Alembic migrations (`core/alembic.ini`), integrations (storage, parser, embeddings, email, scoring, explainer), consent/DSR/audit, seeding CLI, Celery bare app (`jobify.celery_app`). Email templates at `core/emails/`.
  - `api/` — `jobify_api` FastAPI service. App factory, routes, auth, middleware, DSR/admin routes, employer/invite routes. Entry point `jobify_api.main:app`. Scripts: `jobify-seed-jobs`, `jobify-seed-consents`, `jobify-grant-admin`.
  - `worker/` — `jobify_worker` Celery daemon. Tasks (parse, embed, score, sweep_notifications), runtime singletons, worker entry point `jobify_worker.worker_app`. See `worker/README.md`.
  - `tests/` — all tests at repo root (`tests/unit/`, `tests/integration/`, `tests/eval/`).
  - Root `pyproject.toml` is the workspace (`[tool.uv.workspace] members = [core, api, worker]`). `.env` lives at repo root.
- `IMPLEMENTATION_SPEC.md` — **how** we build it (engineering spec, v0.2 MVP-first).
- `docs/prd/KPA_Enhanced_BRD_v1_1.pdf` — **what** we build (product BRD; scope source of truth).
- `docs/superpowers/specs/` — per-slice design docs (the **why** behind each section below). Their spent step-by-step build plans were removed once shipped — recoverable from git history if ever needed.
- `app/` — Flutter mobile + web client (last section). The spec overrides the BRD's React Native + Next.js stack.
- `frontend/` — unified Vite + React + TS web app; three route-prefixed surfaces under one HashRouter: `/` (applicant/public, `src/sites/web`), `/employers` (recruiter marketing, `src/sites/employers`), `/console` (admin + recruiter ops, `src/sites/console`). Shared transport/session/auth/env in `src/shared`. `npm run build` = `tsc -b && vite build`. See `frontend/README.md`. Static `frontend/styleguide/` has no build step.

Scope vs "how" conflict: BRD wins on product behavior; spec wins on tech.

## Commands + setup

All backend commands run from the **repo root** (`pyproject.toml` + `uv.lock` live there). `.env` at repo root. **Operational reference in READMEs** — `api/README.md` (run, tests, migrations, DB/Redis/pgvector setup, seeding, full `JOBIFY_*` env-var table, endpoint docs), `worker/README.md` (worker run + beat command, queues), `app/README.md` (Flutter run/test, web OAuth origins), `frontend/README.md` (Vite dev/build, env vars, surface→route map). This file is non-obvious bits only. Boot rules:

- App refuses to boot if a required `JOBIFY_*` var is missing/invalid (`settings.py` in `jobify_api`); `JOBIFY_DB_URL` **must** use `postgresql+asyncpg://` (enforced in `Settings._enforce_async_driver`).
- Integration fixtures inject `JOBIFY_JWT_SECRET="x"*32` + `JOBIFY_GOOGLE_OAUTH_CLIENT_IDS=test.apps.googleusercontent.com` — match these for new apps under test.
- **Alembic runs from `core/`:** `cd core && uv run alembic upgrade head` (alembic.ini lives in `core/`).
- **Worker runs from repo root:** `uv run --env-file=.env celery -A jobify_worker.worker_app worker --pool=solo --concurrency=1 -Q parse,embed,score,notify --loglevel=info`. Dispatch by task name via `jobify.celery_app.enqueue("jobify.<task>", …)`.
- **CI verbatim** (run these exact commands from repo root before claiming green) — backend: `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -s -m eval` · `uv run pytest -v -m integration`; app: `dart format --set-exit-if-changed lib test` · `flutter analyze` · `flutter test`.

## Architecture — non-obvious bits

> Each subproject has a paired design doc in `docs/superpowers/specs/` (the **why** + full reserved-slug tables). Below = load-bearing rules only: things that cause a bug if violated and aren't obvious from the code.

### App wiring (`jobify_api.app_factory`)

`create_app()` builds a fresh app per call (test isolation), owning three `app.state` things: `settings`; `db_engine` + `db_sessionmaker` (single async engine, sets `search_path=jobify` via asyncpg `server_settings` so model code does **not** repeat `schema="jobify"`; disposed on `shutdown` — **don't create your own engine in module scope**); `storage` (a `Storage` protocol impl, currently `LocalFileStorage`). Routes read these via `Depends` (`get_session` in `jobify_api.dependencies`, `get_storage`); tests swap via `app.dependency_overrides`.

### Middleware — pure ASGI, not BaseHTTPMiddleware

`RequestIdMiddleware` is pure ASGI on purpose: `BaseHTTPMiddleware` wraps the app in an `anyio` task group → asyncpg raises `Future attached to a different loop`. **New middleware must be pure-ASGI.** Request id = uuid4; client `X-Request-Id` honored only if a valid uuid4, else replaced; on every response (incl. errors) as the only log correlation handle. `CORSMiddleware` mounted **after** `RequestIdMiddleware` (outermost). Origins from `JOBIFY_CORS_ALLOW_ORIGINS` (default `http://localhost:8080`); no cookies → `allow_credentials` off. Only web needs it (mobile sends no `Origin`).

### Error handling — RFC 7807 problem+json

`jobify_api.middleware.error_handler`: `HTTPException` + unhandled `Exception` flow through `_problem()` → `application/problem+json` with `request_id`. The unhandled path re-attaches `X-Request-Id` (`ServerErrorMiddleware` sits outside `RequestIdMiddleware`). `HTTPException.detail` is user-visible — a user-facing string, not a debug aid.

### Resume route invariants — error ladder

`jobify_api.routes.resumes` enforces this order; each layer assumes the previous passed — **don't reorder:**

1. **401** Bearer parse + JWT + user re-fetch (`current_user`). Slugs `missing_bearer_token`/`invalid_access_token`/`user_not_found`.
2. **403** `not_an_applicant` — `require_applicant` (`jobify_api.auth.dependencies`, the ONE shared applicant guard — seven inline copies drifted and two lost the `deleted_at` filter, letting DSR-tombstoned applicants through; don't re-inline it) rejects recruiter/admin **before any applicant-row read**.
3. **500** `applicant_missing` — defense in depth (unreachable; `_upsert_identity` provisions the row at sign-in). Logs `applicant.row-missing-for-applicant-role`.
4. **415** content-type whitelist (`JOBIFY_ALLOWED_RESUME_CONTENT_TYPES`). **413** size cap (`JOBIFY_MAX_UPLOAD_BYTES`, 10 MiB).
5. **404** `resume not found` (GET) — **uniform** across unknown-id AND owned-by-another (single JOIN). Distinguishing leaks existence. Keep uniform.

Applicant id is **never** from the URL — from `current_user.id`. Prefix `/v1/applicants/me` (`me` literal). Storage key set **after** DB flush (`resumes/{resume.id}{ext}`); ext from `_CONTENT_TYPE_TO_EXT` off the validated content-type — never the filename. Parse dispatch is fire-and-forget post-commit (see Parse worker).

### Soft delete model

Every domain table: `id` (uuid4), `created_at`, `updated_at`, `deleted_at TIMESTAMPTZ NULL`. Live queries filter `deleted_at IS NULL`; uniqueness via partial indexes `WHERE deleted_at IS NULL` (e.g. `User.ix_users_email_live`). New tables reuse the `CreatedAt`/`UpdatedAt`/`DeletedAt` `Annotated` types in `db/models.py`. `Base.__table_args__` is typed `Any` + `# noqa: RUF012` — don't "fix" the noqa.

### Audit logs (`audit_log()`) — spec `2026-05-28-audit-logs-substrate-design.md`

- **Append-only, caller-owns-txn:** flushes one row in the caller's txn (no commit, no fire-and-forget; rolls back with the business action). The **documented exception** to soft-delete: `AuditLog` skips the `Created/Updated/DeletedAt` types and never filters `deleted_at IS NULL`. No UPDATE/DELETE.
- `actor_user_id` is `ON DELETE SET NULL` (so a DSR hard-delete leaves the audit row, re-identification impossible). `actor_role` is a plain-TEXT **snapshot** (`'system'` valid for cron/worker, `actor=None`). `audit_log(actor=None, actor_role=None)` raises `ValueError`.
- Slugs dotted-lowercase-verb-past; reserved prefixes `resume.*` `application.*` `job.*` `consent.*` `user.*` `admin.*` `auth.*` `employer.*` (table in spec §4).
- **structlog FIRST, `audit_log()` SECOND, then side-effect** (canonical `jobify_api.routes.applications:recruiter_download_application_resume`). structlog → Fluent Bit → Elasticsearch is the live channel; the DB row is durable — complementary.

### Consent + channel prefs — spec `2026-05-29-consent-channel-prefs-design.md`

- **`user_consents` = state; `audit_logs` = history.** `set_consent(...)` is the ONLY path writing a `consent.*` audit row (same txn); no-op flips write none. Don't hand-write consent audit rows.
- **`ON DELETE CASCADE` on `user_id`** (opposite of audit_logs) — consent vanishes with the user; history survives via `actor_user_id SET NULL`.
- **Eager seeding at signup** — `_upsert_identity` calls `seed_default_consents(...)`; later reads are plain SELECTs. Default changes affect only NEW signups. `email_transactional` defaults `true` — signup UI MUST notify the user.
- **Sweep gate:** `sweep_notifications._dispatch_one` checks consent between user-load and dispatch. No consent → `status=CANCELLED`, terminal (re-grant doesn't resurrect). `get_consent` raising `LookupError` (seeding skipped — pre-P4-B / DSR-cascaded) → falls back to `DEFAULT_CONSENTS[scope]`; backfill `jobify-seed-consents`. Inbox excludes `CANCELLED` + `FAILED`.
- Scopes are `StrEnum` at the boundary, TEXT in DB; reserved scopes ship default `false` so impls skip an enum migration.
- **Adding a Postgres enum value** can't share a txn with other DDL. Try `op.get_context().autocommit_block()` first; our async setup trips on `_in_external_transaction` — Alembic 0014's `bind.commit()` + `run_async(...)` is a **documented exception, DO NOT copy unprompted** (document the error first).

### DSR export — spec `2026-05-29-dsr-export-design.md`

- **Sync HTTP, JSON envelope.** `POST /v1/me/dsr/export` → `application/json`, `Content-Disposition: attachment`, `Cache-Control: no-store`.
- **`refresh_tokens` are NEVER exported** (session secrets); a `redactions` entry documents it.
- **Defensive column denylist** in `jobify/dsr/__init__.py` (`_REDACTED_COLUMN_NAMES` + `_REDACTED_COLUMN_SUFFIXES`) strips `*_secret`/`password_hash`/`*_password`/`access_token`/etc from EVERY row. Zero such columns today — **adding a sensitive column to `db/models.py` → extend the denylist** (`test_row_to_dict_drops_redacted_columns` pins it).
- `audit_history` = `actor_user_id = self.id` only (v0). **Two audit rows:** `user.dsr_export_requested` (flushed BEFORE assembly) + `user.dsr_export_completed` (after, with `section_counts`). Recruiters/admins get different (mostly empty) envelopes.

### DSR delete — spec `2026-05-29-dsr-delete-design.md`

- **Soft-delete + scrub, NOT hard-delete the User row** — hard-delete CASCADE-wipes applications/matches (lose analytics + eval substrate). Tombstone `users` + `applicants` with PII scrubbed; hard-delete the truly-PII tables around them.
- **Migration 0015 made `applicants.full_name` + `applicants.locations` nullable** for scrubbing. New PII column on applicants/users/resumes → decide nullability + tombstone, update `delete_user_data` + a migration.
- **Application-layer deletion graph** (`jobify.dsr.deleter.delete_user_data`), not FK CASCADE — walks the graph for correct counts + order-sensitive blob-delete-before-scrub.
- **Atomic txn** (handler does explicit `await session.commit()` at success) — partial deletion is worse than none. Re-signup works (email-collision filters `deleted_at IS NULL`). Confirmation token in **body** not query: `DELETE /v1/me/dsr` `{"confirmation": "DELETE_MY_ACCOUNT"}`.
- Sole-owner employer → a `warnings` entry (employer stays). Blob deletion best-effort (`dsr.blob-delete-failed`, no rollback).
- **No HTTP idempotency** — later calls 401 `user_not_found` (tombstone soft-deleted); clients treat as "done". The 401-after-delete test uses `concurrent_async_client` (real pool forces a refetch past the identity map).

### Don't reuse models as response schemas

SQLAlchemy models are never response models. Define `*Read`/`*Create`/`*Update` Pydantic v2 in the route module (`ResumeRead` with `ConfigDict(from_attributes=True)`).

### Auth + JWT invariants

- `current_user` **re-fetches the user row every call** — a user soft-deleted 30s ago is locked out within the access TTL (≤10 min), not the refresh TTL. Don't cache.
- **Sign-in always provisions `role=APPLICANT`.** Tests needing recruiter/admin create the row via `session` + `mint_access_token` (no "sign in as recruiter"; canonical `tests/integration/test_resumes_auth.py`).
- 401 slugs deliberately generic — `invalid_access_token` never differentiates signature vs claim (timing-oracle countermeasure). Don't add specific slugs.
- **Refresh rotates every use;** re-presenting a rotated token → full family revocation via `_revoke_family`. The bulk UPDATE relies on Postgres READ COMMITTED + EvalPlanQual — don't switch to a row-at-a-time loop.
- JWT: ≥32-byte secret, HS256, issuer `jobify-api`, `jti` required. 30s `iat` skew checked manually (PyJWT leeway would relax `exp` too).

### Admin moderation — spec `2026-05-29-admin-moderation-design.md`

- **`/v1/admin/*` gated by `_require_admin` after `current_user`** → 401 → `_require_admin` → 403 `not_an_admin` → DB. No admin-resource lookups before the role check.
- **Suspended users get 401 `user_suspended`** (not 403) — distinct slug for a suspension message; Flutter signs out cleanly on any non-`invalid_access_token` 401.
- **`suspended_at` AND `suspension_reason` clear together** on unsuspend (tooling reads `reason IS NOT NULL` as "suspended").
- `admin.user.suspended` writes a row **every call** (re-suspend reason = evidence); `unsuspended` is no-op-on-noop. Suspending self → 400 `cannot_suspend_self`.
- **`jobify-grant-admin <email>` bootstraps** (no grant route — chicken-and-egg). The audit-log viewer doesn't self-audit its query.
- **Employer verification review** (`GET /v1/admin/employers?status=`, `POST .../{id}/verify`, `POST .../{id}/reject {reason}`; migration 0020). The tri-state is **DERIVED, not stored** — `verified_at` set → verified; else `rejected_at` set → rejected; else pending. Verify/reject are mutually exclusive (each clears the other's timestamp + `rejection_reason`), so re-verifying a rejected employer just works; setting `verified_at` also flips the `employer_verified` trust badge in `/v1/feed`. `AdminEmployerRead.reviewed_at`/`reason` are derived (no review table — `audit_logs` `admin.employer.{verified,rejected}` is the history). Writes an audit row every call (re-review = evidence), like suspend.

### Parse F1 quality gate

- **Gold dataset `core/data/parse_eval/`** (`<id>.txt` + `<id>.expected.json`); raw text (PDF/DOCX extraction bypassed — gate measures parser heuristics).
- **`uv run pytest -m eval`** → `test_library_parser_meets_quality_gate` → `jobify.eval.parse_f1.eval_gold_dataset()`. CI runs it (`lint-types-unit-eval`, no DB) before integration.
- **Gate** (spec §13 P1): macro-F1 ≥ 0.85; floors `email ≥ 0.95`/`phone ≥ 0.85`/`name ≥ 0.70`/`skills ≥ 0.75`. **Only those 4 fields gate** (others print only). Set-skills F1 counts FPs (measures `_extract_skills` over-match drift).
- New gold example: drop a pair with the next id, re-run `-m eval -v -s`; if it tanks a floor, fix the expectation or document the limitation.

### Parse worker (Celery) — spec `2026-05-18-resume-parse-worker-design.md`

- **Fire-and-forget after commit:** `parse_resume.delay()` wrapped in broad `except Exception` + `exc_info=True` (`dispatch.failed`). Broker outage MUST NOT fail an upload (row + blob durable). **Don't tighten the except.**
- **3-txn split** (`parse.py:_parse_resume_async`): Txn1 load + idempotency gate + mark `parsing`; (no DB) read blob + extract + parse; Txn3 reload, verify still `parsing`, write `parsed_json` + `parsed`. A lock across extraction starves writers — keep the split.
- **Retry:** `ParserError` → immediate `failed`; `TransientParserError` → autoretry ×3 exp backoff; unknown → wrapped. On exhaustion the row is marked `failed` BEFORE the raise (no wedge at `parsing`).
- **Eager mode + running loop:** with `JOBIFY_CELERY_TASK_ALWAYS_EAGER=true` inside an async request, `asyncio.run()` would explode — `parse.py` dispatches to a fresh thread. Tests rely on this.

### Embedding worker (Gemini) — spec `2026-05-19-embedding-worker-design.md`

- **One vector per applicant** (`applicant_embeddings.applicant_id UNIQUE`) — the *latest* parsed resume's canonical profile; older resumes unreachable from matching.
- **Idempotency via `canonicalized_text_hash`** — Txn1 computes text + sha256, bails on match (no provider call). **3-txn split** like parse: Txn1 gate; Txn2 (no DB) Gemini; Txn3 re-verify hash, UPSERT via `pg_insert(...).on_conflict_do_update(...)`. Dispatched from `parse_resume` Txn3, fire-and-forget (don't tighten).
- **Provider task via prompt prefix:** `gemini-embedding-2` does NOT accept `task_type` (that was `-001`). `encode()` formats internally; call sites pass `EmbeddingTask.DOCUMENT`/`.QUERY` + optional `title`.
- **Lazy provider resolution:** `embed.py` resolves via `get_embedding_provider()` (lazy-singleton in `celery_app.py`), never importing `GeminiEmbeddingProvider`. The `jobify.integrations.embeddings` `__init__` omits the provider from re-exports so `google.genai` isn't pulled in by test imports; impl users import from `...embeddings.gemini`.
- **`from module import name` test-patch gotcha:** modules holding a local `get_embedding_provider` reference aren't intercepted by patching `celery_app.get_embedding_provider` alone. `patched_embedding_provider` patches **three** modules (`celery_app`, `embed_job`, `embed`) + seeds the `_embedding_provider` cache. Mirror for any function imported-by-name across modules.
- **Pgvector + HNSW + cosine** (Migration 0004, `vector_cosine_ops`). Dim from `JOBIFY_EMBEDDING_DIM` (1536) — must match `Vector(N)` in the migration (mismatch errors on first insert). No `embed_status` column: it exists or doesn't; next parse re-dispatches.

### Seeding — spec `2026-05-20-p2.0-jobs-and-seeding-design.md`

- **`employers`/`jobs` via CLI** (`uv run jobify-seed-jobs` reads `core/data/sample_jobs.json`, upserts), not migrations. Idempotency: `employers.name_norm` (DB partial-UNIQUE) + `(jobs.employer_id, lower(jobs.title))` (script-only). JSON uses `posted_days_ago: int` (→ `now() - timedelta`) so it doesn't age.
- **Updates preserve human state:** `employers.name` never overwritten; `verified_at` set only when `NULL`.
- **`_apply_in_session(session, payload, report)` is the test seam** (CLI's `_apply()` opens its own engine; tests pass the savepoint session). `embed_job` dispatch (`_dispatch_embeds(...)`) runs AFTER `_apply` returns (outside `asyncio.run`); same broad-except.
- **Drift guard** `test_loader_against_sample_jobs_json` asserts `employers==10, jobs==27` — update in the same commit.

### Scoring worker — spec `2026-05-20-p2.2-matches-and-scoring-design.md`

- **`matches` = applicant × job embedding join.** One row per `(applicant_id, job_id)` live pair, UPSERT on rescore via partial-UNIQUE `WHERE deleted_at IS NULL`.
- **Two workers, one `score` queue:** `score_applicant` (from `embed_applicant` Txn3) + `score_job` (from `embed_job` Txn3), post-commit, broad-except. Pure-Python cosine (`jobify.scoring.vector`). Explanations run via bounded `asyncio.gather` (`_EXPLAIN_CONCURRENCY=10`), not per-item awaits.
- **Workers import `settings` from `celery_app`, never construct `Settings()`** — a second module-level instance is invisible to test `monkeypatch.setenv`. The worker engine's `NullPool` is load-bearing (fresh `asyncio.run()` loop per task; pooled asyncpg connections bind to dead loops).
- **`surfaced_at` preserved on rescore** via `func.coalesce(Match.surfaced_at, case((literal(crosses_threshold), now()), else_=None))` — a later sub-threshold rescore does NOT unset it (feed monotonic).
- **`score_components` + `model_versions` JSONB** = eval substrate (replay weight/threshold A/B without rescoring). **Two-txn split** (no external call): Txn1 loads all (incl. `Employer.name`), Python computes, Txn2 UPSERTs in one commit. `TransientScoringError` wraps UPSERT failures for autoretry. Threshold `0.55` (`JOBIFY_MATCH_SURFACE_THRESHOLD`) + vector weight `0.6` (`JOBIFY_MATCH_VECTOR_WEIGHT`) env-driven; per-rule weights equal.

### Feed + job detail — spec `2026-05-20-p2.3-feed-and-job-detail-design.md`

- **`/v1/feed`** filters `surfaced_at IS NOT NULL` AND `jobs.status='open'` AND both sides `deleted_at IS NULL`; uses `ix_matches_applicant_surfaced (applicant_id, total_score DESC) WHERE ...` for seek + order.
- **Cursor = opaque base64 `{score, match_id}`** (no server state); compare `(total_score, id) < (cursor...)`; malformed → `400 invalid_cursor`. **Peek-one+1:** `LIMIT limit+1`, trim, set `next_cursor` if the extra was present. **Weak ETag** `W/"<sha256(applicant_id + max(updated_at) + count)>"`.
- **`/v1/jobs/{id}` returns the match unconditionally** when a row exists (ignores `surfaced_at`) — a pasted URL shows the score. **Uniform 404** across unknown/closed/soft-deleted. All applicant routes use the shared `require_applicant` guard (see Resume route invariants).
- **Shared route plumbing:** response shapes (`JobRead`, `EmployerRead`, `JobDetail*`) live in `jobify_api.routes.schemas` (a leaf module — hosting them in `feed.py` forced a mid-file import split to dodge the cycle); cursor base64+JSON encode/decode + `make_weak_etag` live in `jobify.pagination` with typed per-module wrappers. New list routes reuse both.

### Match explanations — specs `p2.4` + `2026-05-28-llm-match-explanations-design.md`

- **`matches.explanation` JSONB** `{fit, caveat, generator, generator_version}`, nullable. Generated inline in both score workers.
- **`MatchExplainer` Protocol** routes two impls; workers call `await get_match_explainer().explain(ctx)`, call site unchanged. **`explain()` NEVER raises** — scoring is never failed by the explainer.
- **`TemplatedExplainer`** (`explainer.py`, wraps pure `templated_explanation()`) deterministic. **`GeminiMatchExplainer`** (`llm_explainer.py`) surfaced-only (if `ctx.total < ctx.threshold` returns templated, no Gemini); any failure logs `explain.llm-failed` (with `raw_text`) + falls back to templated.
- **`thinking_budget=0` is load-bearing** in the explainer's `GenerateContentConfig` — gemini-2.5 thinks by default and thought tokens count against `max_output_tokens`; with the 200 cap, thinking starved the output and EVERY explain silently fell back to templated (the never-raise contract hides it). Watch `generator` in stored explanations, not just error logs.
- **Selection:** `JOBIFY_MATCH_EXPLAINER` = `"llm"` (default, Gemini) | `"templated"` (dev fallback, no `JOBIFY_GEMINI_API_KEY`). Model `JOBIFY_MATCH_EXPLAINER_MODEL` (`gemini-2.5-flash`). Factory `get_match_explainer()` lazy-singleton. **`explainer.py` does NOT import `google.genai`** (separate module; factory does `from google import genai` lazily). `patched_match_explainer` mirrors the embedding fixture (three modules + cache).
- **`GENERATOR_VERSION` bumps on semantic template/prompt change** — flag template/prompt edits.

### Notifications outbox — spec `2026-05-20-p3.1-notifications-outbox-design.md`

- **Outbox:** writers insert `notifications` on the event; `sweep_notifications` (beat) claims via `SELECT FOR UPDATE SKIP LOCKED`. Idempotency per `notifications.id`.
- **Email = `LoggingEmailChannel` stub** (logs `email.sent`, marks `sent`). Real SES: implement `EmailChannel` in `jobify/integrations/email/ses.py`, set `JOBIFY_EMAIL_CHANNEL=ses`.
- **Retry ×5**, backoff `min(60·2^(attempt-1), 3600) + jitter(0,30)` → `send_after`; exhaustion → `failed`.
- **Apply inserts TWO rows** (`email` + `in_app`); idempotent re-applies and re-apply-after-withdraw insert none. `GET /v1/notifications` excludes `failed` + `cancelled`.

### Applications + saved jobs — spec `2026-05-20-p3.0-applications-and-saved-jobs-design.md`

- **Re-apply after withdraw UPDATEs the same row** to `status='applied'` (partial-UNIQUE on `(applicant_id, job_id) WHERE deleted_at IS NULL`). Withdrawal changes status, not soft-delete; refreshes `created_at`, keeps row id (cursor `{created_at, application_id}` stays valid).
- **PATCH only `applied → withdrawn`** (`{"status":"withdrawn"}`); else `400 invalid_transition`. Re-withdraw = **200 no-op**. Uniform 404 across unknown/other-user.
- **Save: `POST` idempotent create, `DELETE` idempotent soft-delete (204 always).** Re-save after unsave = fresh row; re-save of a live row returns it (200).
- **Saved-list keeps closed jobs** (no `status='open'` filter) so the applicant sees the role closed. Apply + save at *creation* enforce `status='open'` (404 for closed/deleted).

### Recruiter routes — spec `2026-05-28-recruiter-jobs-crud-design.md`

- **`POST /v1/employers` is the ONLY role-elevation path** — employer + `employer_users(role='owner')` + bounded `UPDATE users.role` APPLICANT→RECRUITER (WHERE includes `role=APPLICANT`, never demotes ADMIN, no-op for RECRUITER). One-way.
- **Employer name dedup** via partial-UNIQUE `ix_employers_name_norm_live` → 409 `employer_name_taken`. **Unique-violation walks `__cause__`:** raw `asyncpg.UniqueViolationError` at `e.orig.__cause__`; route does `cause = getattr(orig, "__cause__", None) or orig` then `type(cause).__name__ == "UniqueViolationError"` (avoids importing asyncpg). `await session.rollback()` on both branches.
- **`_load_recruiter_job(job_id, user, session)` is canonical** for PATCH/DELETE/applicants — `_require_recruiter` first (403 before id lookup), joins `EmployerUser` for ownership, filters soft-deleted, uniform 404. **Reuse, don't re-implement.** `DELETE` returns 404 on the second call (not 204).
- **`PATCH` re-embeds ONLY when a content field changes** — `_EMBED_TRIGGERING_FIELDS = {title, description, locations, min_exp_years, max_exp_years, ctc_min, ctc_max}`. Status-only PATCH does NOT dispatch `embed_job`. Status via Pydantic `Literal["open","closed"]` → 422 on unknown. `embed_job` import is **deferred inside the route fn** (module-level triggers `Settings()` at collection); dispatch in broad-except `embed.dispatch-failed`.
- **`/v1/jobs/me` MUST be declared BEFORE `/v1/jobs/{job_id}`** (FastAPI matches in order; NOTE comment — don't reorder). Counts via `func.count(distinct(case(...)))` to emulate `COUNT(... FILTER)` in one GROUP BY: `applicant_count` = `status='applied' AND deleted_at IS NULL`; `surfaced_match_count` = `surfaced_at IS NOT NULL AND deleted_at IS NULL`. `?status` is `Literal["open","closed"]` — fail closed; an untyped param silently bypassed the open-only default for any junk value. Cursor query served by `ix_jobs_employer_posted_at_live (employer_id, posted_at DESC, id DESC)` (0019; replaced the redundant-prefix `ix_jobs_employer_id_live`).
- **`GET /v1/jobs/{id}/applicants` is PII-audited** (`job.applicants_listed` audit row + `recruiter.applicants-listed` structlog) — it exposes names + emails, same disclosure class as the resume download. Any new recruiter endpoint exposing applicant PII must audit.
- **Recruiter resume download:** `Content-Disposition` built via `_content_disposition_attachment()` (RFC 6266 — the filename is applicant-controlled; raw interpolation let quotes/CRLF break the header). Blob read happens AFTER the audit commit (connection released during storage I/O).
- **`JobRead.employer_verified` is required** — build every `JobRead` via `JobRead.from_job_and_employer(job, employer)` (only legit constructor; callers with only `Job` must fetch the employer). Unverified employers' jobs still surface in `/v1/feed`.
- **`GET /v1/jobs/{id}/applicants`** uses `Applicant.full_name` for `display_name` (User has none); joins `Application → Applicant → User`. **`GET /v1/applications/{id}/resume`** = recruiter download: caller must be RECRUITER at the owning employer; single JOIN (`Application → Job → EmployerUser → Resume[outer]`), any leg fails → uniform 404; latest via `ORDER BY Resume.created_at DESC`. Emits `recruiter.resume-accessed` structlog + `audit_log()`.

### Employer team management (R4) — spec `2026-06-06-recruiter-employer-experience-design.md` §5

- **Role is DERIVED from membership, never set directly.** `jobify/employers/membership.py`: `flip_to_recruiter` (any join → APPLICANT→RECRUITER, never ADMIN) + `maybe_demote_to_applicant` (zero live memberships left → RECRUITER→APPLICANT) are the only `users.role` writers in this flow. `current_user` re-fetches per request → a removed recruiter loses access within the access-TTL (no token revocation). **Any new join/leave path must call these.**
- **RBAC helpers (`jobify_api.auth.dependencies`):** `_require_employer_member` (uniform 404 if no live link — don't leak existence), `_require_employer_owner` (404 if not a member, then 403 `not_an_owner`). Owner mutates members/invites; any member reads. Called BEFORE any resource lookup.
- **Last-owner guard is lock-based:** `_count_live_owners(..., lock=True)` does `SELECT … FOR UPDATE` on owner rows (aggregates can't carry FOR UPDATE — lock rows, count in Python), used in the demote/remove guards — else two concurrent owner removals both pass `<=1` → zero owners. Membership inserts (`add_member`, `accept_invite`) catch the `ix_employer_users_pair_live` `IntegrityError → 409 already_a_member` (mirrors `create_employer`).
- **Invites:** `POST …/invites` outboxes a `Notification` (kind `employer_invite`) ONLY when the email maps to an existing user (`notifications.user_id` NOT NULL); brand-new invitees discover via `GET /v1/me/invites`; SES deferred. Invitee routes (`jobify_api.routes.invites`) authorize by `invite.email == current_user.email` (NOT membership); lazy expiry (`pending`→`expired` on read/accept, 410); accept verifies the employer is live; decline reuses the `revoked` status. Slugs: `employer.{member_added,member_role_changed,member_removed,invite_created,invite_accepted,invite_revoked}`.
- **`employer_invites.email` is PII** → DSR export adds `received_invites`/`sent_invites`, delete erases invites where `email==user.email OR accepted_user_id==user.id`. **Any new PII *table* must be added to `jobify/dsr/__init__.py` + `deleter.py` + the `test_user_export_top_level_fields` pin.** No self-leave endpoint yet (direct-add is one-way; removing yourself needs another owner).

## Test patterns

- **Two conftests.** `tests/conftest.py` `client` uses a **fake DSN** (`postgresql+asyncpg://u:p@h:5432/d`) — app boots, no DB; unit tests use this. `tests/integration/conftest.py` shadows it with real Postgres + savepoint rollback: session on a connection holding an outer txn, `join_transaction_mode="create_savepoint"` lets tests `await session.commit()` without escaping; teardown rolls back (**no truncation between tests**). Test DB URL = `JOBIFY_TEST_DB_URL` (NOT `JOBIFY_DB_URL`) — CI must set it or conftest falls back to the local `jobify:jobify` role.
- **Every `tests/integration/test_*.py` needs module-level `pytestmark = pytest.mark.integration`** — CI's unit job (`-m "not integration and not eval"`) has NO Postgres; an unmarked test leaks into it and fails at connect. Per-test decorators drifted (5 strays); locally invisible because a dev DB is always up.
- **Savepoint sessions hide driver-codec types.** An ORM object created in-test returns the Python value you assigned (identity map) — pgvector only materializes `numpy.ndarray` on a real DB round-trip. Serialization tests must `session.expire_all()` after commit (see `test_export_serializes_pgvector_embedding`; the DSR export 500'd in prod while tests passed).
- **Three HTTP clients:** `client` (sync `TestClient`, separate loop — only for routes NOT sharing the `session` connection); `async_client` (`httpx` + `ASGITransport`, shares the loop, overrides `get_session` for savepoint isolation — **default**); `concurrent_async_client` (real pool, no override — required for `SELECT … FOR UPDATE` tests e.g. refresh-token reuse; teardown `TRUNCATE ... RESTART IDENTITY CASCADE`).
- **`poolclass=NullPool`** on the integration engine forces a fresh asyncpg connection bound to the current test loop (else reused connections raise loop-mismatch). Keep it.

## Conventions

- **uv only** (don't `pip install` — bypasses `uv.lock`). **No Docker for MVP** (Homebrew `postgresql@16`).
- **Hand-written migrations** in `core/src/jobify/db/migrations/versions/` (autogenerate off; excluded from mypy). Edit the revision before `upgrade head`.
- **structlog only** — `structlog.get_logger(__name__)`, context as kwargs; no `print`/`logging.getLogger`. `JOBIFY_LOG_FORMAT=json` for prod.
- **All handlers `async def`.** Versioned routes under `/v1` except bare `/health` + `/ready` (probes).
- **Branch workflow → `WORKFLOW.md`.** One short-lived branch per feature off latest `origin/main`; `scripts/new-feature.sh <name>` to start, `scripts/sync-with-main.sh` to reconcile after a squash-merge (it auto-`rebase --onto`s past already-merged commits — never restack new work on a merged branch).
- **Doc ownership.** Operational content (commands, env vars, setup, endpoint docs) lives in `api/README.md` / `app/README.md`; this file holds only code-invariants ("why it's shaped this way / what breaks if changed") + a spec pointer per section. Keep CLAUDE.md well under 40k — it's loaded into every session and truncates silently past the limit.

## Source-of-truth when in doubt

- API conventions + roadmap → `IMPLEMENTATION_SPEC.md`. Product scope → `docs/prd/KPA_Enhanced_BRD_v1_1.pdf`. Per-slice design → `docs/superpowers/specs/` (spent build plans were removed once shipped — in git history).

## Flutter app (`app/`)

Applicant iOS + Android + Web. `lib/data/` + `lib/presentation/` + `lib/core/` (no `domain/`); abstract repo interfaces next to impls (`data/<feature>/<repo>_repository.dart` + `_impl.dart`). Riverpod 4.x (code-gen), dio 5.7, go_router 14.6 with `StatefulShellRoute.indexedStack` (four-tab nav). Run/test commands + web-OAuth origin setup: `app/README.md`. Re-run `dart run build_runner build --delete-conflicting-outputs` after touching `@freezed`/`@riverpod`/`@JsonSerializable`.

### Non-obvious bits

- **Refresh-on-401 interceptor** (`lib/data/api/refresh_on_401_interceptor.dart`) is the most important code: single-flight via `Completer<String>?`. Tests are the canonical spec — keep passing. **Cleanup order:** `_inFlight = null` BEFORE `complete()` (else a synchronous continuation re-enters `onError` on a stale completer).
- **Don't override `validateStatus` on Dio** — `(s) => s < 500` masks 401s so the refresh interceptor never fires (tests pass because the mock maps 401→reject). Default Dio (4xx/5xx throws) is required.
- **`AccessTokenHolder`** — mutable singleton bridging dio (below Riverpod) and the app. `dio_provider` depends on `authStateProvider` (presentation) to push `SignedOut` on refresh failure — the ONE documented data→presentation exception.
- **Riverpod 4.x codegen drops the `Notifier` suffix** — `AuthStateNotifier` → `authStateProvider`.
- **No feed mutation on apply/save/withdraw/unsave** — each invalidates the relevant list controller + `jobDetailControllerProvider(id)`, never the feed.
- **List screens share `PagedState<T>` + `loadNextPage`** (`lib/presentation/paging/`). The error path preserves loaded items via `AsyncValue.error(...).copyWithPrevious(...)` — `copyWithPrevious` is `@internal`; the `// ignore: invalid_use_of_internal_member` in `paging.dart` is load-bearing.
- **Magic strings in enums** (`JobStatus`/`ApplicationStatus`/`ApplicationSource`/`MatchGenerator` use `@JsonKey(unknownEnumValue: X.unknown)`; slugs in `lib/core/error/auth_slugs.dart`). DTOs are `@JsonSerializable` plain by default; `@freezed` only for `copyWith` (`JobDetailDto` + `PagedState<T>`).
- **`/v1/me` is nullable on `email` + `applicant.full_name`** (DB columns are nullable — DSR scrubbing / phone-only auth later); `MeDto` mirrors this with `String?`. Keep DTO nullability in lockstep with the Pydantic response models, not with the happy path.
- **Per-tab nav stacks** — `/jobs/:id` is a child under each branch; JobDetail's 404 uses `context.pop()`.
- **Widget tests use `ThemeData.light(useMaterial3: true)`, NOT `buildTheme()`** (`buildTheme` calls `GoogleFonts.inter(...)` → network fetch, fails offline/CI).
- **`PackageInfo.fromPlatform()` in a `keepAlive: true` provider**, not `FutureBuilder.future:` (which re-runs the platform-channel per rebuild). **`DateFormat` instances module-static** (ICU parse at construction).
- **`--dart-define`, no flavors:** `JOBIFY_API_BASE_URL` + `JOBIFY_GOOGLE_WEB_CLIENT_ID` required at compile time (`Env.validateOrThrow()` in `main()`). Light theme only in v0. Shared test infra in `test/helpers/` (`MockInterceptor`, `fake_repositories.dart`).
- **Google sign-in is two flows** (detail: `specs/2026-05-21-flutter-app-shell-design.md`). Mobile: imperative `GoogleSignInDataSource.getIdToken()`. Web: GIS `signIn()` returns no `idToken`, so `google_web_sign_in.dart` uses `renderButton()` via `googleWebSignInProvider` (`keepAlive FutureProvider` awaiting `initialize()`); impl by conditional import (`_web.dart` / `_stub.dart` keeps `dart:js_interop` off mobile/test); `SignInScreen` branches on `kIsWeb`. `completeWebSignIn(idToken)` lives on the impl, reached via downcast. `GoogleSignInDataSourceImpl` builds `GoogleSignIn` platform-conditionally (`clientId:` web / `serverClientId:` mobile).
- **Local web sign-in** needs an Authorized-JS-origin on the web OAuth client + API CORS (`JOBIFY_CORS_ALLOW_ORIGINS`) — full setup + curl probe in `app/README.md` ("Web Google sign-in").
- **Privacy screen** (`presentation/privacy/`) = consent toggles + DSR export + DSR delete nav. Reserved scopes (`whatsapp_notifications` etc.) deliberately HIDDEN (no Dart gate yet). DSR export uses the clipboard in v0. DSR delete is a separate screen `/profile/privacy/delete` with a `DELETE_MY_ACCOUNT` guard; success → clear `AccessTokenHolder`, push `SignedOut`. Turning OFF `email_transactional` triggers a confirmation dialog.
- **Recruiter feature** (`presentation/recruiter/` + `data/jobs/recruiter_*` + `data/employers/team/`; spec `2026-06-06-recruiter-employer-experience-design.md`). Second `StatefulShellRoute` under `/recruiter/*`; `roleAwareRedirect` (`role_redirect.dart`) flips shells on `SignedIn.role`. Team tab (`recruiter_employer_screen.dart`) derives owner-ness from the caller's own roster row via `SignedIn.userId` (UI gating is defense-in-depth) and HIDES change-role/remove on your own row. Invitee `PendingInvitesScreen` (`/profile/invites`) accepts → `refreshSession()` → role flips → redirect to recruiter shell; **`accept()` treats `acceptInvite` as the success boundary** (a failed post-accept refresh is swallowed — re-accepting 404s). `/recruiter/jobs/:id/edit` with null `extra` resolves the job from the include-closed list via `EditJobResolver` (no blank create form). Dashboard sums `listMyJobs(status:'closed')` (open+closed) client-side.
