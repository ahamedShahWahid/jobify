# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

KPA (Khan Placement Agency) is an early-stage placement platform. The repo currently contains:

- `api/` — FastAPI backend (Python 3.12, `uv`-managed). Currently shipped: health/readiness probes, async SQLAlchemy + Alembic against Postgres 16, Google OAuth sign-in + rotating refresh JWTs, `GET /v1/me`, resume upload + retrieval at `/v1/applicants/me/resumes`, and the Celery + Redis parse worker. Matching is the next major slice and is deferred.
- `IMPLEMENTATION_SPEC.md` — **how** we build it (the engineering spec; owner-authored, v0.2 MVP-first).
- `docs/prd/KPA_Enhanced_BRD_v1_1.pdf` — **what** we're building (product BRD/PRD; source of truth for scope).
- `docs/superpowers/plans/` and `docs/superpowers/specs/` — per-feature plans and design docs.

The Flutter mobile + web frontend described in the spec (§3) does not yet exist in this repo. The spec overrides the BRD's React Native + Next.js stack — see `~/.claude/projects/-Users-ahamadshah-ahamed-personal-kpa/memory/kpa-frontend-stack-flutter.md`.

When scope and "how" conflict, the BRD wins on product behavior; the spec wins on tech choices.

## Working directory note

Almost all backend commands run from `api/`, not the repo root. The `uv` workspace, `alembic.ini`, and `pyproject.toml` all live there. The README in `api/` is the most up-to-date reference for day-to-day commands; this file calls out only the non-obvious bits.

## Commands

```bash
# From api/
uv sync                                                   # install deps
uv run --env-file=.env uvicorn kpa.main:app --reload --port 8000

# Migrations (writes to KPA_DB_URL)
uv run alembic upgrade head
uv run alembic revision -m "describe the change"          # hand-edit; no --autogenerate by default
uv run alembic downgrade -1

# Tests
uv run pytest -v -m "not integration"                     # fast, no DB
uv run pytest -v -m integration                           # needs local Postgres + kpa_test DB
uv run pytest -v tests/unit/test_settings.py::test_db_url_rejects_sync_driver           # single unit test
uv run pytest -v tests/integration/test_resumes_auth.py::test_upload_recruiter_role_returns_403  # single integration test

# Lint / format / type-check
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy                                               # strict; src/kpa only, migrations excluded
```

Single-source for env vars is `api/.env` (copy from `.env.example`). Required at boot: `KPA_ENV`, `KPA_SERVICE_NAME`, `KPA_DB_URL`, `KPA_REDIS_URL`, `KPA_JWT_SECRET` (≥32 bytes), `KPA_GOOGLE_OAUTH_CLIENT_IDS`. The app refuses to boot if any required var is missing or invalid (see `settings.py`). Integration fixtures inject `KPA_JWT_SECRET="x" * 32` and `KPA_GOOGLE_OAUTH_CLIENT_IDS=test.apps.googleusercontent.com` — match these if you stand up a new app under test.

`KPA_DB_URL` **must** use the `postgresql+asyncpg://` driver — this is enforced in `Settings._enforce_async_driver`.

## Architecture — non-obvious bits

### App wiring (`src/kpa/app_factory.py`)

`create_app()` builds a fresh app on every call so tests get full isolation. It owns the lifecycle of three things stored on `app.state`:

- `settings` — validated `Settings` instance.
- `db_engine` + `db_sessionmaker` — single async engine. The engine sets `search_path=kpa` via asyncpg `server_settings`, so model code does **not** need to repeat `schema="kpa"` on every query (the `Base.__table_args__` declares it once for DDL).
- `storage` — a `Storage` protocol implementation (currently `LocalFileStorage`).

Routes get these via FastAPI `Depends(...)` (`get_session`, `get_storage`) that read from `request.app.state`. This keeps routes thin and lets tests swap dependencies via `app.dependency_overrides`.

The engine is disposed on the FastAPI `shutdown` event. Don't create your own engine in module scope.

### Middleware — pure ASGI, not BaseHTTPMiddleware

`RequestIdMiddleware` (`middleware/request_id.py`) is implemented as a pure ASGI middleware on purpose. Starlette's `BaseHTTPMiddleware` wraps the inner app in an `anyio` task group, which makes asyncpg detect a mismatched event loop and raise `Future attached to a different loop` — both in tests and prod. **New middleware in this repo should follow the same pure-ASGI pattern** until something forces otherwise.

The request id is a uuid4. A client-supplied `X-Request-Id` is honored only if it parses as a valid uuid4; otherwise it's replaced. Every response (including problem+json errors) carries this header — it's the only correlation handle in the logs.

Starlette's `CORSMiddleware` is mounted **after** `RequestIdMiddleware` (so it's outermost — it answers the browser preflight and stamps `Access-Control-*` on every response, errors included). It's pure-ASGI, so it doesn't trip the asyncpg loop issue above. Origins come from `KPA_CORS_ALLOW_ORIGINS` (CSV, default `http://localhost:8080` — the Flutter web dev server). Bearer-token auth (no cookies) → `allow_credentials` stays off. Only the web client needs this; mobile sends no `Origin`.

### Error handling — RFC 7807 problem+json

`middleware/error_handler.py` replaces FastAPI's default error shape. Both `HTTPException` and unhandled `Exception` flow through `_problem()` and produce `application/problem+json` with a `request_id` field. The unhandled-exception path explicitly re-attaches the `X-Request-Id` header because Starlette's `ServerErrorMiddleware` sits outside `RequestIdMiddleware` in the stack.

When you raise `HTTPException`, the `detail` becomes the user-visible `detail` field. Treat it as a user-facing string, not a debugging aid.

### Resume route invariants — error ladder

`routes/resumes.py` enforces an error ladder in this exact order. Each layer assumes the previous passed; don't reorder them.

1. **401** — Bearer header parsing + JWT validation + user-row re-fetch (`current_user`). Slugs: `missing_bearer_token`, `invalid_access_token`, `user_not_found`.
2. **403** `not_an_applicant` — `_require_applicant` rejects recruiter/admin tokens **before any DB read for an applicant row**.
3. **500** `applicant_missing` — defense in depth; theoretically unreachable because `AuthService._upsert_identity` provisions the applicants row on first sign-in. The handler logs `applicant.row-missing-for-applicant-role` so it pages if it ever trips.
4. **415** — content-type whitelist (`KPA_ALLOWED_RESUME_CONTENT_TYPES`).
5. **413** — size cap (`KPA_MAX_UPLOAD_BYTES`, default 10 MiB).
6. **404** `resume not found` (GET only) — **uniform** across "unknown resume id" AND "owned by another applicant". Both cases are collapsed in a single JOIN'd query (`routes/resumes.py:182-193`). Distinguishing them would leak whether a resume id exists — commit `ac9efdf` for the rationale. Keep the slug uniform if you add new lookup paths.

The applicant id is **never** taken from the URL — it's resolved from `current_user.id` via `_require_applicant`. The route prefix is `/v1/applicants/me` (the `me` is literal, not a placeholder).

The storage key is set **after** the DB flush so we can name the blob `resumes/{resume.id}{ext}`. The extension comes from `_CONTENT_TYPE_TO_EXT` keyed off the validated content-type — never trust the uploaded filename's extension. There's no rollback compensation if the blob write fails after the row exists; for the MVP this is fine because we still own the DB cleanup, but be aware before adding S3.

Parse dispatch is fire-and-forget post-commit — see §"Parse worker" below for why the broad `except Exception` around `parse_resume.delay()` must stay broad.

### Soft delete model

Every domain table carries `id` (uuid4), `created_at`, `updated_at`, `deleted_at TIMESTAMPTZ NULL`. Live-row queries must filter `deleted_at IS NULL`. Uniqueness is enforced via partial indexes `WHERE deleted_at IS NULL` (see `User.ix_users_email_live`, etc.). When you add a new table, follow this pattern — the `CreatedAt` / `UpdatedAt` / `DeletedAt` `Annotated` types in `db/models.py` are reusable.

