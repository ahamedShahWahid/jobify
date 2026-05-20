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

### Don't reuse models as response schemas

Per spec §4.2 and the comment in `db/models.py`: SQLAlchemy models are never response models. Define `*Read` / `*Create` / `*Update` Pydantic v2 models in the route module (see `ResumeRead` with `ConfigDict(from_attributes=True)` for the conversion pattern).

### Auth + JWT invariants

- `current_user` (`auth/dependencies.py`) re-fetches the user row on every call. A user soft-deleted 30s ago is locked out within the access TTL (≤10 min), not the refresh TTL. Don't add caching here.
- **Sign-in always provisions `role=APPLICANT`** (`auth/service.py:_upsert_identity`). Tests needing a recruiter/admin must create the row directly via `session` and mint a token with `mint_access_token` — there is no "sign in as recruiter" path. See `tests/integration/test_resumes_auth.py` for the canonical pattern.
- 401 slugs are deliberately generic. `invalid_access_token` never differentiates signature failures from claim failures — it's a timing-oracle countermeasure baked into `tokens.py:AccessTokenError`. Don't add more specific slugs.
- Refresh rotates on every use. Re-presenting an already-rotated token triggers full family revocation via `_revoke_family` ("reuse detected"). The bulk UPDATE relies on Postgres READ COMMITTED + EvalPlanQual semantics to catch concurrent legitimate rotations — don't switch it to a row-at-a-time loop.
- JWT secret must be ≥32 bytes; HS256, issuer `kpa-api`, `jti` required. The 30s `iat` skew tolerance is checked manually because PyJWT's leeway would relax `exp` too.

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
