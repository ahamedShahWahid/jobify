# Jobify — Installation & Usage

A start-to-finish guide to running the full Jobify stack locally: backend (FastAPI API + Celery worker), web frontend (Vite/React), and the Flutter client.

This document stitches together the per-package READMEs into one onboarding path. For deeper, package-specific detail see `api/README.md`, `worker/README.md`, `frontend/README.md`, and `app/README.md`.

---

## 1. Architecture at a glance

```
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│ Flutter app  │   │ Web frontend │   │  (other clients) │
│ iOS/Android/ │   │ Vite + React │   │                  │
│ web  :8080   │   │   :5173      │   │                  │
└──────┬───────┘   └──────┬───────┘   └────────┬─────────┘
       │                  │                    │
       └──────────────────┼────────────────────┘
                          ▼  HTTPS / JWT
                 ┌──────────────────┐
                 │  jobify_api      │  FastAPI  :8000
                 │  (api/)          │
                 └───┬─────────┬────┘
        enqueue by   │         │  SQLAlchemy (asyncpg)
        task name    ▼         ▼
        ┌──────────────┐   ┌──────────────────┐
        │ Redis        │   │ Postgres 16      │
        │ broker :6379 │   │ + pgvector :5432 │
        └──────┬───────┘   └──────────────────┘
               ▼
        ┌──────────────────┐
        │ jobify_worker    │  Celery (parse/embed/score/notify)
        │ (worker/)        │
        └──────────────────┘
```

### Where everything runs (local)

| Service | URL / address | Port | Started by |
|---------|---------------|------|-----------|
| **API** (FastAPI) | http://localhost:8000 | 8000 | `uvicorn jobify_api.main:app` (§4.7) |
| → Swagger UI | http://localhost:8000/docs | 8000 | — |
| → ReDoc | http://localhost:8000/redoc | 8000 | — |
| → OpenAPI schema | http://localhost:8000/openapi.json | 8000 | — |
| → Liveness probe | http://localhost:8000/health | 8000 | — |
| → Readiness probe | http://localhost:8000/ready | 8000 | — |
| **Web frontend** (Vite) | http://localhost:5173 | 5173 | `npm run dev` (§6) |
| → web surface | http://localhost:5173/#/ | 5173 | — |
| → employers surface | http://localhost:5173/#/employers | 5173 | — |
| → console surface | http://localhost:5173/#/console/signin | 5173 | — |
| **Flutter web** | http://localhost:8080 | 8080 | `flutter run -d web-server --web-port=8080` (§7) |
| **Postgres** | localhost:5432 (`jobify`, `jobify_test`) | 5432 | `brew services start postgresql@16` |
| **Redis** (Celery broker) | localhost:6379 (db 0) | 6379 | `brew services start redis` |
| **Celery worker** | no listening port (consumes Redis queues) | — | `celery -A jobify_worker.worker_app worker` (§4.8) |

> From the Android emulator, reach the API at **http://10.0.2.2:8000** (the emulator's
> alias for the host's `localhost`), not `localhost:8000`.

The backend is a **uv workspace** with three packages, all driven from the repo root:

| Package   | Distribution   | Role |
|-----------|----------------|------|
| `core/`   | `jobify`        | Domain: DB models + Alembic migrations, integrations (storage, parser, embeddings, email, scoring), Celery app config, seeding CLI |
| `api/`    | `jobify_api`    | FastAPI service — app factory, routes, auth/JWT, middleware. Entry point `jobify_api.main:app` |
| `worker/` | `jobify_worker` | Celery daemon — `parse`, `embed`, `score`, `sweep_notifications` tasks |

> **Two rules that prevent most first-run confusion:**
> 1. All backend commands run from the **repo root** (where `pyproject.toml`, `uv.lock`, and `.env` live)…
> 2. …**except Alembic**, which runs from `core/` (its `alembic.ini` lives there).

---

## 2. Prerequisites