The `Base.__table_args__` is typed `Any` and uses `# noqa: RUF012` because SQLAlchemy's declarative base types this as a class-level mutable. Don't "fix" the noqa.

### Audit logs

- **Append-only.** `audit_logs` has no UPDATE or DELETE paths in code. The `CreatedAt` / `UpdatedAt` / `DeletedAt` `Annotated` types in `db/models.py` are deliberately NOT used on `AuditLog` — this is the documented exception to the soft-delete pattern above. Queries against `audit_logs` never filter `deleted_at IS NULL`.
- **Caller owns the txn.** `await audit_log(session, action=..., actor=..., resource_type=..., resource_id=..., context=...)` flushes one row inside the caller's transaction. No commit, no fire-and-forget dispatch. The row is as durable as the business action it records — if the request rolls back, the audit row rolls back too. Spec §5.1 documents why fire-and-forget was rejected (broker outage → evidence loss; rolled-back business txn → false evidence).
- **`actor_user_id` is `ON DELETE SET NULL`.** Load-bearing for future DSR-delete (sub-project D, scoped as "hard-delete PII, keep anonymized aggregates"): hard-deleting a user succeeds, but the audit row survives — re-identification of the deleted user is intentionally impossible.
- **`actor_role` is a snapshot** at action time, plain TEXT (not the `UserRole` enum) because `'system'` is a valid value for cron / worker actions where `actor=None`. A user whose role later flips (applicant → recruiter via `POST /v1/employers`) still has audit rows showing the role they had at the time.
- **Helper guard.** `audit_log(actor=None, actor_role=None)` raises `ValueError` before touching the session. The DB's `actor_role NOT NULL` would have caught it anyway, but the helper-boundary check is cheaper to debug.
- **Action-slug namespace:** dotted, lowercase, verb-past. Reserved top-level prefixes: `resume.*`, `application.*`, `job.*`, `consent.*` (P4-B), `user.*` (P4-C/D for DSR), `admin.*`, `auth.*`, `employer.*`. Full table in `docs/superpowers/specs/2026-05-28-audit-logs-substrate-design.md` §4.
- **The structlog line stays.** Fluent Bit → Elasticsearch → Kibana is the live operational channel (PagerDuty filters, on-call queries); the DB row is the durable channel. Both fire from the same handler — they are complementary, not substitutes. The `recruiter.resume-accessed` structlog line in `routes/applications.py:recruiter_download_application_resume` is the canonical example: structlog FIRST, `audit_log()` SECOND, then the side-effecting work.
- **No retention TTL yet.** Indefinite retention until the table grows past ~10M rows; a `purge_old_audit_logs` Celery beat task is the deferred follow-up.

### Consent + notification-channel preferences

- **`user_consents` is the operational state**, `audit_logs` is the history. Every grant/revoke via `set_consent(...)` writes one audit row in the same txn. No-op flips (`granted=true → granted=true`) write no audit row — DPDP auditability is about state changes, not re-affirmations.
- **`ON DELETE CASCADE` on `user_id`** — opposite of `audit_logs` (SET NULL). Consent for a non-existent user is meaningless; the row vanishes with the user. The audit-log entries documenting their grants survive via `audit_logs.actor_user_id ON DELETE SET NULL`.
- **Eager seeding at signup.** `auth/service.py:_upsert_identity` calls `seed_default_consents(...)` on the new-user branch in the same txn. All later reads are simple SELECTs — no default-fallback logic in the hot path. Changing a default later affects only NEW signups; existing users' explicit values aren't unilaterally revoked.
- **`email_transactional` defaults to `true` at signup** — legally-borderline call. The signup UI MUST notify the user ("by signing up, you agree to receive service-related communications"); sub-project F's consent screen will own that copy.
- **Sweep gate.** `sweep_notifications._dispatch_one` looks up consent between the user load and the channel dispatch. No consent → `status=CANCELLED`, `cancelled_at=now()`, terminal. Re-granting does NOT resurrect cancelled rows.
- **`LookupError` fallback in the sweep.** If `get_consent` raises (means seeding was skipped — pre-P4-B user, or DSR-delete cascaded the row), the sweep falls back to `DEFAULT_CONSENTS[scope]`. The backfill CLI (`kpa-seed-consents`) closes the pre-P4-B gap for existing users.
- **`CANCELLED` is a Postgres native-enum value** added via `ALTER TYPE ... ADD VALUE` inside `op.get_context().autocommit_block()` (Alembic 0014). This is the canonical example of a future enum-extension migration. Note: Postgres does NOT support `DROP VALUE` — downgrading 0014 leaves `cancelled` in the type, which is harmless.
- **Inbox excludes `CANCELLED`.** `GET /v1/notifications` filters `status NOT IN ('failed', 'cancelled')`. The user explicitly didn't want these; they shouldn't surface.
- **Scopes are a `StrEnum` at the API boundary, plain TEXT in the DB.** Mirrors `audit_logs.action`. Reserved scopes ship in v0 with default `false` (WhatsApp, SMS, recruiter visibility, third-party sharing) so adding their impls later doesn't need an enum migration.
- **`set_consent` is the only path that writes a `consent.*` audit row.** Don't write audit rows for consent state changes by hand — the no-op-on-noop optimization is centralized.
- **Adding a new value to a Postgres native enum** (e.g., `NotificationStatus`) requires `ALTER TYPE ... ADD VALUE` which cannot run inside a transaction with other DDL. In sync-mode Alembic this is `op.get_context().autocommit_block()`. In async-mode (our setup), the `autocommit_block()` API trips on the connection's `_in_external_transaction` flag — Alembic 0014 uses a `bind.commit()` + `bind.connection.dbapi_connection.run_async(...)` workaround as a documented exception. **DO NOT** copy this pattern unprompted; it bypasses SQLAlchemy's transaction tracking. If you need to add an enum value, first try `autocommit_block()`; if it actually fails in our env, document the error before reaching for the workaround.

### DSR export

