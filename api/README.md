# KPA API

FastAPI service for the Khan Placement Agency platform. This directory contains the backend foundations, DB layer, and the resume upload data plane. Auth, parsing, and matching code land in follow-on plans.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) 0.5+
- Postgres 16 (Homebrew — see [Database](#database) for setup)

Docker is **not** required for MVP work. Containerization rejoins the project at the deploy-target step (see `IMPLEMENTATION_SPEC.md` §11.1 / §13 P5).

## First-time setup

```bash
cd api
uv sync
cp .env.example .env   # adjust as needed
```

Then set up Postgres — see [Database](#database).

## Run locally

The service reads its config from environment variables (all prefixed `KPA_`).
The easiest path is to keep them in `.env` (created in First-time setup above)
and let `uv` load it:

```bash
uv run --env-file=.env uvicorn kpa.main:app --reload --port 8000
```

- `--reload` watches `src/` and restarts the server on code changes. Drop it
  for production-style runs.
- `--port 8000` is the convention; pick anything free if 8000 is in use.

If you'd rather pass vars inline (e.g., CI, one-off overrides), skip `.env`:

```bash
KPA_ENV=local KPA_SERVICE_NAME=kpa-api \
  uv run uvicorn kpa.main:app --reload --port 8000
```

### Verify it's up

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Expected response:

```json
{
  "status": "ok",
  "service": "kpa-api",
  "version": "0.1.0",
  "env": "local"
}
```

Other useful URLs while the server is running:

- `http://127.0.0.1:8000/docs` — Swagger UI (interactive API docs)
- `http://127.0.0.1:8000/redoc` — ReDoc (alternative docs view)
- `http://127.0.0.1:8000/openapi.json` — raw OpenAPI schema

Every response (including errors) carries an `X-Request-Id` header — that's
the correlation handle that shows up in the structured logs, so grep for it
when chasing a request through the system.

Stop the server with `Ctrl-C`.

## Database

Local dev runs Postgres 16 directly via Homebrew — no Docker. CI runs the same Postgres as a service container.

### First-time setup (one-time, per machine)

```bash
brew install postgresql@16
brew services start postgresql@16

# Create the role and the two databases (dev + integration tests).
psql -d postgres <<'SQL'
CREATE ROLE kpa WITH LOGIN PASSWORD 'kpa' CREATEDB;
CREATE DATABASE kpa OWNER kpa;
CREATE DATABASE kpa_test OWNER kpa;
SQL

uv run alembic upgrade head         # applies migrations to the dev DB
```

The dev connection string lives in `.env`:

```
KPA_DB_URL=postgresql+asyncpg://kpa:kpa@localhost:5432/kpa
```

Integration tests connect to `kpa_test` by default; override with `KPA_TEST_DB_URL` if your local Postgres isn't on `localhost:5432`.

### Reset the dev database

```bash
psql -d postgres -c "DROP DATABASE kpa;"
psql -d postgres -c "CREATE DATABASE kpa OWNER kpa;"
uv run alembic upgrade head
```

The integration test DB stays clean across runs (savepoint rollback per test), so you rarely need to reset it.

### pgvector (required for embedding worker)

The embedding worker uses a `vector(1536)` column on `applicant_embeddings`. Local Postgres needs the `pgvector` extension installed at the OS level.

Homebrew currently bottles pgvector only for PG17/18. For Postgres 16 (the project's pinned version), build from source:

```bash
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make install
```

Then create the extension as a Postgres superuser (preferred — keeps the `kpa` role at normal privilege):

```bash
# Run as a superuser (e.g. the default 'postgres' role):
psql -U postgres -d kpa -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -U postgres -d kpa_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

If you don't have a separate superuser role set up locally, the quickest fallback is to temporarily grant superuser to `kpa` so the Alembic migration can create the extension itself:

```bash
# dev only — revert after migrations run if desired
psql -d postgres -c "ALTER ROLE kpa SUPERUSER;"
psql -d kpa -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -d kpa_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

The Alembic migration `0004_applicant_embeddings.py` runs `CREATE EXTENSION IF NOT EXISTS vector` idempotently as the first step of `upgrade()`.

### Generate a new migration

```bash
uv run alembic revision -m "describe the change"
# Edit the generated file under src/kpa/db/migrations/versions/.
uv run alembic upgrade head
```

Autogeneration (`--autogenerate`) is intentionally not the default workflow yet — hand-written migrations keep schema changes explicit while the model surface is small. Revisit once the table count grows past ~10.

### Verify readiness

```bash
curl -s http://127.0.0.1:8000/ready | python -m json.tool
```

`/ready` returns 200 when Postgres responds to `SELECT 1`, 503 otherwise. Use it for load-balancer readiness checks; use `/health` (no DB) for liveness.

## Redis (for the parse worker)

The resume parse pipeline runs on Celery + Redis. Local dev uses Homebrew Redis on the default port.

### First-time setup

```bash
brew install redis
brew services start redis
```

Verify it's up:

```bash
redis-cli ping     # → PONG
```

The connection string lives in `.env`:

```
KPA_REDIS_URL=redis://localhost:6379/0
```

### Run the parse worker

In a second terminal (uvicorn keeps running in the first):

```bash
cd api
uv run --env-file=.env celery -A kpa.workers.celery_app worker \
    --pool=solo --concurrency=1 -Q parse,embed --loglevel=info
```

- `--pool=solo`: single-concurrency. The MVP pattern; switch to `--pool=prefork` later when load justifies parallelism.
- `-Q parse,embed`: consume from both the `parse` queue (resume parsing) and the `embed` queue (Gemini embedding). Run a second worker pinned to `-Q embed` if you want to isolate queue consumption. Future `score`/`notify` queues land in their own plans.

Upload a resume in the first terminal; the worker logs `parse.complete` when it's done. Poll `GET /v1/applicants/me/resumes/{rid}` (with the same Bearer token used for the upload) to see `parse_status` transition.

### Skipping the worker for tests

Tests use Celery eager mode (set via `KPA_CELERY_TASK_ALWAYS_EAGER=true` in test fixtures) so `.delay()` runs the task body inline — no Redis required during `pytest`. Production never sets this flag.

## Resume uploads

Two endpoints, both scoped to the caller's own applicant record:

```
POST   /v1/applicants/me/resumes
GET    /v1/applicants/me/resumes/{resume_id}
```

POST accepts `multipart/form-data` with one field `file`. Content-type is checked against `KPA_ALLOWED_RESUME_CONTENT_TYPES`; size against `KPA_MAX_UPLOAD_BYTES`. The file is persisted under `KPA_STORAGE_ROOT` (gitignored `var/` by default); the resume row in `kpa.resumes` lands with `parse_status=pending`. Parsing is a later plan.

Both routes require an `Authorization: Bearer <access_jwt>` header — the applicant id is derived from the access token (via the `current_user` dependency), not from the URL. Expect `401` for a missing or invalid token (or a soft-deleted user), `403 not_an_applicant` for recruiter/admin roles, and a uniform `404` for unknown or other-user resume ids. Size violations return `413`; disallowed content-types return `415`. Obtain the access token via the Google OAuth sign-in endpoint documented in [Auth](#auth) below.

Quick test from the shell once the server is running:

```bash
ACCESS=...   # access JWT from POST /v1/auth/oauth/google — see Auth below
curl -s -X POST "http://127.0.0.1:8000/v1/applicants/me/resumes" \
    -H "Authorization: Bearer $ACCESS" \
    -F "file=@/path/to/cv.pdf" | python -m json.tool
```

### Run with JSON logs (prod-style)

For Fluent Bit / Elasticsearch compatibility, flip the log format:

```bash
KPA_LOG_FORMAT=json uv run --env-file=.env uvicorn kpa.main:app --port 8000
```

(Inline env vars override anything in `.env`, so this works even with the
default `KPA_LOG_FORMAT=text` in the file.)

## Tests

Unit tests (no DB required):

```bash
uv run pytest -v -m "not integration"
```

Integration tests (require local Postgres + `kpa_test` database — see [Database](#database)):

```bash
uv run pytest -v -m integration
```

Full suite:

```bash
uv run pytest -v
```

## Lint, format, type-check

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

## Configuration

All settings are read from environment variables prefixed `KPA_`:

| Variable           | Required | Default | Purpose                         |
| ------------------ | -------- | ------- | ------------------------------- |
| `KPA_ENV`          | yes      | —       | `local` \| `dev` \| `staging` \| `prod` |
| `KPA_SERVICE_NAME` | yes      | —       | Reported in `/health`           |
| `KPA_DB_URL`       | yes      | —       | SQLAlchemy DSN; must use the `postgresql+asyncpg://` driver |
| `KPA_STORAGE_ROOT` | no       | `var/uploads` | Filesystem root for `LocalFileStorage`. Relative paths resolve against CWD. |
| `KPA_MAX_UPLOAD_BYTES` | no   | `10485760` | Max bytes per upload (10 MiB).                      |
| `KPA_ALLOWED_RESUME_CONTENT_TYPES` | no | (pdf, doc, docx) | Comma-separated content-type whitelist. |
| `KPA_LOG_LEVEL`    | no       | `INFO`  | Stdlib log level                |
| `KPA_LOG_FORMAT`   | no       | `text`  | `text` (key=value) or `json`    |
| `KPA_JWT_SECRET`   | yes      | —       | HS256 signing secret; min 32 bytes |
| `KPA_JWT_ACCESS_TTL_SECONDS`  | no | `600`     | Access token lifetime (10 min default) |
| `KPA_JWT_REFRESH_TTL_SECONDS` | no | `2592000` | Refresh token lifetime (30 d default)  |
| `KPA_GOOGLE_OAUTH_CLIENT_IDS` | yes | —        | CSV of Google Client IDs (web/iOS/Android) |
| `KPA_GOOGLE_JWKS_URL`         | no | `https://www.googleapis.com/oauth2/v3/certs` | Override for tests / offline dev |
| `KPA_GOOGLE_JWKS_CACHE_TTL_SECONDS` | no | `3600` | JWKS in-process cache TTL |
| `KPA_AUTH_REQUIRE_EMAIL_VERIFIED`   | no | `false` | Reject Google sign-ins without `email_verified=true` |
| `KPA_REDIS_URL`    | yes      | —       | Redis connection string (`redis://` or `rediss://`). Required for Celery broker. |
| `KPA_CELERY_TASK_ALWAYS_EAGER` | no | `false` | When true, Celery tasks run synchronously in-process. Tests only. |
| `KPA_GEMINI_API_KEY` | yes    | —       | Gemini Developer API key for the embedding worker |
| `KPA_EMBEDDING_MODEL` | no   | `gemini-embedding-2` | Embedding model identifier |
| `KPA_EMBEDDING_DIM` | no     | `1536`  | Matryoshka output dim — must be in {128,256,512,768,1024,1536,3072} and match the migration's Vector(N) |

The service refuses to boot if required variables are missing or invalid.

## Auth

Three sign-in/session endpoints plus one identity endpoint:

```
POST   /v1/auth/oauth/google          # Google ID token → access + refresh
POST   /v1/auth/refresh               # rotate refresh; new access + refresh
POST   /v1/auth/logout                # revoke refresh (idempotent 204)
GET    /v1/me                         # current user + applicant payload
```

The Google flow is **client-driven** — the Flutter app obtains a Google ID
token via the official SDK and POSTs it to `/v1/auth/oauth/google`. The
backend verifies the token against Google's JWKS, upserts the user, and
mints an HS256 access JWT (10 min) plus an opaque rotating refresh token
(30 d, sha256-hashed at rest).

There's no `/callback` redirect endpoint — the spec's prior `/oauth/{provider}/callback`
naming was inaccurate for client-driven flows and was replaced.

Refresh tokens rotate on every successful refresh. Reuse of an
already-rotated token triggers full revocation of the family. See
`docs/superpowers/specs/2026-05-17-auth-google-oauth-applicant-design.md`
for the design rationale.

### Quick test from the shell

```bash
# Mint a JWT secret if you don't have one yet:
openssl rand -base64 48 | tr -d '\n' | tr -d '=' | head -c 64

# Then start the server (with KPA_JWT_SECRET and KPA_GOOGLE_OAUTH_CLIENT_IDS set in .env)
# and hit /v1/me with a valid Bearer access JWT:
ACCESS=...   # from a real Google sign-in
curl -s http://127.0.0.1:8000/v1/me -H "Authorization: Bearer $ACCESS" | python -m json.tool
```

## Project layout

```
api/
├── alembic.ini
├── src/kpa/
│   ├── app_factory.py        # create_app() — middlewares + routes + engine + storage
│   ├── main.py               # uvicorn entry point
│   ├── settings.py
│   ├── middleware/
│   │   ├── request_id.py     # X-Request-Id propagation
│   │   └── error_handler.py  # RFC 7807 problem+json
│   ├── observability/
│   │   └── logging.py        # structlog config
│   ├── workers/
│   │   ├── celery_app.py     # Celery instance + per-worker engine lifecycle
│   │   └── tasks/
│   │       └── parse.py       # parse_resume — 3-txn split, retry, idempotency
│   ├── integrations/
│   │   ├── storage/          # Storage protocol + LocalFileStorage
│   │   └── parser/
│   │       ├── base.py        # ResumeParser Protocol + ParsedResume schema
│   │       ├── text.py        # PDF (pypdf+pdfminer) + DOCX extraction
│   │       ├── library.py     # LibraryResumeParser — regex + keyword impl
│   │       └── skills_dict.py # Curated skill keyword list
│   ├── db/
│   │   ├── session.py        # async engine, sessionmaker, get_session dep
│   │   ├── models.py         # Base, User, Applicant, Resume
│   │   └── migrations/       # alembic env + versions/
│   ├── auth/
│   │   ├── dependencies.py    # current_user, optional_current_user
│   │   ├── google_verifier.py # JWKS-backed Google ID-token verifier
│   │   ├── service.py         # AuthService — sign-in, refresh, logout
│   │   └── tokens.py          # HS256 access JWT + opaque refresh primitives
│   └── routes/
│       ├── health.py         # GET /health (liveness)
│       ├── ready.py          # GET /ready (readiness, DB ping)
│       ├── resumes.py        # /v1/applicants/me/resumes …
│       ├── auth.py           # /v1/auth/oauth/google, /refresh, /logout
│       └── me.py             # GET /v1/me
└── tests/
    ├── unit/                 # no DB required
    └── integration/          # require local Postgres (savepoint isolation)
```