| Tool | Version | Install | Needed for |
|------|---------|---------|------------|
| Python | 3.12 (`>=3.12,<3.13`) | `brew install python@3.12` | backend |
| [uv](https://docs.astral.sh/uv/) | 0.5+ | `brew install uv` | backend (package manager) |
| PostgreSQL | 16 | `brew install postgresql@16` | backend |
| pgvector | 0.8.0 | build from source (§4.4) | embedding worker |
| Redis | latest | `brew install redis` | Celery broker |
| Node.js | 18+ | `brew install node` | web frontend |
| Flutter | 3.27.x (stable) | [flutter.dev](https://docs.flutter.dev/get-started/install) | mobile/web app |

> **No Docker for MVP.** Local dev uses Homebrew services directly. Containerization rejoins the project at the deploy-target step.
>
> **uv only** — never `pip install` (it bypasses `uv.lock`).

---

## 3. Fast path — one command

Once the prerequisites in §2 and the env file in §5 are in place, boot the entire stack:

```bash
scripts/start-all.sh                 # Postgres, Redis, migrations, API, worker, frontend
scripts/start-all.sh --with-flutter  # also launch the Flutter web client on :8080 (slow DDC build)
```

Idempotent and safe to re-run. Logs + PID files land in `var/run/` (gitignored).

Tear it all down:

```bash
scripts/stop-all.sh                  # stops app processes; leaves Postgres/Redis running
scripts/stop-all.sh --with-infra     # also stops the Homebrew Postgres/Redis services
```

If you prefer to understand each piece (or `start-all.sh` fails), follow the manual setup below — it is exactly what the script automates.

---

## 4. Manual setup — backend

### 4.1 Clone & install dependencies

```bash
git clone <repo-url> jobify
cd jobify
uv sync                  # creates .venv, installs all 3 workspace packages + dev tools
```

### 4.2 Create the env file

```bash
cp .env.example .env     # root .env — NOT inside api/
```

Then edit `.env` — see §5 for the variables that must be set before first boot.

### 4.3 Postgres (one-time per machine)

```bash
brew install postgresql@16
brew services start postgresql@16

psql -d postgres <<'SQL'
CREATE ROLE jobify WITH LOGIN PASSWORD 'jobify' CREATEDB;
CREATE DATABASE jobify OWNER jobify;
CREATE DATABASE jobify_test OWNER jobify;
SQL
```

The dev DSN in `.env`:

```
JOBIFY_DB_URL=postgresql+asyncpg://jobify:jobify@localhost:5432/jobify
```

`jobify_test` is used by the integration tests (override with `JOBIFY_TEST_DB_URL`).

### 4.4 pgvector (required for the embedding worker)

Homebrew only bottles pgvector for PG17/18, so on Postgres 16 build it from source:

```bash
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make install
```

Enable the extension on both databases (as a superuser):

```bash
psql -U postgres -d jobify      -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -U postgres -d jobify_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 4.5 Run migrations (from `core/`)

```bash
cd core && uv run alembic upgrade head && cd ..
```

> Migrations are **hand-written** (autogenerate is off). To add one:
> ```bash
> cd core && uv run alembic revision -m "describe the change"
> # edit the new file under core/src/jobify/db/migrations/versions/
> cd core && uv run alembic upgrade head
> ```

### 4.6 Redis (one-time per machine)

```bash
brew install redis
brew services start redis
```

```
JOBIFY_REDIS_URL=redis://localhost:6379/0
```

### 4.7 Run the API

```bash
uv run --env-file=.env uvicorn jobify_api.main:app --reload --port 8000
```

Verify:

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool   # liveness
curl -s http://127.0.0.1:8000/ready  | python -m json.tool   # DB/Redis readiness
```

Expected `/health`:

```json
{ "status": "ok", "service": "jobify-api", "version": "0.1.0", "env": "local" }
```

Useful URLs:

- `http://127.0.0.1:8000/docs` — Swagger UI
- `http://127.0.0.1:8000/redoc` — ReDoc
- `http://127.0.0.1:8000/openapi.json` — raw schema

Every response carries an `X-Request-Id` header — the log-correlation handle.

### 4.8 Run the worker

```bash
uv run --env-file=.env celery -A jobify_worker.worker_app worker \
    --pool=solo --concurrency=1 -Q parse,embed,score,notify,outbox --loglevel=info
```

| Queue    | Tasks |
|----------|-------|
| `parse`  | `jobify.parse_resume` |
| `embed`  | `jobify.embed_applicant`, `jobify.embed_job` |
| `score`  | `jobify.score_applicant`, `jobify.score_job` |
| `notify` | `jobify.sweep_notifications` |
| `outbox` | `jobify.sweep_outbox` |

API and worker transactions stage task names and arguments in `outbox_events`.
`jobify.sweep_outbox` leases those rows and publishes them to Celery.

> Run Celery beat alongside the worker; it schedules both notification and
> durable-outbox sweeps from `jobify_worker.celery_app`.
> For tests, set `JOBIFY_CELERY_TASK_ALWAYS_EAGER=true` to run tasks inline (no Redis).

### 4.9 Seed demo data

```bash
uv run --env-file=.env jobify-seed-jobs            # apply (idempotent)
uv run --env-file=.env jobify-seed-jobs --dry-run  # validate JSON only, nothing written
```

Fixture: `core/data/sample_jobs.json` (10 employers, 27 jobs). Email templates: `core/emails/`.

---

## 5. Configuration (`.env`)

All settings are environment variables prefixed `JOBIFY_`, read from the **repo-root** `.env`. **The API refuses to boot if a required variable is missing or invalid.** Generate a JWT secret with `openssl rand -base64 32`.

These **7 are required** to boot — set them in `.env` first:

| Variable | Purpose |
|----------|---------|
| `JOBIFY_ENV` | `local` \| `dev` \| `staging` \| `prod` |
| `JOBIFY_SERVICE_NAME` | Reported in `/health` |
| `JOBIFY_DB_URL` | SQLAlchemy DSN — **must** be `postgresql+asyncpg://` |
| `JOBIFY_JWT_SECRET` | HS256 signing secret, min 32 bytes |
| `JOBIFY_GOOGLE_OAUTH_CLIENT_IDS` | CSV of accepted Google client IDs (web/iOS/Android) |
| `JOBIFY_REDIS_URL` | Celery broker + result backend |
| `JOBIFY_GEMINI_API_KEY` | Gemini API key for the embedding worker |

The remaining ~18 optional vars (logging, upload limits, JWT TTLs, CORS, embedding, email, scoring/explainer) all have working defaults — **the full annotated table is in [`api/README.md` → Configuration](api/README.md#configuration)** (single source of truth; `.env.example` is the tracked template). Two onboarding gotchas worth knowing up front:

> ⚠️ **CORS override replaces, not appends.** Setting `JOBIFY_CORS_ALLOW_ORIGINS` to a single origin drops the default. To support both the web frontend and Flutter web, list both: `http://localhost:5173,http://localhost:8080`. CORS is read at startup — **restart the API** after changing it.
>
> ⚠️ **`JOBIFY_EMBEDDING_DIM` must match the migration's `Vector(N)`** — changing it without a matching migration breaks the embedding worker.

---

## 6. Web frontend (`frontend/`)

One Vite + React + TS app; three surfaces under one HashRouter (all URLs live under `/#/`):

| Surface | Dev URL | Purpose |
|---------|---------|---------|
| **web** | `http://localhost:5173/#/` | applicant + public marketing |
| **employers** | `http://localhost:5173/#/employers` | recruiter marketing |
| **console** | `http://localhost:5173/#/console/signin` | internal admin + recruiter ops |

```bash
cd frontend
npm install
cp .env.example .env      # set VITE_GOOGLE_CLIENT_ID, VITE_API_BASE_URL
npm run dev               # http://localhost:5173
npm run build             # tsc -b && vite build → dist/
```

> The web surfaces need `http://localhost:5173` in the API's `JOBIFY_CORS_ALLOW_ORIGINS` **and** in the Google Web OAuth client's *Authorized JavaScript origins*.

---

## 7. Flutter client (`app/`)

iOS + Android + Web client. Stack: Flutter 3.27.x, Riverpod 4.x, freezed 3.x, dio 5.7, go_router 14.6, google_sign_in.

```bash
cd app
flutter pub get
dart run build_runner build --delete-conflicting-outputs
cp .env.example .env      # set JOBIFY_GOOGLE_WEB_CLIENT_ID, JOBIFY_API_BASE_URL
```

Run (the backend must be up on `http://localhost:8000` first):

```bash
# iOS simulator
flutter run -d ios --dart-define-from-file=.env

# Android emulator — note 10.0.2.2 is the emulator's alias for the host's localhost
flutter run -d emulator-5554 \
  --dart-define=JOBIFY_API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define-from-file=.env

# Web — pin :8080 so it matches the Google OAuth allowlist
flutter run -d web-server --web-port=8080 --dart-define-from-file=.env
```

> **Web Google sign-in** uses the GIS rendered-button flow. The Web OAuth client must
> list `http://localhost:8080` (no trailing slash) under *Authorized JavaScript origins*
> (NOT redirect URIs), and `:8080` must be in `JOBIFY_CORS_ALLOW_ORIGINS`. Changes
> propagate in 5 min – a few hours; probe without a browser:
> ```bash
> curl -s -o /dev/null -w '%{http_code}\n' -H 'Origin: http://localhost:8080' \
>   'https://accounts.google.com/gsi/button?client_id=<WEB_CLIENT_ID>&is_fedcm_supported=true'
> # 403 = not allowed yet; 200 = live
> ```

iOS one-time config (Xcode build configs, `Debug.xcconfig`) is documented in `app/README.md`.

---

## 8. Usage — auth flow

The clients obtain a Google ID token and exchange it for Jobify tokens:

```
POST   /v1/auth/oauth/google   # Google ID token → access JWT (10 min) + refresh (30 d)
POST   /v1/auth/refresh        # rotate refresh; returns new access + refresh
POST   /v1/auth/logout         # revoke refresh (idempotent 204)
GET    /v1/me                  # current user + applicant payload
```

Refresh tokens rotate on every use; reusing a rotated token triggers full family revocation. Access tokens are HS256; refresh tokens are opaque and sha256-hashed at rest.

Versioned routes live under `/v1`; only `/health` and `/ready` are unversioned (probes).

---

## 9. Tests, lint, type-check

Run the **exact CI commands** before claiming green (from repo root):

```bash
# Backend
uv run ruff check core/src api/src worker/src tests
uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"   # unit (no DB)
uv run pytest -v -s -m eval                           # parse-F1 quality gate (no DB)
uv run pytest -v -m integration                       # needs local Postgres + jobify_test

# Flutter (from app/)
dart format --set-exit-if-changed lib test
flutter analyze
flutter test
```

Integration tests set `JOBIFY_CELERY_TASK_ALWAYS_EAGER=true`, so Redis isn't required during `pytest`.

---

## 10. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| API exits immediately on boot | A required `JOBIFY_*` var is missing/invalid. Check the startup error; verify `.env` against §5. |
| `JOBIFY_DB_URL must use postgresql+asyncpg` | DSN uses `postgresql://`; change the driver to `postgresql+asyncpg://`. |
| `alembic: command not found` / wrong dir | Alembic runs from `core/`, not the repo root: `cd core && uv run alembic upgrade head`. |
| `extension "vector" does not exist` | pgvector not built/enabled — see §4.4 (build for PG16, `CREATE EXTENSION` on both DBs). |
| Web sign-in button 403s | Dev origin not in the Web OAuth client's *Authorized JavaScript origins*, or not yet propagated — probe with the `gsi/button` curl in §7. |
| Browser blocks API calls (CORS) | Origin missing from `JOBIFY_CORS_ALLOW_ORIGINS` (override replaces the default — list all origins), or API not restarted after the change. |
| Flutter (Android) can't reach the API | Use `http://10.0.2.2:8000`, not `localhost` — the emulator's host-loopback alias. |
| 500s after pulling new migrations | Run `cd core && uv run alembic upgrade head` — a new column exists in code but not your local DB. |
| `start-all.sh: no .env at repo root` | Copy `.env.example` → `.env` first. |
| Worker does nothing | Redis not running (`brew services start redis`) or `JOBIFY_REDIS_URL` wrong; confirm the worker prints it's consuming the four queues. |

---

## 11. Reference

- `WORKFLOW.md` — branch workflow (`scripts/new-feature.sh`, `scripts/sync-with-main.sh`)
- `api/README.md` · `worker/README.md` · `frontend/README.md` · `app/README.md` — package detail
- `CLAUDE.md` + per-package `core/`, `api/`, `worker/`, `app/`, `frontend/` `CLAUDE.md` — code invariants
- `docs/prd/` — product BRD (what we build)