- **Sync HTTP, JSON envelope.** `POST /v1/me/dsr/export` returns the dump immediately as `application/json` with `Content-Disposition: attachment; filename="kpa-data-export-{user_id}-{timestamp}.json"` and `Cache-Control: no-store`. MVP-acceptable at our scale; switch to async + signed-URL when an applicant's audit history exceeds ~10K rows.
- **`refresh_tokens` are NEVER in the export.** They are session secrets, not personal data; exporting them would let an exposed export be used to impersonate the user. A `redactions` entry documents the exclusion to the user.
- **Defensive column-name denylist in `kpa/dsr/__init__.py`** — `_REDACTED_COLUMN_NAMES` + `_REDACTED_COLUMN_SUFFIXES` strip any column named `totp_secret`/`*_secret`/`password_hash`/`*_password`/`access_token`/etc. from EVERY serialized row, regardless of which table it lives on. Today the schema has zero such columns; the denylist exists so that when MFA / new OAuth-token storage ships in later sub-projects, those columns do NOT silently land in DSR exports. **When you add a new sensitive column anywhere in `db/models.py`, extend the denylist** — `test_row_to_dict_drops_redacted_columns` pins the contract.
- **`audit_history` is `actor_user_id = self.id` only** in v0 — not the full `(resource_type, resource_id)` join across user-owned resources. Documented v0 limit per spec §4.2. Expand when a regulator pushes back.
- **Two audit rows per export.** `user.dsr_export_requested` (written + flushed BEFORE assembly so it's durable on assembly failure) and `user.dsr_export_completed` (written AFTER with `section_counts` in context). Failed-export replay is admin tooling later.
- **Reserved action slugs for sub-project D (DSR-delete):** `user.dsr_delete_requested`, `user.dsr_deleted`. Don't reuse these prefixes.
- **Recruiters get a different envelope** — applicant sections (`applicant`, `resumes`, `applicant_embedding`, `applications`, `saved_jobs`, `matches`) are empty; `employer_memberships` + `owned_jobs` populated. Admins get an all-empty envelope today.
- **Per-section serialization is `dict[str, Any]`** not per-table Pydantic models. Trade-off for v0 — we don't introduce 12 row-shape models. The export contract is the section SET, not the row schemas; row schemas drift with the existing tables and the export inherits that.

### DSR delete

- **Soft-delete + scrub, not hard-delete the User row.** Hard-deleting users would CASCADE-wipe applications and matches (FKs to applicants → users), losing recruiter analytics and the eval substrate. The brainstorm constraint was "hard-delete PII, keep anonymized aggregates" — we honor it by tombstoning `users` and `applicants` with PII scrubbed, then hard-deleting the truly-PII tables around them.
- **Migration 0015 made `applicants.full_name` + `applicants.locations` nullable** specifically to enable scrubbing. When you add a new PII column to applicants/users/resumes, decide whether it needs the same nullability + tombstone treatment, and update `delete_user_data` + a follow-up migration.
- **Application-layer deletion graph, not FK CASCADE.** Several FKs are CASCADE (Notification, UserConsent → users) but we don't rely on them; the orchestrator (`kpa.dsr.deleter.delete_user_data`) walks the graph explicitly so the report counts and the order-sensitive blob-delete-before-scrub work correctly.
- **Atomic transaction.** Unlike the export (whose `dsr_export_requested` row is durable on assembly failure), the delete's `dsr_delete_requested` audit row commits or rolls back atomically with all destructive work. Partial deletion is worse than no deletion. The route handler does an explicit `await session.commit()` at the success path so atomicity is pinned to the handler, not the request lifecycle.
- **`audit_logs.actor_user_id` references survive** as pointers to the tombstone — soft-delete-and-scrub keeps the User row, so the FK still resolves. `SET NULL` only fires if a future admin sub-project hard-deletes the tombstone (post-retention).
- **Re-signup works** because `_upsert_identity`'s email-collision check filters `deleted_at IS NULL` — tombstoned emails (scrubbed to NULL anyway) don't conflict.
- **Confirmation token in body, not query.** `DELETE /v1/me/dsr` with body `{"confirmation": "DELETE_MY_ACCOUNT"}` — query-string would leak the token into access logs.
- **Sole-owner employer edge case** surfaces a `warnings` entry in the response. The employer stays (admin tooling handles reassignment). Recruiter's `employer_users` rows still hard-delete.
- **Resume blob deletion is best-effort.** Storage 5xx logs `dsr.blob-delete-failed` but doesn't roll back the DB. Orphaned blobs are reaped by a future janitor; tracked for the deploy-target (P5) sub-project.
- **NO HTTP idempotency after a successful DSR delete.** Subsequent calls return 401 `user_not_found` because `current_user` re-fetches and the tombstone is soft-deleted. Clients should treat 401 as "already done" post-DELETE. Operationally idempotent (the data is gone) but not HTTP-idempotent.
- **Integration test for the 401-after-delete path uses `concurrent_async_client`** (real connection pool), not `async_client`. The savepoint-bound session caches the user object in its identity map; a fresh pool connection guarantees a real refetch.

### Don't reuse models as response schemas

Per spec §4.2 and the comment in `db/models.py`: SQLAlchemy models are never response models. Define `*Read` / `*Create` / `*Update` Pydantic v2 models in the route module (see `ResumeRead` with `ConfigDict(from_attributes=True)` for the conversion pattern).

### Auth + JWT invariants

- `current_user` (`auth/dependencies.py`) re-fetches the user row on every call. A user soft-deleted 30s ago is locked out within the access TTL (≤10 min), not the refresh TTL. Don't add caching here.
- **Sign-in always provisions `role=APPLICANT`** (`auth/service.py:_upsert_identity`). Tests needing a recruiter/admin must create the row directly via `session` and mint a token with `mint_access_token` — there is no "sign in as recruiter" path. See `tests/integration/test_resumes_auth.py` for the canonical pattern.
- 401 slugs are deliberately generic. `invalid_access_token` never differentiates signature failures from claim failures — it's a timing-oracle countermeasure baked into `tokens.py:AccessTokenError`. Don't add more specific slugs.
- Refresh rotates on every use. Re-presenting an already-rotated token triggers full family revocation via `_revoke_family` ("reuse detected"). The bulk UPDATE relies on Postgres READ COMMITTED + EvalPlanQual semantics to catch concurrent legitimate rotations — don't switch it to a row-at-a-time loop.
- JWT secret must be ≥32 bytes; HS256, issuer `kpa-api`, `jti` required. The 30s `iat` skew tolerance is checked manually because PyJWT's leeway would relax `exp` too.

### Admin moderation

- **`/v1/admin/*` is gated by `_require_admin` after `current_user`.** Layer order: `current_user` → 401 invariants → `_require_admin` → 403 not_an_admin → DB read. No DB lookups for admin-only resources happen before the role check.
- **Suspended users get 401 `user_suspended`** from `current_user`, not 403. The slug is distinct from `user_not_found` and `invalid_access_token` so clients can show "Your account has been suspended. Contact support." On Flutter the refresh interceptor short-circuits to sign-out for any non-`invalid_access_token` 401 — that means suspended users are signed out cleanly without an attempted refresh.
- **`users.suspended_at` AND `users.suspension_reason` clear together.** Unsuspending is `UPDATE users SET suspended_at=NULL, suspension_reason=NULL`. Never leave a stale reason on an unsuspended row — admin tooling reads (reason IS NOT NULL) as "this user is suspended" defensively.
- **`admin.user.suspended` writes a new audit row on every call**, even if the user is already suspended (re-suspension with a different reason is meaningful audit evidence). `admin.user.unsuspended` is no-op-on-noop — calling unsuspend on an active user writes no audit row.
- **Suspending self is blocked** with 400 `cannot_suspend_self`. The admin cannot lock themselves out — recovery would need direct DB access.
- **`kpa-grant-admin <email>` is the bootstrap path.** No `POST /v1/admin/users/{id}/grant-admin` route — bootstrap chicken-and-egg. Once the first admin exists, follow-ups can ship a route.
- **Audit-log viewer (`GET /v1/admin/audit-logs`)** does NOT write an audit row for the query itself. Self-auditing-of-admins is overkill at MVP scale; access logs (Fluent Bit → Elasticsearch) capture each call's `request_id`.
- **Reserved action slugs (still unused by this PR):** `admin.job.unpublished`, `admin.user.dsr_export_requested`, `admin.user.dsr_deleted`. Don't repurpose them.

### Parse F1 quality gate

- **Gold dataset lives in `api/data/parse_eval/`** as `<id>.txt` + `<id>.expected.json` pairs. 8 examples in v0 covering software, data science, frontend, fresher, PM, DevOps, mobile, ML personas. Each `.txt` is raw resume text — text extraction (PDF/DOCX) is intentionally bypassed because the gate measures the parser's heuristics, not the byte-to-text step.
- **Run:** `uv run pytest -m eval` (added marker registered in `pyproject.toml`). The single test `test_library_parser_meets_quality_gate` runs `kpa.eval.parse_f1.eval_gold_dataset()` and asserts the gate.
- **Gate config** (spec §13 P1 target): overall macro-F1 ≥ 0.85, per-field floors `email ≥ 0.95`, `phone ≥ 0.85`, `name ≥ 0.70`, `skills ≥ 0.75`. Ratchet to 0.90 overall before launch.
- **Only 4 fields are scored** today: `name`, `email`, `phone`, `skills`. The other `ParsedResume` fields (`experience`, `education`, `certifications`) are extracted by noisier date-range/keyword regex — they print in the breakdown but don't gate. Add them to the gate when the LLM parser replaces `LibraryResumeParser`.
- **Set-skills F1** treats predicted + expected as sets (case-folded). False positives count — the substring-containment matcher in `_extract_skills` is known to over-match short SKILLS dict entries; keeping FPs in the F1 measures that drift.
- **Adding a gold example:** drop a `.txt` + `.expected.json` pair with the next id, re-run `uv run pytest -m eval -v -s` to see the per-example breakdown. If a new example tanks a per-field floor, decide whether to fix the expectation or accept the parser limitation (and document why).
- **CI runs the gate** as a separate `lint-types-unit-eval` job in `.github/workflows/api.yml`, before the heavier `integration` job. No DB needed for the eval — it runs against the in-process parser.

### Parse worker (Celery + Redis)

- **Dispatch is fire-and-forget after commit.** `routes/resumes.py` wraps `parse_resume.delay()` in a broad `except Exception` with `exc_info=True` (event name `dispatch.failed`). A broker outage MUST NOT fail an upload because the row + blob are already durable — admin tooling will replay pending rows. Don't tighten the except.
- **3-transaction split.** `workers/tasks/parse.py:_parse_resume_async` is structured: (Txn1) load + idempotency gate + mark `parsing`; (no DB) read blob + extract text + parse — can take seconds; (Txn3) reload, verify still `parsing`, write `parsed_json` + `parsed`. Holding a row lock across extraction would starve other writers — preserve the split.
- **Retry contract.** `ParserError` → immediate `failed`, no retry. `TransientParserError` → Celery autoretry, up to 3 with exponential backoff. Unknown exceptions get wrapped into `TransientParserError`. On final exhaustion the row is marked `failed` *before* the raise (`parse.py:87-100`) so it doesn't wedge at `parsing`.
- **Eager mode + running event loop.** When `KPA_CELERY_TASK_ALWAYS_EAGER=true` and `.delay()` is called from inside an `httpx.AsyncClient` request, the task body's `asyncio.run()` would explode because a loop is already running. `parse.py:72-83` detects this and dispatches to a fresh thread. Tests rely on this — don't simplify it.
- **Local worker:** `uv run --env-file=.env celery -A kpa.workers.celery_app worker --pool=solo --concurrency=1 -Q parse`. `--pool=solo` is the MVP default; switch to `prefork` only with load justification.

### Embedding worker (Gemini)

- **One vector per applicant** (`applicant_embeddings.applicant_id UNIQUE`). Multi-resume applicants embed the *latest* parsed resume's canonical profile. Older resumes' content isn't reachable from matching.
- **Idempotency via `canonicalized_text_hash`** on the row. The worker computes the canonical profile text + sha256 in Txn 1, bails if the hash matches the existing row. No provider call, no row write.
- **3-transaction split** mirrors `parse_resume`: Txn 1 gate; Txn 2 (no DB) Gemini call; Txn 3 re-verify the hash hasn't drifted, then UPSERT via `pg_insert(...).on_conflict_do_update(...)`. Don't collapse.
- **Dispatched from `parse_resume` Txn 3** post-commit, fire-and-forget. Same broad `except Exception` + `_log.warning("embed.dispatch-failed", exc_info=True)` as the upload-route → parse dispatch. Don't tighten.
- **Provider task via prompt prefix.** `gemini-embedding-2` does NOT accept the `task_type` param (that was `gemini-embedding-001`). `GeminiEmbeddingProvider.encode()` formats internally; call sites pass `EmbeddingTask.DOCUMENT` / `.QUERY` + optional `title` and stay provider-agnostic.
- **`embed.py` does not import `GeminiEmbeddingProvider`.** It resolves the provider at runtime via `get_embedding_provider()`, which is the lazy-singleton in `celery_app.py`. `embed.py` imports `EmbeddingTask` etc. from `kpa.integrations.embeddings.base` and `canonicalize_profile` from `kpa.integrations.embeddings.canonicalize`.
- **The `kpa.integrations.embeddings` package `__init__` deliberately omits `GeminiEmbeddingProvider` from its re-exports** so `google.genai` (heavy dep) is not pulled in when test fixtures or other code imports the package. Code that needs the impl must import from `kpa.integrations.embeddings.gemini` directly.
- **`from module import name` gotcha for test fixtures.** Because `embed.py` does `from kpa.workers.celery_app import get_embedding_provider`, monkeypatching `celery_app.get_embedding_provider` alone doesn't intercept the worker's call (the local reference in `embed.py` still points at the original). The integration conftest's `patched_embedding_provider` fixture patches two locations and seeds one cache: `celery_app.get_embedding_provider`, `embed.get_embedding_provider` (because `embed.py` imports the function by name and holds a local reference), and the `_embedding_provider` module-level cache (so a previously-cached real provider doesn't bypass the patch). Mirror this pattern in any future fixture that needs to swap a function imported by name across modules.
- **Pgvector + HNSW + cosine.** Migration 0004 creates the `vector` extension via `CREATE EXTENSION IF NOT EXISTS vector` and the HNSW index using `vector_cosine_ops` (matches §6.3 cosine similarity). Dim is config-driven via `KPA_EMBEDDING_DIM` (default 1536; must match `Vector(N)` in the migration — no runtime assertion yet, mismatch surfaces as a Postgres error on first insert).
- **No `embed_status` column.** The embedding either exists or doesn't — no intermediate state shown to users. If retry exhaustion leaves no row, the next parse completion re-dispatches.
- **Test C coverage gap.** Integration tests cover the happy path, idempotency, "no parsed resume" branch, and dispatch resilience. The Txn 3 `content_hash_now != content_hash` race (parsed_json mutated mid-flight) is NOT tested because forcing the race within savepoint isolation is fiddly. Filed for follow-up.
- **Local worker becomes** `celery ... -Q parse,embed` (single worker, two queues) or run a second worker pinned to `-Q embed`.

