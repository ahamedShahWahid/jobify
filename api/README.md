# KPA API

FastAPI service for the Khan Placement Agency platform. This directory contains the backend foundations + DB layer. Auth and domain code land in follow-on plans.

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
| `KPA_LOG_LEVEL`    | no       | `INFO`  | Stdlib log level                |
| `KPA_LOG_FORMAT`   | no       | `text`  | `text` (key=value) or `json`    |

The service refuses to boot if required variables are missing or invalid.

## Project layout

```
api/
├── alembic.ini
├── src/kpa/
│   ├── app_factory.py        # create_app() — middlewares + routes + engine
│   ├── main.py               # uvicorn entry point
│   ├── settings.py
│   ├── middleware/
│   │   ├── request_id.py     # X-Request-Id propagation
│   │   └── error_handler.py  # RFC 7807 problem+json
│   ├── observability/
│   │   └── logging.py        # structlog config
│   ├── db/
│   │   ├── session.py        # async engine, sessionmaker, get_session dep
│   │   ├── models.py         # Base, User, Applicant
│   │   └── migrations/       # alembic env + versions/
│   └── routes/
│       ├── health.py         # GET /health (liveness)
│       └── ready.py          # GET /ready (readiness, DB ping)
└── tests/
    ├── unit/                 # no DB required
    └── integration/          # require local Postgres (savepoint isolation)
```
