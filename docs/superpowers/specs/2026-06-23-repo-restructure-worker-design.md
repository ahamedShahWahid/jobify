# Repo restructure — shared `core/` + peer `api/` & `worker/` packages — design

**Date:** 2026-06-23
**Status:** Approved (architecture); spec under review.

## Goal

Split the single backend package (`jobify`, today living entirely under `api/`)
into **three packages in a uv workspace**, so the worker is a true peer of the api
rather than nested inside it:

```
deps:   api ─► core ◄─ worker
```

- **core/** — the shared domain (models, db, settings, integrations, scoring,
  consent, audit, observability, the Celery producer + email templates).
- **api/** — the FastAPI service (app, routes, middleware, auth, dsr, employers,
  pagination, request-scoped dependencies, operational CLIs). Depends on core.
- **worker/** — the Celery daemon (celery_app + tasks). Depends on core.

Plus the existing `app/` (Flutter) and `frontend/` (web). Static `styleguide/`
moves under `frontend/`. This restructure also resolves the original ask (a
top-level home for the daemon) — `worker/` IS that home, now as a real package.

## Decisions taken during brainstorming

- **Driver:** the worker must not live under the api layer. Chosen architecture =
  **shared core, api + worker as peers** (not "worker depends on api", not "worker
  nested in api").
- **Churn-minimizing package naming:** the shared domain package keeps the import
  name **`jobify`** (moved to `core/src/jobify/`). So every `from jobify.<domain>
  import …` in the domain itself and in the worker stays unchanged. Only
  api-specific modules move to a NEW package **`jobify_api`** (`api/src/jobify_api/`),
  and the worker moves to **`jobify_worker`** (`worker/src/jobify_worker/`).
- **Dispatch decoupling (breaks the cycle):** the **Celery app instance lives in
  core** (`jobify.celery_app`) — bare: broker/backend + task_routes + conf only, with
  **no task imports and no reference to the worker package**. The worker registers
  the task implementations onto that shared app and owns the worker-runtime signals;
  the api dispatches **by task name** via `celery_app.send_task(...)`, so api never
  imports worker. Task names are already explicit (`name="jobify.parse_resume"`, etc.).
  This single-shared-app design (vs a separate producer) also makes Celery eager mode
  work in tests: the task modules are imported in-process (tests already import them),
  registering them on the shared app, so `send_task` runs inline under
  `task_always_eager`.
- **Static dirs:** `styleguide/` → `frontend/styleguide/`. `emails/` → `core/emails/`
  (the email channel that renders+sends them lives in `integrations/email`, which is
  core).
- **Tests:** one workspace-level suite at repo-root `tests/` (moved from
  `api/tests/`). A per-package test split is explicitly **out of scope** (the
  integration fixtures span routes→tasks→domain; fragmenting them adds risk for no
  near-term benefit).

## Module mapping (`jobify` package today → target package)

Determined by FastAPI coupling + who imports each module (worker imports were
audited: it touches only db, settings, integrations, scoring, consent, audit).

### core/ — package `jobify` (framework-free domain)
- `db/` — `models.py`, the engine/sessionmaker in `session.py` (see split below),
  `migrations/` + alembic.
- `settings.py`, `observability/`, `consent/`, `audit/`, `scoring/`.
- `integrations/` — `parser/`, `embeddings/`, `storage/` (Storage protocol +
  `LocalFileStorage`), `notifications/`, `email/`.
- `eval/` — the parse-F1 quality gate (exercises the library parser = domain).
- **NEW `celery_app.py`** — the bare shared Celery app: `Celery("jobify",
  broker=settings.redis_url, backend=…)` + `conf.update(task_default_queue,
  task_acks_late, worker_prefetch_multiplier, task_always_eager from settings,
  task_routes, …)`. **No `include=`, no task imports, no worker reference.** Plus a
  thin `enqueue(name, *args)` helper wrapping `celery_app.send_task(name, args=[…])`
  for the api's dispatch sites.
- `emails/` — the email templates (moved from repo root).

### api/ — package `jobify_api` (FastAPI service, depends on core)
- `app_factory.py`, `main.py`, `routes/`, `middleware/`, `auth/`, `dsr/`,
  `employers/`, `pagination.py`.
- **NEW `dependencies.py`** (or `deps/`) — the two request-scoped FastAPI
  dependencies extracted from core: `get_session(request: Request)` (was in
  `db/session.py`) and `get_storage(request: Request)` (was in
  `integrations/storage/base.py`). Core keeps the engine/sessionmaker + Storage
  protocol; the `Request`-typed wrappers (the only FastAPI imports in those domain
  files) move here so core is framework-free.
- `scripts/` — operational CLIs (`jobify-seed-jobs`, `jobify-seed-consents`,
  `jobify-grant-admin`). `seed_jobs` dispatches via the core producer. The
  `[project.scripts]` entry points move to api's pyproject.

### worker/ — package `jobify_worker` (Celery daemon, depends on core)
- `tasks/` (parse, embed, embed_job, score_applicant, score_job,
  sweep_notifications) — each `@celery_app.task(name="jobify.…")` where
  `celery_app` is imported from core (`from jobify.celery_app import celery_app`).
  Domain imports stay `from jobify.…`; intra-worker imports become
  `from jobify_worker.…`. Worker→worker dispatch (`.delay()` chaining) is unchanged.
- **`worker_app.py`** — the `celery -A` entry target: imports the core `celery_app`,
  imports every task module (to register them), and connects the worker-runtime
  signals (`worker_process_init`/`worker_shutting_down` → the per-worker
  `NullPool` engine + sessionmaker lifecycle, moved here from today's celery_app).
  Run: `celery -A jobify_worker.worker_app worker -Q parse,embed,score,notify`.
- `README.md` — run worker + (inert) beat, queue list, the Redis + root `.env`
  dependency, and a pointer that the shared Celery app config lives in
  `core` (`jobify.celery_app`).

## The dispatch decoupling (concrete)

The 4 api→worker sites change from importing the task function to a name-based
dispatch via the core `enqueue` helper:

| Site | Was | Becomes |
| --- | --- | --- |
| `scripts/seed_jobs.py` | `from jobify.workers.tasks.embed_job import embed_job; embed_job.delay(jid)` | `from jobify.celery_app import enqueue; enqueue("jobify.embed_job", jid)` |
| `routes/resumes.py` | `parse_resume.delay(rid)` | `enqueue("jobify.parse_resume", rid)` |
| `routes/applicants.py` | `score_applicant.delay(aid)` | `enqueue("jobify.score_applicant", aid)` |
| `routes/jobs.py` (×2) | `embed_job.delay(jid)` | `enqueue("jobify.embed_job", jid)` |

`enqueue(name, *args)` wraps `celery_app.send_task(name, args=[...])`; the routing
comes from the app's `task_routes`. Because the app is the SAME instance the worker
registers tasks onto, `task_always_eager` (set from settings) makes `send_task` run
the task inline in tests — provided the task modules are imported in-process so they
register. The integration tests already import the task modules (they assert on task
behavior), and the eager fixture will import `jobify_worker.tasks` to guarantee
registration. This removes the two-app eager hazard a separate producer would have
created.

## Workspace + packaging

- **Root `pyproject.toml`** (NEW) — `[tool.uv.workspace] members = ["core", "api",
  "worker"]`; owns dev/test deps (pytest, ruff, mypy, fpdf2) and the shared
  `[tool.ruff]` / `[tool.mypy]` / `[tool.pytest.ini_options]` config.
- **`core/pyproject.toml`** — runtime domain deps: sqlalchemy[asyncio], asyncpg,
  alembic, pgvector, pydantic, pydantic-settings, structlog, google-genai, pdf libs
  (pdfminer.six, pypdf, python-docx), celery[redis] (for the producer), httpx,
  pyjwt[crypto] (token utils if domain), anyio.
- **`api/pyproject.toml`** — `jobify` (core, workspace dep) + fastapi, uvicorn,
  python-multipart. Holds the `[project.scripts]` entry points.
- **`worker/pyproject.toml`** — `jobify` (core) + celery[redis].
- uv workspace = one lockfile, one venv; `uv sync` at root installs all three.
- Per-dep placement (which lib is core vs api vs worker) is finalized in the plan by
  grepping actual imports per package; the lists above are the starting split.

### `.env` / config

- The single `.env` moves to the **repo root** (`api/.env` → `./.env`); all run
  commands load it (`uv run --env-file=.env …` from root, or `--env-file=../.env`
  from a package dir). `JOBIFY_DB_URL`, `JOBIFY_REDIS_URL`, `JOBIFY_TEST_DB_URL`,
  and the rest are unchanged. `.gitignore` already ignores `.env`; add the root
  `.env` / `.env.example`. Alembic (`cd core && uv run alembic …`) and the worker
  (`cd worker && uv run …`) both reference the root env file.

## Alembic

Moves to `core/` (core owns the models). `core/alembic.ini` +
`core/src/jobify/db/migrations/`. `env.py` imports are unchanged
(`from jobify.db.models import Base`, `from jobify.settings import Settings`). Run
via `cd core && uv run alembic upgrade head` (README updated).

## Tests

- Move `api/tests/` → repo-root `tests/` (unit, integration, eval, conftest).
- Update imports: `jobify.app_factory` → `jobify_api.app_factory`, route/middleware/
  auth/dsr/employers/pagination references → `jobify_api.*`; worker task references →
  `jobify_worker.*`; domain references stay `jobify.*`.
- The savepoint/integration conftest is unchanged in behavior; it imports
  `jobify_api.app_factory.create_app` for the ASGI clients and `jobify.*` for domain.
- CI runs from root: `uv run ruff check core api worker tests`,
  `uv run ruff format --check …`, `uv run mypy`, `uv run pytest …` (same markers).

## Verification (behavior must be identical)

- `uv sync` at root succeeds; all three packages import.
- `uv run pytest -v -m "not integration and not eval"`, `-m eval`, and `-m
  integration` all green (the existing suite is the behavioral contract — same
  tests, new import paths).
- `uv run ruff check`, `ruff format --check`, `uv run mypy` clean across all three
  packages.
- Worker smoke: `cd worker && uv run celery -A jobify_worker.celery_app worker
  -Q parse,embed,score,notify` starts and logs ready; a dispatched task
  (`enqueue(...)` from an api route) is consumed.
- `frontend` untouched → `npm run build` clean; `frontend/styleguide/index.html`
  still opens.
- A grep proves no remaining `from jobify.workers` / `jobify.routes` / `jobify.app_factory`
  imports (those moved) and no dangling `emails/` / `styleguide/` path refs.

## Phasing (one cohesive refactor; each phase ends green)

1. **Workspace skeleton** — root `pyproject.toml` (workspace + tool config) and the
   three empty package dirs with pyprojects; `uv sync` works.
2. **Extract core** — move domain modules into `core/src/jobify/` (names unchanged);
   move the engine/sessionmaker + Storage protocol, stripping the two FastAPI
   `Request` deps (they reappear in api in phase 3); add `jobify.celery_app` (bare
   app + `enqueue`); move alembic + `emails/`. Core imports/builds with no FastAPI.
3. **Carve api** — move api modules into `api/src/jobify_api/`; create
   `jobify_api/dependencies.py` (get_session/get_storage); repoint intra-api imports
   to `jobify_api.*`; move `[project.scripts]`.
4. **Move worker** — relocate to `worker/src/jobify_worker/`; intra-worker imports →
   `jobify_worker.*`; `celery -A` path; rewire the 4 dispatch sites to
   `jobify.queue.enqueue`; resolve eager-mode dispatch for tests.
5. **Tests + CI + docs** — move tests to root, fix imports, update CI commands;
   `styleguide → frontend/`; update `CLAUDE.md`, the three READMEs, project memory.
   Full green run from root.

## Out of scope

- Per-package test suites (one root suite for now).
- Defining a real `beat_schedule` / periodic tasks.
- Containerization (Dockerfiles/Procfiles) — `worker/`, `api/` are the future homes.
- Optimizing prod dependency closures beyond the core/api/worker split.
- Any change to runtime behavior, endpoints, queues, or task logic.
