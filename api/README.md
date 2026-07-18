# Jobify API

FastAPI service for the Jobify platform (`jobify_api` package). Part of the `core/api/worker` uv workspace.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) 0.5+
- Postgres 16 (Homebrew — see [Database](#database) for setup)
- Redis (for the Celery worker — see [Worker](#worker))

Docker is **not** required for MVP work. Containerization rejoins the project at the deploy-target step (see `IMPLEMENTATION_SPEC.md` §11.1 / §13 P5).

## First-time setup

```bash
# From repo root
uv sync
cp .env.example .env   # adjust as needed (root .env — not inside api/)
```

Then set up Postgres — see [Database](#database).

## Run locally

All commands run from the **repo root** (not from `api/`). The `.env` file lives at the repo root.

```bash
uv run --env-file=.env uvicorn jobify_api.main:app --reload --port 8000
```

- `--reload` watches source dirs and restarts on code changes.
- `--port 8000` is the convention; pick anything free if 8000 is in use.

Inline env vars (for one-off overrides):

```bash
JOBIFY_ENV=local JOBIFY_SERVICE_NAME=jobify-api \
  uv run uvicorn jobify_api.main:app --reload --port 8000
```

### Verify it's up

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Expected:

```json
{
  "status": "ok",
  "service": "jobify-api",
  "version": "0.1.0",
  "env": "local"
}
```

Other useful URLs:

- `http://127.0.0.1:8000/docs` — Swagger UI
- `http://127.0.0.1:8000/redoc` — ReDoc
- `http://127.0.0.1:8000/openapi.json` — raw OpenAPI schema

Every response carries an `X-Request-Id` header — the log correlation handle.

## Database

Local dev runs Postgres 16 directly via Homebrew — no Docker.

### First-time setup (one-time, per machine)

```bash
brew install postgresql@16
brew services start postgresql@16

psql -d postgres <<'SQL'
CREATE ROLE jobify WITH LOGIN PASSWORD 'jobify' CREATEDB;
CREATE DATABASE jobify OWNER jobify;
CREATE DATABASE jobify_test OWNER jobify;
SQL

cd core && uv run alembic upgrade head   # applies migrations to the dev DB
```

The dev connection string lives in `.env` (repo root):

```
JOBIFY_DB_URL=postgresql+asyncpg://jobify:jobify@localhost:5432/jobify
```

Integration tests connect to `jobify_test` by default; override with `JOBIFY_TEST_DB_URL` if needed.

### Migrations (Alembic)

Alembic config lives in `core/`. All migration commands run from `core/`:

```bash
cd core && uv run alembic upgrade head
cd core && uv run alembic revision -m "describe the change"
# Edit the generated file under core/src/jobify/db/migrations/versions/
cd core && uv run alembic upgrade head
```

Hand-written migrations — autogenerate is intentionally off.

### Reset the dev database

```bash
psql -d postgres -c "DROP DATABASE jobify;"
psql -d postgres -c "CREATE DATABASE jobify OWNER jobify;"
cd core && uv run alembic upgrade head
```

### pgvector (required for embedding worker)

Homebrew bottles pgvector only for PG17/18. For Postgres 16, build from source:

```bash
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make install
```

Create the extension as a Postgres superuser:

```bash
psql -U postgres -d jobify -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -U postgres -d jobify_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Verify readiness

```bash
curl -s http://127.0.0.1:8000/ready | python -m json.tool
```

## Worker

Resume parse, embedding, scoring, and notification tasks run on Celery + Redis. See `worker/README.md` for the run command and queue details.

### Redis first-time setup

```bash
brew install redis
brew services start redis
```

The connection string in `.env` (repo root):

```
JOBIFY_REDIS_URL=redis://localhost:6379/0
```

### Skipping the worker for tests

Integration tests use eager Celery execution and explicitly drain durable outbox rows, so Redis is not required during `pytest`.

## Seeding demo data

```bash
# Apply (idempotent — safe to re-run)
uv run --env-file=.env jobify-seed-jobs

# Validate the JSON only; nothing written
uv run --env-file=.env jobify-seed-jobs --dry-run
```

The canonical fixture lives at `core/data/sample_jobs.json` (10 employers, 27 jobs).
Email templates live at `core/emails/`.

## Tests

All test commands run from the **repo root**:

```bash
# Unit tests (no DB required):
uv run pytest -v -m "not integration and not eval"

# Parse F1 quality gate (no DB):
uv run pytest -v -s -m eval

# Integration tests (require local Postgres + jobify_test database):
uv run pytest -v -m integration

# Full suite:
uv run pytest -v
```

Tests live in `tests/` at repo root. The integration conftest uses `JOBIFY_TEST_DB_URL` (falls back to `postgresql+asyncpg://jobify:jobify@localhost:5432/jobify_test`).

## Lint, format, type-check

Run from repo root:

```bash
uv run ruff check core/src api/src worker/src tests
uv run ruff format core/src api/src worker/src tests
uv run mypy
```

## Configuration

All settings are read from environment variables prefixed `JOBIFY_`. The `.env` file lives at the **repo root** (not inside `api/`).

| Variable           | Required | Default | Purpose                         |
| ------------------ | -------- | ------- | ------------------------------- |
| `JOBIFY_ENV`          | yes      | —       | `local` \| `dev` \| `staging` \| `prod` |
| `JOBIFY_SERVICE_NAME` | yes      | —       | Reported in `/health`           |
| `JOBIFY_DB_URL`       | yes      | —       | SQLAlchemy DSN; must use `postgresql+asyncpg://` |
| `JOBIFY_DB_POOL_SIZE` | no | `10` | Persistent API database connections per process |
| `JOBIFY_DB_MAX_OVERFLOW` | no | `10` | Temporary connections above pool size |
| `JOBIFY_DB_POOL_TIMEOUT_SECONDS` | no | `30` | Wait for a pooled connection |
| `JOBIFY_DB_POOL_RECYCLE_SECONDS` | no | `1800` | Recycle pooled connections |
| `JOBIFY_DB_COMMAND_TIMEOUT_SECONDS` | no | `30` | asyncpg command timeout |
| `JOBIFY_STORAGE_BACKEND` | no | `local` | `local` filesystem or `s3` object storage. |
| `JOBIFY_STORAGE_ROOT` | no       | `var/uploads` | Filesystem root when storage backend is `local`. |
| `JOBIFY_S3_BUCKET` | for S3 | — | Object-storage bucket. |
| `JOBIFY_S3_PREFIX` | no | empty | Object-key prefix within the bucket. |
| `JOBIFY_AWS_REGION` | no | SDK default | AWS region for S3/SES. |
| `JOBIFY_AWS_ENDPOINT_URL` | no | AWS | S3-compatible endpoint override. |
| `JOBIFY_PROVIDER_CONNECT_TIMEOUT_SECONDS` | no | `5` | S3/provider connect deadline. |
| `JOBIFY_PROVIDER_READ_TIMEOUT_SECONDS` | no | `30` | S3/provider read deadline. |
| `JOBIFY_MAX_UPLOAD_BYTES` | no   | `10485760` | Max bytes per upload (10 MiB). |
| `JOBIFY_ALLOWED_RESUME_CONTENT_TYPES` | no | (pdf, doc, docx) | Comma-separated content-type whitelist. |
| `JOBIFY_LOG_LEVEL`    | no       | `INFO`  | Stdlib log level                |
| `JOBIFY_LOG_FORMAT`   | no       | `text`  | `text` (key=value) or `json`    |
| `JOBIFY_JWT_SECRET`   | yes      | —       | HS256 signing secret; min 32 bytes |
| `JOBIFY_JWT_ACCESS_TTL_SECONDS`  | no | `600`     | Access token lifetime (10 min) |
| `JOBIFY_JWT_REFRESH_TTL_SECONDS` | no | `2592000` | Refresh token lifetime (30 d) |
| `JOBIFY_GOOGLE_OAUTH_CLIENT_IDS` | yes | —        | CSV of Google Client IDs       |
| `JOBIFY_GOOGLE_JWKS_URL`         | no | `https://www.googleapis.com/oauth2/v3/certs` | Override for tests |
| `JOBIFY_GOOGLE_JWKS_CACHE_TTL_SECONDS` | no | `3600` | JWKS in-process cache TTL |
| `JOBIFY_AUTH_REQUIRE_EMAIL_VERIFIED`   | no | `false` | Reject unverified Google sign-ins |
| `JOBIFY_AUTH_GOOGLE_RATE_LIMIT_PER_MINUTE` | no | `10` | Google sign-in attempts per client IP per minute |
| `JOBIFY_AUTH_REFRESH_RATE_LIMIT_PER_MINUTE` | no | `30` | Refresh attempts per IP/token fingerprint per minute |
| `JOBIFY_CORS_ALLOW_ORIGINS` | no | `http://localhost:8080` | Comma-separated list of allowed CORS origins (web frontend). |
| `JOBIFY_REDIS_URL`    | yes      | —       | Redis for API rate limits and readiness. |
| `JOBIFY_METRICS_BEARER_TOKEN` | staging/prod | — | Bearer token protecting `/metrics` |

The API refuses to boot if required variables are missing or invalid. Worker-only
Gemini, email, lease, batch, and Celery settings are documented in `worker/README.md`.

## Auth

```
POST   /v1/auth/oauth/google          # Google ID token → access + refresh
POST   /v1/auth/refresh               # rotate refresh; new access + refresh
POST   /v1/auth/logout                # revoke refresh (idempotent 204)
GET    /v1/me                         # current user + applicant payload
```

The Flutter app obtains a Google ID token and POSTs it to `/v1/auth/oauth/google`. The backend verifies against Google's JWKS, upserts the user, and mints an HS256 access JWT (10 min) plus an opaque rotating refresh token (30 d, sha256-hashed at rest).

Refresh tokens rotate on every use. Reuse of a rotated token triggers full family revocation.

### Web Google sign-in (Flutter web)

The web client uses the GIS button flow (not the imperative `signIn()` call). The web OAuth client must list the dev origin in **Authorized JavaScript origins** (e.g. `http://localhost:8080`). Propagation check:

```bash
curl -s -o /dev/null -w '%{http_code}' \
  -H 'Origin: http://localhost:8080' \
  'https://accounts.google.com/gsi/button?client_id=<id>&is_fedcm_supported=true'
```

Returns 200 when the origin is live. Also add `http://localhost:8080` to `JOBIFY_CORS_ALLOW_ORIGINS`.

## Project layout

```
repo root/
├── pyproject.toml        # uv workspace (members: core, api, worker)
├── tests/                # all tests (unit + integration + eval)
├── .env                  # JOBIFY_* vars (gitignored)
├── core/
│   ├── alembic.ini
│   ├── emails/           # HTML email templates
│   ├── data/             # sample_jobs.json, parse_eval/
│   └── src/jobify/       # domain package: db, integrations, scoring, outbox, …
├── api/
│   └── src/jobify_api/   # FastAPI service: app_factory, routes, auth, middleware, …
└── worker/
    └── src/jobify_worker/ # Celery tasks: parse, embed, score, sweep_notifications
```