### Seeding and demo data

- **`employers`/`jobs` are populated via a CLI**, not migrations. `uv run kpa-seed-jobs` reads `api/data/sample_jobs.json` and upserts. Idempotency keys: `employers.name_norm` (DB-enforced via partial UNIQUE) and `(jobs.employer_id, lower(jobs.title))` (script-only — real recruiters re-list roles).
- **The JSON encodes `posted_days_ago: int`, not `posted_at`.** Loader converts to `now() - timedelta(days=...)` at run time so the checked-in fixture doesn't visibly age. Re-seeding "ages forward" past dates.
- **Updates preserve human-set state.** `employers.name` is never overwritten (the canonical name set by a real recruiter wins over the JSON spelling). `employers.verified_at` is only set when currently `NULL` — re-verification timestamps are not stomped.
- **`_apply_in_session(session, payload, report)` is the test seam.** The CLI's `_apply()` opens its own engine; integration tests call `_apply_in_session` directly with the savepoint-bound session. Mirror this pattern if you add new seed scripts.
- **Drift guard:** `test_loader_against_sample_jobs_json` asserts `count(employers)==10, count(jobs)==27`. If you intentionally change the fixture, update the test in the same commit.
- **`embed_job` dispatch from the seed CLI** lives in `_dispatch_embeds(...)` and runs *after* `_apply` returns (outside the `asyncio.run` boundary so eager-mode `asyncio.run()` in the task body doesn't conflict). Same broad-except + `_log.warning("embed.dispatch-failed", ...)` pattern as the upload route → parse worker; broker down ≠ seed failure. Don't tighten.
- **Three modules need patching to intercept `get_embedding_provider`** in tests: `celery_app`, `embed_job`, and `embed` (P1.3). All three import the function by name, so each holds a local reference. The `patched_embedding_provider` fixture patches all three plus the `_embedding_provider` cache. Mirror this pattern in any future fixture that needs to swap a function imported by name across multiple modules.

### Scoring worker (match)

- **`matches` table is the join of the applicant and job embedding spaces.** One row per `(applicant_id, job_id)` live pair, UPSERT on rescore via the partial-UNIQUE index `WHERE deleted_at IS NULL`.
- **Two workers, one queue (`score`).** `score_applicant` is dispatched from `embed_applicant` Txn 3 post-commit; `score_job` is dispatched from `embed_job` Txn 3. Same broad-except + `_log.warning("score.dispatch-failed", ...)` pattern; don't tighten.
- **Pure-Python cosine** in `kpa.scoring.vector`. No HNSW dependency. P2.3 feed will switch to pgvector's `<=>` if top-K becomes a hot path.
- **`surfaced_at` is preserved on rescore.** The UPSERT `set_={...}` uses `func.coalesce(Match.surfaced_at, sa.case((sa.literal(crosses_threshold), func.now()), else_=None))`. Once a match is surfaced, a later rescore that drops below threshold does NOT unset it — the feed stays monotonic over time.
- **`score_components` + `model_versions` JSONB columns** record the per-rule fits and the model/weight settings used. This is the eval substrate: weight/threshold A/B can replay against historical rows without rescoring.
- **Two-transaction split (not three).** No external API call, so no need to release the DB between load and compute. Txn 1 loads everything; Python computes in memory; Txn 2 UPSERTs all rows in one commit.
- **`TransientScoringError`** wraps UPSERT failures for autoretry. Permanent issues (missing entities) are logged and return without raising.
- **Threshold (0.55) and vector weight (0.6) are env-driven.** `KPA_MATCH_SURFACE_THRESHOLD` and `KPA_MATCH_VECTOR_WEIGHT`. Per-rule structured weights are equal (1/3 each); promote to a config table once labeled feedback exists.

### Feed and job detail routes

- **`/v1/feed` filters on `matches.surfaced_at IS NOT NULL` AND `jobs.status='open'` AND both sides `deleted_at IS NULL`.** The query uses `ix_matches_applicant_surfaced (applicant_id, total_score DESC) WHERE deleted_at IS NULL AND surfaced_at IS NOT NULL` for both the seek and the order.
- **Cursor is opaque base64 of `{score, match_id}`.** Pure decoding — no server state, no expiry. Tuple comparison `(total_score, id) < (cursor_score, cursor_id)` maps cleanly to the index. Malformed cursor → `400 invalid_cursor`.
- **`peek-one + 1`**: query `LIMIT limit + 1`; trim to `limit` and set `next_cursor` if the extra row was present. Avoids a separate "is there more?" query.
- **ETag is weak.** `W/"<sha256(applicant_id + max(updated_at) + count)>"`. JSONB re-serialization order may change the body bytes without changing the data — weak ETag is semantically correct.
- **`/v1/jobs/{id}` returns the match unconditionally** when a row exists, regardless of `surfaced_at`. Pasting a URL shows the score even if the match didn't make the feed.
- **Uniform 404 across unknown / closed / soft-deleted.** Same rationale as the resumes route — distinguishing leaks existence.
- **`_require_applicant`** is duplicated inline in `routes/feed.py` and `routes/jobs.py` rather than extracted to a shared module. The `routes/resumes.py` version has different downstream error semantics (`500 applicant_missing` is load-bearing there); copying keeps each route module standalone.

### Match explanations (templated + llm)

- **`matches.explanation` is JSONB** with shape `{fit, caveat, generator, generator_version}`. Nullable for backward compat with pre-P2.4 rows. Generated inline in both score workers' compute step (no separate worker).
- **`kpa.scoring.explainer.MatchExplainer` Protocol** routes between two impls. Workers call `await get_match_explainer().explain(ctx)`; the call site does not change between templated and LLM.
- **`TemplatedExplainer`** (`kpa/scoring/explainer.py`) — wraps the pure-function `templated_explanation(...)` from `kpa/scoring/explain.py`. Deterministic, no network. `generator="templated"`.
- **`GeminiMatchExplainer`** (`kpa/scoring/llm_explainer.py`) — uses `google.genai` to call the configured Gemini text model. Surfaced-only LLM call: if `ctx.total < ctx.threshold`, returns the templated explanation without calling Gemini. Any failure (provider exception, empty response, malformed JSON, non-dict JSON) logs `explain.llm-failed` (warning, `exc_info=True`) and falls back to templated. `explain()` **never raises** — scoring is never failed or retried by the explainer.
- **Selection via env.** `KPA_MATCH_EXPLAINER` is `"llm"` (default — Gemini) or `"templated"` (deterministic fallback used in dev when `KPA_GEMINI_API_KEY` is missing). The default was flipped from `"templated"` to `"llm"` once open decision #1 (LLM provider) resolved to Gemini. `KPA_MATCH_EXPLAINER_MODEL` (default `"gemini-2.5-flash"`) is read only when the LLM branch is selected. `get_match_explainer()` in `celery_app.py` is the lazy-singleton factory (mirrors `get_embedding_provider` / `get_email_channel`). The LLM impl falls back to templated on any Gemini failure (see `GeminiMatchExplainer` bullet above), so an outage of the provider never fails scoring.
- **`kpa/scoring/explainer.py` does NOT import `google.genai`.** The LLM impl lives in a separate module so the templated path never pays the genai import cost (mirrors the embeddings package's `__init__` not re-exporting `GeminiEmbeddingProvider`). The factory's LLM branch does `from google import genai` lazily.
- **`patched_match_explainer` fixture patches three modules + the `_match_explainer` cache.** Strictly only the `celery_app.get_match_explainer` + `_match_explainer` patches are load-bearing today, because both score workers import `get_match_explainer` inside the function body (each call re-reads from `sys.modules['kpa.workers.celery_app']`). The `score_applicant` / `score_job` module-level patches (with `raising=False`) are defensive — if a future refactor hoists the import to module top, the fixture keeps working without changes. Mirrors the `patched_embedding_provider` shape so the two stay analogous.
- **The score worker's Txn 1 already loads `Employer.name`** alongside `Job` + `JobEmbedding` (added when the templated explainer first shipped). The LLM impl uses the same context.
- **`GENERATOR_VERSION` bumps when the templates or LLM prompt change semantically.** Reviewers should flag template/prompt edits as version-bump candidates. `LLM_GENERATOR_VERSION = "1"` is the initial release.
- **First text-gen call in the repo.** If the `google-genai` 1.x structured-output API changes shape, only `kpa/scoring/llm_explainer.py` needs to change; the Protocol, the factory, and the workers are insulated.

### Notifications outbox

- **Outbox pattern.** Writers insert `notifications` rows on the triggering event (e.g., `apply`); a `sweep_notifications` Celery beat task claims rows via `SELECT FOR UPDATE SKIP LOCKED` and dispatches to channel adapters. Idempotency is per `notifications.id` — the row is the unit of work.
- **Email channel is `LoggingEmailChannel` stub.** It logs a structured `email.sent` event to stdout and marks the row `sent`. The real SES adapter is deferred until the deploy target is picked (P5). To swap: implement `EmailChannel` Protocol in `kpa/integrations/email/ses.py` and set `KPA_EMAIL_CHANNEL=ses`.
- **Retry / backoff.** `sweep_notifications` retries up to 5 times. Back-off: `min(60 * 2^(attempt - 1), 3600) + jitter(0, 30)` seconds, written to `send_after`. On final exhaustion the row is marked `failed` and left for admin triage.
- **Apply trigger inserts TWO rows.** A successful 201 from `POST /v1/jobs/{id}/apply` inserts one `email` row and one `in_app` row. Idempotent re-applies (already `applied`) and re-applies after withdraw (`withdrawn → applied`) do **not** insert new notification rows.
- **`GET /v1/notifications` excludes `FAILED` rows.** The inbox endpoint filters `status != 'failed'`. Surfacing admin-only failure state to users is deferred; if needed, a staff endpoint will expose it separately.
- **Per-user channel preferences / consents deferred to P4.** Currently all channels are enabled for all users. When P4 lands, the sweep must gate dispatch on the user's consent record.

### Applications + saved jobs routes

- **Re-apply after withdraw UPDATEs the same row back to `status='applied'`** (approach b from the design doc). The partial-UNIQUE index is on `(applicant_id, job_id) WHERE deleted_at IS NULL`. Withdrawal does NOT soft-delete the row — it changes status. A second INSERT against the same live unique pair would fail; instead the route UPDATEs the existing row and refreshes `created_at`. This preserves row id stability (cursor format `{created_at, application_id}` stays valid across re-applies).
- **PATCH only accepts `applied → withdrawn`.** Body must be `{"status": "withdrawn"}`. Any other target value returns `400 invalid_transition`. Re-withdrawing an already-withdrawn application is a **200 no-op** (not 409, not 400). Uniform 404 across unknown and other-user application ids — distinguishing them leaks ownership.
- **Save is `POST = create (idempotent), DELETE = soft-delete (idempotent)`.** Re-saving after an unsave creates a fresh row (not the same row restored). DELETE returns 204 regardless of prior state. Re-saving a currently-live saved_job returns the existing row (200, not 201).
- **Saved-list keeps closed-job entries.** `GET /v1/saved` does NOT filter on `jobs.status = 'open'`. A job can close after saving; the saved entry remains visible so the applicant knows the role closed. Apply and save at *creation* time do enforce `status='open'` — they return 404 for closed/soft-deleted jobs.
- **`source` is free-form `VARCHAR(32)`**, default `'feed'`. No server-side enum enforcement yet. Promote to a DB enum when the set of valid values stabilizes (tracked as follow-up). Arbitrary strings have no XSS risk (JSON output only) but will show up raw in dashboards.

### Recruiter routes (jobs CRUD + employer self-service)

- **`POST /v1/employers` is the ONLY role-elevation path.** Creates employer + `employer_users(role='owner')` link + bounded UPDATE `users.role` from APPLICANT to RECRUITER (the WHERE clause includes `role=APPLICANT` so it never demotes ADMIN, and is a no-op for an existing RECRUITER). One-way in this slice — there is no demotion endpoint.
- **Employer name dedup via partial-UNIQUE `ix_employers_name_norm_live`.** 409 `employer_name_taken` on a duplicate normalized name (`lower(collapse_ws(strip(name)))`). No auto-join — admin merge / invite flow is deferred to P4.
- **Unique-violation detection walks the `__cause__` chain.** SQLAlchemy's `IntegrityError.orig` is `AsyncAdapt_asyncpg_dbapi.IntegrityError` (the DBAPI wrapper); the raw `asyncpg.UniqueViolationError` (which carries `constraint_name`) is at `e.orig.__cause__`. The route does `cause = getattr(orig, "__cause__", None) or orig`, then checks `type(cause).__name__ == "UniqueViolationError"`. Avoids importing asyncpg (no `py.typed` marker, would force a mypy override). Also calls `await session.rollback()` on both branches — savepoint is broken after the IntegrityError.
- **`_load_recruiter_job(job_id, user, session)`** is the canonical "load job for the recruiter" helper used by `PATCH`, `DELETE`, and `GET /jobs/{id}/applicants`. It calls `_require_recruiter` first (so applicants get 403 BEFORE any id lookup), then joins `EmployerUser` to enforce ownership and filter soft-deleted, returning a uniform 404 for unknown / wrong-employer / soft-deleted. Do NOT re-implement; reuse it.
- **`DELETE /v1/jobs/{id}` returns 404 on the second call (not 204-idempotent).** This deviates from the spec wording but follows the codebase's uniform-404 stance: `_load_recruiter_job` excludes soft-deleted rows, so a second DELETE from any recruiter sees "not found." To switch to 204-idempotency, bypass `_load_recruiter_job` and short-circuit on `deleted_at IS NOT NULL`.
- **`PATCH /v1/jobs/{id}` re-embeds ONLY when a content field changes.** `_EMBED_TRIGGERING_FIELDS = {title, description, locations, min_exp_years, max_exp_years, ctc_min, ctc_max}`. A status-only PATCH does NOT dispatch `embed_job`. A combined patch dispatches once. Status validation goes through Pydantic `Literal["open","closed"]` — unknown values surface as 422 (not 400 `invalid_transition`); this matches the rest of the codebase's validation surface.
- **Deferred `embed_job` import inside the route function**, mirroring `routes/resumes.py`'s `parse_resume` pattern. Module-level `from kpa.workers.tasks.embed_job import embed_job` triggers `Settings()` instantiation via `celery_app.py` at module load, which fails when env vars aren't yet set (test collection). Keep the dispatch wrapped in a broad `except Exception` + `_log.warning("embed.dispatch-failed", ...)` — broker outage MUST NOT fail the request.
- **`/v1/jobs/me` MUST be declared BEFORE `/v1/jobs/{job_id}`** in the route file. FastAPI matches in declaration order; otherwise "me" gets parsed as a (failing) UUID. There's a NOTE comment above the route — don't reorder.
- **`/v1/jobs/me` counts via `func.count(distinct(case((...), X.id)))`** — the CASE/DISTINCT combo emulates `COUNT(... FILTER (WHERE ...))` without depending on dialect-specific FILTER syntax. `applicant_count` = applications with `status='applied' AND deleted_at IS NULL`; `surfaced_match_count` = matches with `surfaced_at IS NOT NULL AND deleted_at IS NULL`. Both are computed in a single GROUP BY query per page — no N+1.
- **`JobRead.employer_verified`** is a required field on the shared `JobRead` DTO (`routes/feed.py`). Every caller of `JobRead` MUST construct via `JobRead.from_job_and_employer(job, employer)` — that helper is the only legitimate construction point. Callers needing only `Job` (without `Employer`) must fetch the employer row. Touched callers: `routes/jobs.py:create_job`, `routes/jobs.py:patch_job`, `routes/jobs.py:get_job_detail`, `routes/jobs.py:list_my_jobs`, `routes/feed.py:get_feed`, `routes/saved_jobs.py:list_saved_jobs`, `routes/applications.py:list_applications`.
- **`GET /v1/jobs/{id}/applicants` uses `Applicant.full_name`** for `display_name` (the `User` model has no `display_name` column). Joins `Application → Applicant → User` to get the email. Cursor encodes `{created_at, application_id}` (mirrors `/v1/jobs/me` but on `Application.created_at`).
- **`GET /v1/applications/{id}/resume` is the recruiter-side download.** RBAC: caller must be a RECRUITER at the employer that owns the application's job. Single JOIN query (`Application → Job → EmployerUser → Resume[outer]`) — if the join fails on any leg, uniform 404. Latest resume via `ORDER BY Resume.created_at DESC`. Emits `recruiter.resume-accessed` structured log with `{request_id, recruiter_user_id, employer_id, application_id, applicant_id, resume_id}` — this is the **audit-trail seed** for P4 DPDP; an `audit_logs` table is deferred. Tests assert the log via `structlog.testing.capture_logs()`.
- **Unverified employers' jobs still surface in `/v1/feed`.** No admin gating yet. `JobRead.employer_verified` is exposed so a future "verified-only" feed filter is a one-line change.

### Employer team management (R4 — members + invites)

Full design: spec `2026-06-06-recruiter-employer-experience-design.md` §5. Non-obvious code-invariants:

- **Role is derived from membership, never set directly.** `kpa/employers/membership.py`: `flip_to_recruiter` (any join → APPLICANT→RECRUITER, never ADMIN) and `maybe_demote_to_applicant` (zero live memberships left → RECRUITER→APPLICANT, returns the demoted flag). The ONLY writers of `users.role` in the team flow. `current_user` re-fetches per request, so a removed recruiter loses access within the access-TTL — no token revocation.
- **RBAC helpers in `auth/dependencies.py`:** `_require_employer_member` (uniform 404 if no live link — don't leak existence) and `_require_employer_owner` (404 if not a member, then 403 `not_an_owner` — membership already proven so the 403 leaks nothing). Owner mutates; any member reads. Called BEFORE any resource lookup.
- **Last-owner guard is lock-based:** `_count_live_owners(session, employer_id, lock=True)` does `SELECT … FOR UPDATE` on the owner rows (aggregates can't carry FOR UPDATE in PG, so it locks rows + counts in Python). Without the lock two concurrent owner removals both pass the `<=1` check → zero owners. Used in the demote (PATCH role) and remove (DELETE) guards.
- **Membership inserts catch `IntegrityError → 409 already_a_member`** (concurrent check-then-insert against the partial-UNIQUE `ix_employer_users_pair_live`), mirroring `create_employer`. Applies to `add_member` and `accept_invite`.
- **Invite outbox is best-effort + existing-user-only.** `POST …/invites` inserts a `Notification` (kind `employer_invite`) ONLY when the email maps to an existing user (`notifications.user_id` is NOT NULL). Brand-new invitees discover via `GET /v1/me/invites`; real email/SES is deferred. Don't try to outbox for unknown emails.
- **Invitee-facing `routes/invites.py` authorizes by email match** (`invite.email == current_user.email`), NOT membership. Lazy expiry: a `pending` invite past `expires_at` flips to `expired` on read/accept (410 on accept). Decline reuses the `revoked` status (no separate enum value). Accept verifies the employer is still live.
- **`employer_invites.email` is PII** — it IS covered by DSR: export adds `received_invites` (addressed to the user) + `sent_invites` (owner-created); delete erases invites where `email == user.email OR accepted_user_id == user.id`. **Any new PII *table* (not just column) must be added to `kpa/dsr/__init__.py` export + `kpa/dsr/deleter.py` graph + the `test_user_export_top_level_fields` contract pin.**
- **Reserved `employer.*` audit slugs** (all now used): `member_added`, `member_role_changed`, `member_removed` (context `demoted_to_applicant`), `invite_created`, `invite_accepted`, `invite_revoked` (decline reuses revoked with `declined_by_invitee`).
- **No self-leave endpoint** — direct-add (spec-intended) flips an applicant to recruiter with no acceptance; removing yourself requires another owner. Tracked follow-up.

> **NOTE:** this file is ~60k, well over the ~40k lean budget (loaded every session; silent truncation past the limit). A trim pass — pushing operational detail to READMEs and rationale to specs — is overdue.

## Test patterns

### Two-conftest design

`tests/conftest.py` provides a `client` fixture that uses a **fake DSN** (`postgresql+asyncpg://u:p@h:5432/d`) — the app boots but no DB connection is opened. This is what unit tests use; they never touch Postgres.

`tests/integration/conftest.py` shadows that fixture with a real-Postgres version that uses savepoint-based rollback isolation: each test gets a session bound to a connection that holds an outer transaction; `join_transaction_mode="create_savepoint"` lets test code call `await session.commit()` without escaping the outer txn; teardown rolls back. **No truncation between tests.** The migrations run once per test session.

A `pytestmark = pytest.mark.integration` at the top of the integration conftest tags every test under that directory. There's no need to mark individual integration tests.

### Three HTTP test clients, not two

The integration conftest (`tests/integration/conftest.py`) provides three HTTP clients:

- `client` (sync `TestClient`) — separate event loop. Only safe for routes that don't share the `session` fixture's asyncpg connection. TestClient runs the ASGI app via Starlette's blocking portal which conflicts with asyncpg connections bound to the pytest-asyncio test loop.
- `async_client` (`httpx.AsyncClient` + `ASGITransport`) — shares the test loop; overrides `get_session` to reuse the test's session (savepoint isolation). **Default choice** when a test exercises both an HTTP endpoint and `session.execute(...)`.
- `concurrent_async_client` — async, but uses the app's **real** connection pool (no `get_session` override). Required for tests that exercise `SELECT … FOR UPDATE` semantics — e.g., the refresh-token reuse-detection tests — because the shared-session override serialises everything through one connection and breaks the test premise. Trades savepoint isolation for explicit `TRUNCATE ... RESTART IDENTITY CASCADE` in teardown.

### NullPool for the integration engine

The per-test engine in the integration conftest uses `poolclass=NullPool` to force a fresh asyncpg connection bound to the current test's event loop. Without it, asyncpg connections from earlier tests get reused and raise the loop-mismatch error. Keep it.

## Conventions worth knowing

- **uv only.** Don't `pip install` — it bypasses `uv.lock` and breaks reproducibility.
- **No Docker for MVP.** Local Postgres is Homebrew (`postgresql@16`). Containers re-enter at the deploy-target step (spec §11.1 / §13 P5).
- **Hand-written migrations.** Alembic autogenerate is intentionally off until the model surface gets bigger (~10 tables). Edit the generated revision file before running `upgrade head`.
- **Migrations live in `src/kpa/db/migrations/versions/`** and are excluded from mypy.
- **structlog only.** No `print`, no `logging.getLogger(...).info(f"...")`. Use `structlog.get_logger(__name__)` and pass context as kwargs. Output is plain key=value by default; flip `KPA_LOG_FORMAT=json` for prod (Fluent Bit → Elasticsearch).
- **All handlers `async def`.** Per spec §4.2.
- **Versioned routes mount under `/v1`**, except `/health` and `/ready` which are bare so ALB/k8s probes can hit them directly.

## Source-of-truth files when in doubt

- API conventions and roadmap → `IMPLEMENTATION_SPEC.md` (§4 backend, §5 data model, §6 pipelines incl. §6.1 parse worker, §9.1 auth/identity, §10 API design, §11 infra).
- Product scope → `docs/prd/KPA_Enhanced_BRD_v1_1.pdf`.
- Active per-feature work → `docs/superpowers/plans/` (most recent file by date = current focus); paired design doc in `docs/superpowers/specs/`.

## Flutter app (`app/`)

The applicant-facing iOS + Android + Web client lives in `app/` as a sibling of `api/`. Architecture: `lib/data/` + `lib/presentation/` + `lib/core/` (no separate `domain/` layer). Abstract repository interfaces live next to their concrete impls in `data/<feature>/<repo>_repository.dart` + `<repo>_repository_impl.dart`. State management is Riverpod 4.x with code-gen; HTTP is dio 5.7; routing is go_router 14.6 with `StatefulShellRoute.indexedStack` for the four-tab bottom nav.

### Day-to-day commands

```bash
# from app/
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # after touching @freezed / @riverpod / @JsonSerializable
flutter run -d chrome --dart-define-from-file=.env
flutter test
flutter analyze
dart format lib test
```

### Non-obvious bits

- **Refresh-on-401 interceptor** (`lib/data/api/refresh_on_401_interceptor.dart`) is the single most important piece of code; single-flight via `Completer<String>?` so concurrent 401s never stampede the refresh endpoint. Tests in `test/unit/data/api/refresh_on_401_interceptor_test.dart` are the canonical specification — keep them passing.

- **`AccessTokenHolder`** (`lib/data/api/access_token_holder.dart`) is a mutable singleton bridging dio (below Riverpod's reach) and the rest of the app. Single public setter: `set(String? token)`; `clear()` is `set(null)`. No mirror Riverpod notifier — it was removed when the code reviewer flagged it as dead.

- **`dio_provider` depends on a presentation-layer notifier** (`authStateProvider`) to push `SignedOut` on refresh failure. This is the one documented exception to data→presentation purity. The `auth_repository_impl` previously had a second leak; that one was removed by deleting its dead `emit`/`readState` callbacks.

- **Don't override `validateStatus` on the Dio instance.** An earlier version set `validateStatus: (s) => s < 500` which silently masked 401s and made `RefreshOn401Interceptor` non-functional in production (tests passed because the mock interceptor maps 401→reject explicitly). Default Dio behavior — 4xx/5xx throws DioException — is what the refresh interceptor needs to fire.

- **Refresh interceptor cleanup order:** `_inFlight = null` is set **before** the Completer is `complete()`d, not after. Otherwise a continuation that synchronously re-enters `onError` could attach to a stale completer.

- **Riverpod 4.x codegen** drops the `Notifier` suffix from generated providers — the `AuthStateNotifier` class produces `authStateProvider` (not `authStateNotifierProvider`).

- **No mutation of the feed on apply/save/withdraw/unsave.** Each mutation invalidates the corresponding list controller + the `jobDetailControllerProvider(id)`, never the feed.

- **List screens share `PagedState<T>` + `loadNextPage` helpers** (`lib/presentation/paging/`). Feed/Saved/Applications controllers each have a `typedef XxxState = PagedState<Y>` and delegate `loadMore()` to the shared helper. Don't reinvent the pagination state machine per screen.

- **`loadMore` error path preserves loaded items** via `AsyncValue.error(...).copyWithPrevious(AsyncValue.data(...))` — early implementation wiped the list on page-N failure. `copyWithPrevious` is `@internal` in Riverpod 3+; the `// ignore: invalid_use_of_internal_member` comment in `paging.dart` is load-bearing.

- **Magic strings live in enums or constants.** `JobStatus`, `ApplicationStatus`, `ApplicationSource`, `MatchGenerator` are enums with `@JsonKey(unknownEnumValue: X.unknown)` so a future backend value parses to a sentinel instead of throwing. Error slugs live in `lib/core/error/auth_slugs.dart` (`AuthSlugs.invalidAccessToken` etc.). The HTTP API layer (`*_api.dart`) still uses raw strings for source (the wire format); enums are a repo-and-above concept.

- **DTOs are `@JsonSerializable` plain classes by default; `@freezed` only when `copyWith` is needed.** Only `JobDetailDto` (FakeJobsRepository uses `copyWith`) and `PagedState<T>` (paging helper uses `copyWith`) keep freezed. If you add a new DTO, default to plain `@JsonSerializable`.

- **Per-tab navigation stacks** via `StatefulShellRoute.indexedStack`. `/jobs/:id` is defined as a child route under each of the four tab branches. The 404 path in JobDetail uses `context.pop()` so users return to the tab they came from, not a hardcoded `/feed`.

- **google_fonts and tests:** widget tests must use `ThemeData.light(useMaterial3: true)` rather than `buildTheme()` because the production `buildTheme` triggers a network fetch for Inter that fails in CI/offline test environments. The integration test passes because it doesn't render glyphs that depend on the font.

- **`PackageInfo.fromPlatform()` lives in a `keepAlive: true` provider** (`presentation/profile/package_info_provider.dart`), not in a `FutureBuilder.future:` arg — the latter re-runs the platform-channel call on every screen rebuild. Same lesson applies if you ever wrap another platform-channel async in a widget.

- **`DateFormat` instances are module-static**, not per-cell. `DateFormat.yMMMMd()` parses an ICU pattern on construction; allocating one per ListView cell adds real CPU on long lists.

- **Shared test infra in `test/helpers/`:** `MockInterceptor` (replaces the 6 hand-rolled copies), `fake_repositories.dart` (the six Fake*Repository implementations used by the integration test). Reuse before hand-rolling new test fakes.

- **`--dart-define`, no flavors.** `KPA_API_BASE_URL` and `KPA_GOOGLE_WEB_CLIENT_ID` are required at compile time; `Env.validateOrThrow()` runs in `main()` before `runApp`.

- **Light theme only in v0; dark plumbed but disabled.** `MaterialApp.router(themeMode: ThemeMode.light)`. Flip to `ThemeMode.system` + populate the dark branch of `buildTheme` when dark mode ships.

- **No `dio_smart_retry`, no toast plugin, no analytics, no Sentry.** All deferred to follow-up plans per spec §Non-goals.

- **Google sign-in is two flows: imperative on mobile, rendered-button on web.** Mobile uses `GoogleSignInDataSource.getIdToken()` (`_sdk.signIn()`). Web *cannot* — GIS's `signIn()` returns no `idToken` on web — so it uses `lib/data/auth/google_web_sign_in.dart` (interface + `googleWebSignInProvider`, a `keepAlive` `FutureProvider` that awaits `initialize()` so `renderButton()` has run `init`). The impl is selected by conditional import: `google_web_sign_in_web.dart` (uses `google_sign_in_web/web_only.dart`'s `renderButton()` + `onCurrentUserChanged → idToken`) on web, `google_web_sign_in_stub.dart` everywhere else (so `web_only.dart`'s `dart:js_interop` never reaches mobile/`flutter test`). `SignInScreen` branches on `kIsWeb`: rendered button on web, the existing `FilledButton` on mobile (the widget tests run non-web, so they still find "Continue with Google").
- **`AuthRepositoryImpl.completeWebSignIn(idToken)`** is the web entry to the shared backend exchange (`_exchangeGoogleIdToken`). It lives on the impl, NOT the `AuthRepository` interface, reached via downcast in `sign_in_controller.dart` — same pattern as `refreshAccessTokenForInterceptor` (keeps the interface + its test fakes untouched). `signInWithGoogle()` (mobile) and `completeWebSignIn()` (web) both push `Authenticating` then delegate to `_exchangeGoogleIdToken`.
- **`GoogleSignInDataSourceImpl` constructs `GoogleSignIn` platform-conditionally** (`_defaultSdk()`): `clientId:` on web, `serverClientId:` on mobile. Web construction matters even though web never calls `getIdToken()` — `signOut()` lazily inits the plugin, which would hit the `serverClientId is not supported on Web` assert otherwise.
- **`web/index.template.html`'s `google-signin-client_id` meta tag is now redundant.** The web helper passes `clientId` directly to `GoogleSignIn`, which the plugin prefers over the meta tag — so the README's `sed`-substitute-then-`flutter run -d chrome` step isn't required for auth to work. Running via `flutter run -d web-server --web-port=8080 --dart-define-from-file=.env` is enough.
- **Local web sign-in needs Google Cloud + the API configured for the browser:** (1) `http://localhost:8080` (the pinned web-server port) must be an **Authorized JavaScript origin** on the web OAuth client — propagation can take minutes-to-hours; probe with `curl … /gsi/button` (403→200). (2) The API needs CORS for the browser origin — `KPA_CORS_ALLOW_ORIGINS` (default `http://localhost:8080`) drives the Starlette `CORSMiddleware` mounted in `app_factory.py` after `RequestIdMiddleware`.
- **Privacy screen lives in `presentation/privacy/`.** Single screen combines consent toggles + DSR export + DSR delete navigation. Reserved consent scopes (`whatsapp_notifications`, `sms_notifications`, `profile_visibility_recruiters`, `third_party_sharing_recruiters`) are deliberately HIDDEN — they have no Dart-side gate today; showing four greyed-out toggles is worse than hiding.
- **DSR export uses the system clipboard** in v0 — `Clipboard.setData(ClipboardData(text: envelope))`. Native file-save is deferred to a follow-up so we don't pull in `share_plus` / `path_provider` / Web Blob API behind a conditional import. Document this in the snackbar copy.
- **DSR delete flow is a separate screen** at `/profile/privacy/delete` with a `DELETE_MY_ACCOUNT` text-confirmation guard. Submit button is disabled until the controller's value exactly matches. On success: clear `AccessTokenHolder`, push `SignedOut` (router redirects to `/signin`), one-time snackbar via `deleteSuccessSnackbarProvider`.
- **Turning OFF `email_transactional`** triggers a confirmation dialog because the user is opting out of service-critical email. Other consent toggles flip without confirmation.
- **Recruiter feature lives under `presentation/recruiter/` + `data/jobs/recruiter_*` + `data/employers/team/`.** The Team tab (`recruiter_employer_screen.dart`) derives owner-ness from the caller's own roster row via `SignedIn.userId` (UI gating is defense-in-depth; backend is authoritative) and HIDES change-role/remove on your own row. The invitee `PendingInvitesScreen` (`/profile/invites`, applicant-only Profile entry) accepts an invite then calls `refreshSession()` — the role flips and `roleAwareRedirect` (`/profile/*` is applicant-shell) moves the user into the recruiter shell. **`accept()` treats `acceptInvite` as the success boundary**: a failed post-accept `refreshSession` is best-effort (swallowed), because re-accepting 404s. Deep-link `/recruiter/jobs/:id/edit` with null `extra` resolves the job from the include-closed list via `EditJobResolver` (don't render a blank create form). Dashboard sums `listMyJobs(status:'closed')` (open+closed) client-side.
