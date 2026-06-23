# Repo restructure (core/api/worker workspace) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single backend package (`jobify`, today under `api/`) into a uv workspace of three packages — `core/` (shared domain, keeps import name `jobify`), `api/` (`jobify_api`, FastAPI), `worker/` (`jobify_worker`, Celery) — with `api → core ← worker` and no `core→api`/`api↔worker` edges.

**Architecture:** Domain code keeps the import name `jobify` and moves to `core/src/jobify/` (so domain + worker imports stay `from jobify.…`). Api-specific modules move to `api/src/jobify_api/`; worker moves to `worker/src/jobify_worker/`. The Celery app instance lives in core (bare: broker + routes + config + an `enqueue()` helper); the worker registers tasks + runtime signals onto it; the api dispatches by task name. No runtime behavior changes — the existing test suite is the behavioral contract.

**Tech Stack:** Python 3.12, uv workspace, FastAPI, Celery[redis], async SQLAlchemy + Alembic, Postgres 16, structlog, pytest.

## Global Constraints

- **No runtime behavior change.** Endpoints, queues, task logic, and DB schema are identical. The existing test suite must stay green throughout — it is the contract.
- **Package import names:** core = **`jobify`** (unchanged), api = **`jobify_api`**, worker = **`jobify_worker`**. Domain/worker imports of domain stay `from jobify.<domain>…`.
- **No `core→api` edges** (verified: none today) and **no `api↔worker` import edges** (api dispatches by task name via `jobify.celery_app.enqueue`; worker imports only `jobify.*`).
- **Module split (authoritative):**
  - **core (`jobify`):** `db/` (models, session engine/sessionmaker, migrations), `settings.py`, `observability/`, `consent/`, `audit/`, `scoring/`, `integrations/` (parser, embeddings, storage protocol+local, notifications, email), `eval/`, NEW `celery_app.py` (bare app + `enqueue`), `emails/` (moved from repo root).
  - **api (`jobify_api`):** `app_factory.py`, `main.py`, `routes/`, `middleware/`, `auth/`, `dsr/`, `employers/`, `pagination.py`, `scripts/`, NEW `dependencies.py` (the `get_session`/`get_storage` FastAPI request-deps).
  - **worker (`jobify_worker`):** `tasks/` (parse, embed, embed_job, score_applicant, score_job, sweep_notifications), NEW `runtime.py` (per-worker engine/sessionmaker + signals + `get_session_maker` + provider getters), NEW `worker_app.py` (the `celery -A` target).
- **Celery split:** bare app + `settings` singleton + `task_routes` + `enqueue` → `jobify.celery_app` (core). Engine signals (`worker_process_init`/`worker_shutting_down`), `get_session_maker`, `get_embedding_provider`, `get_email_channel`, `get_match_explainer` → `jobify_worker.runtime`. Tasks import `celery_app`/`settings` from `jobify.celery_app`, the rest from `jobify_worker.runtime`. Task names stay `"jobify.parse_resume"` etc.
- **Dep split:** core = alembic, anyio, asyncpg, celery[redis], google-genai, pdfminer.six, pgvector, pydantic, pydantic-settings, pypdf, python-docx, sqlalchemy[asyncio], structlog. api (+core) = fastapi, uvicorn[standard], python-multipart, pyjwt[crypto], httpx. worker (+core) = (none extra).
- **Relocations:** `alembic.ini` + migrations → `core/`; `emails/` → `core/emails/`; `styleguide/` → `frontend/styleguide/`; `.env`/`.env.example` → repo root; test suite → repo-root `tests/` (one suite, no per-package split).
- **Verification per task (the test cycle):** from repo root — `uv sync`; `uv run python -c "<import smoke>"`; `uv run ruff check core api worker tests` (scoped to what exists); `uv run ruff format --check …`; `uv run mypy`; `uv run pytest -v -m "not integration and not eval"`; `uv run pytest -v -s -m eval`; `uv run pytest -v -m integration`. Integration needs local Postgres + `jobify_test` DB + `JOBIFY_TEST_DB_URL` (or the `jobify:jobify` fallback) and Redis for the worker smoke.
- **macOS sed:** use `sed -i ''`. Rewrite imports with `grep -rl 'PATTERN' DIR | xargs sed -i '' 's/OLD/NEW/g'`; escape dots in patterns.
- **uv only** (never pip). Hand-written migrations (autogenerate off). structlog only.

---

## File Structure (target)

```
pyproject.toml          # NEW workspace root: [tool.uv.workspace] members + dev deps + ruff/mypy/pytest config
uv.lock                 # one lockfile (regenerated)
.env  .env.example      # moved from api/
core/
  pyproject.toml        # jobify (domain), no fastapi
  alembic.ini           # moved from api/
  emails/               # moved from repo root
  data/                 # sample_jobs.json, parse_eval/ (moved with core — eval/seed use them)
  src/jobify/           # db, settings, observability, consent, audit, scoring, integrations, eval, celery_app.py
api/
  pyproject.toml        # jobify_api (+ core), fastapi family; [project.scripts]
  src/jobify_api/       # app_factory, main, routes, middleware, auth, dsr, employers, pagination, scripts, dependencies.py
  README.md
worker/
  pyproject.toml        # jobify_worker (+ core)
  src/jobify_worker/    # tasks/, runtime.py, worker_app.py
  README.md
tests/                  # moved from api/tests (unit, integration, eval, conftest)
app/  frontend/  docs/  scripts/
```

> **Note on `data/`:** `api/data/sample_jobs.json` (seeder) and `api/data/parse_eval/` (eval gold set) are consumed by `eval/` (core) and `scripts/seed_jobs` (api). They load via paths relative to the package/repo. Move `api/data/` → `core/data/` and confirm the loaders resolve it (Task 1 verifies via `-m eval`; Task 2 verifies seeder path). If a loader uses a path relative to its own module, adjust it in the owning task.

---

### Task 1: Stand up the uv workspace; relocate the whole package into `core/`

The entire current `jobify` package (including routes + workers, temporarily) moves under `core/` with its import name unchanged, so the full test suite passes with **zero import edits**. This isolates the risky carving (Tasks 2–3) from the mechanical relocation.

**Files:**
- Create: `pyproject.toml` (workspace root), `core/pyproject.toml`
- Move: `api/` dir contents → `core/` (`git mv api core`), then `core/tests` → `tests/`, `emails/` → `core/emails/`, `styleguide/` → `frontend/styleguide/`, `api/.env*` → root
- Modify: import-path-free (no source import edits this task)

**Interfaces:**
- Produces: a single-member workspace (`core`) where `jobify.*` imports unchanged; root-run `uv`/`pytest`/`ruff`/`mypy`. Tasks 2–3 carve packages out of `core`.

- [ ] **Step 1: Move the whole project dir into `core/`**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git mv api core
git mv emails core/emails
git mv styleguide frontend/styleguide
git mv core/tests tests
mv core/.env ./.env 2>/dev/null || true          # .env is gitignored — plain mv
[ -f core/.env.example ] && git mv core/.env.example ./.env.example || true
```

- [ ] **Step 2: Rename the moved project to `core` package config**

Edit `core/pyproject.toml`: change `name = "jobify-api"` → `name = "jobify-core"`. Remove the `[project.scripts]` block (entry points move to api in Task 2 — until then the seed CLIs run via `uv run python -m jobify.scripts.seed_jobs`… but to keep them working now, KEEP `[project.scripts]` here temporarily; they move in Task 2). Keep `[tool.hatch.build.targets.wheel] packages = ["src/jobify"]`. Remove the `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, `[dependency-groups]` blocks from `core/pyproject.toml` — they move to the root workspace pyproject (Step 3). Keep only `[project]` (deps) + `[build-system]` + `[tool.hatch...]`.

- [ ] **Step 3: Create the workspace root `pyproject.toml`**

```toml
[project]
name = "jobify"
version = "0.1.0"
description = "Jobify monorepo workspace"
requires-python = ">=3.12,<3.13"
dependencies = []

[tool.uv]
package = false

[tool.uv.workspace]
members = ["core"]

[tool.uv.sources]
jobify-core = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<0.25",
    "ruff>=0.7,<0.8",
    "mypy>=1.13,<2",
    "fpdf2>=2.7,<3",
    "jobify-core",
]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["core/src", "api/src", "worker/src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "S", "RUF"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S"]

[tool.mypy]
python_version = "3.12"
# (copy the remaining [tool.mypy] body + overrides verbatim from the old api/pyproject.toml,
#  adjusting any `src/` path roots to the new package src dirs as needed)

[tool.pytest.ini_options]
# (copy verbatim from old api/pyproject.toml; ensure testpaths point at tests/)
```
Copy the exact `[tool.mypy]` overrides and `[tool.pytest.ini_options]` body from the pre-move `api/pyproject.toml` (recover via `git show HEAD:api/pyproject.toml`). Ensure pytest markers (`integration`, `eval`) and `testpaths = ["tests"]` are present.

- [ ] **Step 4: Move `data/` and fix alembic location**

`core/data/` already moved with the dir. `core/alembic.ini` moved too. Verify `core/alembic.ini`'s `script_location` points to `src/jobify/db/migrations` (relative to `core/`); adjust if it was absolute. `env.py` imports (`jobify.db.models`, `jobify.settings`) are unchanged.

- [ ] **Step 5: Sync + import smoke**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
rm -rf .venv api/.venv core/.venv && uv sync
uv run python -c "import jobify.app_factory, jobify.workers.celery_app, jobify.db.models; print('core import OK')"
```
Expected: `uv sync` resolves; import prints OK.

- [ ] **Step 6: Run the full verification suite from root**

```bash
uv run ruff check core/src tests && uv run ruff format --check core/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration   # needs Postgres jobify_test + JOBIFY_TEST_DB_URL
```
Expected: all green (unit, eval, integration). If `-m eval` fails on a data path, fix the gold-set path resolution in `jobify/eval/parse_f1.py` (point at `core/data/parse_eval`). If alembic-dependent tests fail, fix `core/alembic.ini` `script_location`.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(repo): uv workspace; relocate backend into core/ (package unchanged)"
```

---

### Task 2: Carve `jobify_api` out of core into `api/`

Move the api-specific modules from `core/src/jobify/` to `api/src/jobify_api/`, extract the two FastAPI request-deps, and rewrite references to the moved modules. Domain imports (`from jobify.<domain>`) stay untouched.

**Files:**
- Create: `api/pyproject.toml`, `api/src/jobify_api/__init__.py`, `api/src/jobify_api/dependencies.py`, `api/README.md` (move from `core/README.md` if backend-run docs live there)
- Move: `core/src/jobify/{app_factory.py,main.py,routes,middleware,auth,dsr,employers,pagination.py,scripts}` → `api/src/jobify_api/`
- Modify: `core/src/jobify/db/session.py` and `core/src/jobify/integrations/storage/base.py` (drop the FastAPI `Request` deps); `core/pyproject.toml` (drop api-only deps + `[project.scripts]`); root `pyproject.toml` (add `api` member); all moved files + `tests/` (import rewrites)

**Interfaces:**
- Consumes: core domain (`jobify.*`), unchanged.
- Produces: `jobify_api.app_factory.create_app`, `jobify_api.dependencies.get_session`/`get_storage`, `[project.scripts]` (`jobify-seed-jobs` etc.) on `jobify_api.scripts.*`.

- [ ] **Step 1: Create the api package skeleton + move modules**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
mkdir -p api/src/jobify_api
git mv core/src/jobify/app_factory.py   api/src/jobify_api/app_factory.py
git mv core/src/jobify/main.py          api/src/jobify_api/main.py
git mv core/src/jobify/pagination.py    api/src/jobify_api/pagination.py
git mv core/src/jobify/routes           api/src/jobify_api/routes
git mv core/src/jobify/middleware       api/src/jobify_api/middleware
git mv core/src/jobify/auth             api/src/jobify_api/auth
git mv core/src/jobify/dsr              api/src/jobify_api/dsr
git mv core/src/jobify/employers        api/src/jobify_api/employers
git mv core/src/jobify/scripts          api/src/jobify_api/scripts
# api package marker:
[ -f api/src/jobify_api/__init__.py ] || : > api/src/jobify_api/__init__.py
```

- [ ] **Step 2: Extract the FastAPI request-deps into `api/src/jobify_api/dependencies.py`**

In `core/src/jobify/db/session.py`: remove `from fastapi import Request` and the `get_session(request: Request)` function (keep `create_engine_from_settings`, `make_sessionmaker`, and any engine/sessionmaker accessors — those are domain). In `core/src/jobify/integrations/storage/base.py`: remove `from fastapi import Request` and the `get_storage(request: Request)` function (keep the `Storage` protocol). Create `api/src/jobify_api/dependencies.py` holding both, reading from `request.app.state` exactly as before:

```python
from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import Request
if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from sqlalchemy.ext.asyncio import AsyncSession
    from jobify.integrations.storage.base import Storage

async def get_session(request: Request) -> "AsyncIterator[AsyncSession]":
    sessionmaker = request.app.state.db_sessionmaker
    async with sessionmaker() as session:
        yield session

def get_storage(request: Request) -> "Storage":
    return request.app.state.storage
```
(Match the exact original bodies — recover via `git show HEAD:api/src/jobify/db/session.py` and `…/storage/base.py`. If `get_session`/`get_storage` had different signatures/yield semantics, preserve them verbatim.)

- [ ] **Step 3: Rewrite imports of the moved api modules**

Across `api/src/jobify_api` AND `tests/`, rewrite `jobify.<apimod>` → `jobify_api.<apimod>` for the moved modules, and repoint the two deps:

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
APIMODS='app_factory|main|pagination|routes|middleware|auth|dsr|employers|scripts'
# from jobify.X  /  import jobify.X   (X in APIMODS)
grep -rlE "(from|import) jobify\.($APIMODS)\b" api/src/jobify_api tests | xargs sed -i '' -E "s/(from|import) jobify\.($APIMODS)/\1 jobify_api.\2/g"
# get_session / get_storage now come from jobify_api.dependencies (were jobify.db.session / jobify.integrations.storage.base)
grep -rlE "from jobify\.db\.session import .*get_session" api/src/jobify_api tests | xargs sed -i '' -E "s/from jobify\.db\.session import get_session/from jobify_api.dependencies import get_session/g"
grep -rlE "from jobify\.integrations\.storage\.base import .*get_storage" api/src/jobify_api tests | xargs sed -i '' -E "s/from jobify\.integrations\.storage\.base import get_storage/from jobify_api.dependencies import get_storage/g"
```
Then manually inspect any `get_session`/`get_storage` import that was bundled with other names on one line (e.g. `from jobify.db.session import get_session, make_sessionmaker`) — split it so `make_sessionmaker` stays from `jobify.db.session` and `get_session` comes from `jobify_api.dependencies`. Grep to find them: `grep -rn "get_session\|get_storage" api/src/jobify_api tests | grep "import"`.

- [ ] **Step 4: Create `api/pyproject.toml` and move script entry points**

```toml
[project]
name = "jobify-api"
version = "0.1.0"
description = "Jobify API service"
requires-python = ">=3.12,<3.13"
dependencies = [
    "jobify-core",
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.32,<0.33",
    "python-multipart>=0.0.12,<0.1",
    "pyjwt[crypto]>=2.10.1,<3",
    "httpx>=0.28.1,<1",
]

[project.scripts]
jobify-seed-jobs = "jobify_api.scripts.seed_jobs:main"
jobify-seed-consents = "jobify_api.scripts.seed_consents:main"
jobify-grant-admin = "jobify_api.scripts.grant_admin:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jobify_api"]

[tool.uv.sources]
jobify-core = { workspace = true }
```
Remove `[project.scripts]` from `core/pyproject.toml`, and remove now-api-only deps (`fastapi`, `uvicorn`, `python-multipart`, `pyjwt`, `httpx`) from `core/pyproject.toml`'s `dependencies`. Add `"api"` to the root `[tool.uv.workspace] members` and `jobify-api` to the root dev group (so tests can import it) + `[tool.uv.sources] jobify-api = { workspace = true }`.

- [ ] **Step 5: Sync + import smoke**

```bash
rm -rf .venv && uv sync
uv run python -c "import jobify, jobify_api.app_factory, jobify_api.dependencies; from jobify_api.app_factory import create_app; create_app(); print('api OK')"
# prove no api->core leak remained as jobify.<apimod>:
grep -rnE "jobify\.(routes|app_factory|middleware|auth|dsr|employers|pagination|scripts)\b" core/src && echo "!! core still references api mods" || echo "clean: no api refs in core"
```
Expected: import prints `api OK`; core has no api refs.

- [ ] **Step 6: Full verification suite (root)**

```bash
uv run ruff check core/src api/src tests && uv run ruff format --check core/src api/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration
```
Expected: all green. Fix any straggler import (e.g. a test importing `jobify.app_factory`) by repointing to `jobify_api.*`. Verify the seeder path still resolves `core/data/sample_jobs.json` (run `uv run jobify-seed-jobs --dry-run`).

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(api): carve jobify_api package out of core"
```

---

### Task 3: Carve `jobify_worker` out of core into `worker/` (Celery split + dispatch rewire)

Move the worker tasks to `worker/src/jobify_worker/`, split `celery_app.py` (bare app → core; engine/signals/providers → worker `runtime.py`; add `worker_app.py` entry), rewire the 4 api dispatch sites to `jobify.celery_app.enqueue`, and update the test fixtures' patch targets.

**Files:**
- Create: `worker/pyproject.toml`, `worker/src/jobify_worker/__init__.py`, `worker/src/jobify_worker/runtime.py`, `worker/src/jobify_worker/worker_app.py`, `worker/README.md`, `core/src/jobify/celery_app.py`
- Move: `core/src/jobify/workers/tasks` → `worker/src/jobify_worker/tasks`; delete `core/src/jobify/workers/` after extracting celery_app contents
- Modify: the 4 dispatch sites in `api/src/jobify_api/{scripts/seed_jobs.py,routes/resumes.py,routes/applicants.py,routes/jobs.py}`; worker task imports; `tests/` fixtures (`patched_embedding_provider`, `patched_match_explainer`) + worker test imports; root workspace pyproject (add `worker`)

**Interfaces:**
- Consumes: core domain (`jobify.*`) + `jobify.celery_app.celery_app`/`settings`/`enqueue`.
- Produces: `jobify.celery_app.enqueue(name, *args)`; `jobify_worker.worker_app` (the `-A` target); `jobify_worker.runtime.{get_session_maker,get_embedding_provider,get_email_channel,get_match_explainer}`.

- [ ] **Step 1: Create the bare core Celery app `core/src/jobify/celery_app.py`**

Extract the broker/config half of the old `core/src/jobify/workers/celery_app.py`:

```python
"""Bare shared Celery app: broker/backend + routing + config. No task imports,
no worker-runtime signals, no provider singletons (those live in jobify_worker)."""
from __future__ import annotations
from celery import Celery
from jobify.settings import Settings

settings = Settings()

celery_app = Celery("jobify", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="parse",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    task_routes={
        "jobify.parse_resume": {"queue": "parse"},
        "jobify.embed_applicant": {"queue": "embed"},
        "jobify.embed_job": {"queue": "embed"},
        "jobify.score_applicant": {"queue": "score"},
        "jobify.score_job": {"queue": "score"},
        "jobify.sweep_notifications": {"queue": "notify"},
    },
)

def enqueue(name: str, *args: object) -> None:
    """Fire-and-forget dispatch by task name (producers never import task code)."""
    celery_app.send_task(name, args=list(args))
```
(Copy the exact `conf.update` values from the old celery_app — match `task_default_queue`, `result_expires`, etc. verbatim.)

- [ ] **Step 2: Move tasks + create `jobify_worker/runtime.py`**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
mkdir -p worker/src/jobify_worker
git mv core/src/jobify/workers/tasks worker/src/jobify_worker/tasks
[ -f worker/src/jobify_worker/__init__.py ] || : > worker/src/jobify_worker/__init__.py
```
Create `worker/src/jobify_worker/runtime.py` with the per-worker engine + signals + provider getters extracted verbatim from the old celery_app (the `_engine`/`_sessionmaker` globals, `_init_engine`/`_dispose_engine` connected to `worker_process_init`/`worker_shutting_down`, `get_session_maker`, `get_embedding_provider`, `get_email_channel`, `get_match_explainer`, and the `_gemini_api_key_or_raise` helper). It imports `settings` from `jobify.celery_app` (`from jobify.celery_app import settings`) and `NullPool` from sqlalchemy; domain imports (`jobify.db.session`, `jobify.integrations.*`, `jobify.scoring.*`) are unchanged. Recover the exact bodies from `git show HEAD:api/src/jobify/workers/celery_app.py` (lines ~69–end).

- [ ] **Step 3: Create the worker entry `worker/src/jobify_worker/worker_app.py`**

```python
"""Celery worker entry: `celery -A jobify_worker.worker_app worker`.
Imports the shared app, registers all task modules, and wires runtime signals."""
from jobify.celery_app import celery_app  # noqa: F401  (the -A target)
from jobify_worker import runtime  # noqa: F401  (connects worker_process_init/shutdown signals on import)
from jobify_worker.tasks import (  # noqa: F401  (register tasks onto celery_app)
    parse,
    embed,
    embed_job,
    score_applicant,
    score_job,
    sweep_notifications,
)
```

- [ ] **Step 4: Rewrite worker task imports**

In `worker/src/jobify_worker/tasks/*.py`:
```bash
cd /Users/ahamadshah/ahamed_personal/jobify
T=worker/src/jobify_worker/tasks
# celery_app + settings now come from core jobify.celery_app:
grep -rlE "from jobify\.workers\.celery_app import" $T | xargs sed -i '' -E "s/from jobify\.workers\.celery_app import/from jobify.celery_app import/g"
# but get_session_maker / providers come from jobify_worker.runtime, NOT jobify.celery_app — fix those names:
```
Then manually fix each task's import line so that:
- `celery_app`, `settings` ← `from jobify.celery_app import celery_app, settings`
- `get_session_maker`, `get_embedding_provider`, `get_email_channel`, `get_match_explainer` ← `from jobify_worker.runtime import …`
- intra-worker task refs (`from jobify.workers.tasks.X import Y`) → `from jobify_worker.tasks.X import Y`:
```bash
grep -rlE "jobify\.workers\.tasks" $T | xargs sed -i '' -E "s/jobify\.workers\.tasks/jobify_worker.tasks/g"
```
Audit each task file's final imports by hand (the sed handles bulk; the split between `jobify.celery_app` and `jobify_worker.runtime` is the part that needs eyes). Then delete the now-empty `core/src/jobify/workers/`:
```bash
git rm -r core/src/jobify/workers
```

- [ ] **Step 5: Rewire the 4 api dispatch sites**

In `api/src/jobify_api/`:
- `scripts/seed_jobs.py`: `from jobify.workers.tasks.embed_job import embed_job; embed_job.delay(str(jid))` → `from jobify.celery_app import enqueue; enqueue("jobify.embed_job", str(jid))`
- `routes/resumes.py`: `from jobify.workers.tasks.parse import parse_resume; parse_resume.delay(str(resume.id))` → `from jobify.celery_app import enqueue; enqueue("jobify.parse_resume", str(resume.id))`
- `routes/applicants.py`: `score_applicant.delay(str(applicant_id))` → `enqueue("jobify.score_applicant", str(applicant_id))` (import `enqueue` from `jobify.celery_app`)
- `routes/jobs.py` (×2): `embed_job.delay(str(job.id))` → `enqueue("jobify.embed_job", str(job.id))`

Keep the surrounding broad `try/except` + `dispatch.failed`/`embed.dispatch-failed` logging exactly as-is (the spec's fire-and-forget contract). Verify none remain:
```bash
grep -rnE "from jobify\.workers|\.delay\(" api/src/jobify_api && echo "!! api still imports worker tasks" || echo "clean: api dispatches by name only"
```

- [ ] **Step 6: `worker/pyproject.toml` + workspace + test fixtures**

```toml
[project]
name = "jobify-worker"
version = "0.1.0"
description = "Jobify Celery worker"
requires-python = ">=3.12,<3.13"
dependencies = ["jobify-core"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jobify_worker"]

[tool.uv.sources]
jobify-core = { workspace = true }
```
Add `"worker"` to root `[tool.uv.workspace] members`, `jobify-worker` to the root dev group, and `[tool.uv.sources] jobify-worker = { workspace = true }`.

Update the test fixtures (in `tests/`): the `patched_embedding_provider` fixture patches three module references of `get_embedding_provider` — now `jobify_worker.runtime` (canonical) + `jobify_worker.tasks.embed` + `jobify_worker.tasks.embed_job` (by-name imports). The `patched_match_explainer` fixture patches `jobify_worker.runtime` + the modules importing it by name (grep `tests/` for the old `jobify.workers.celery_app`/`jobify.workers.tasks` patch targets and repoint). The eager fixture must import `jobify_worker.tasks` (or `jobify_worker.worker_app`) so tasks register on the shared app:
```bash
grep -rnE "jobify\.workers" tests
```
Repoint every hit: `jobify.workers.celery_app` → `jobify.celery_app` (for `celery_app`/`settings`/`enqueue`) or `jobify_worker.runtime` (for providers/session maker), and `jobify.workers.tasks.X` → `jobify_worker.tasks.X`.

- [ ] **Step 7: Sync + import smoke + dispatch sanity**

```bash
rm -rf .venv && uv sync
uv run python -c "import jobify.celery_app, jobify_worker.worker_app, jobify_worker.runtime; from jobify.celery_app import enqueue; print('worker OK')"
grep -rnE "jobify\.workers" core/src api/src worker/src tests && echo "!! stale jobify.workers ref" || echo "clean: no jobify.workers refs anywhere"
```
Expected: `worker OK`; no `jobify.workers` references remain.

- [ ] **Step 8: Full verification suite + worker smoke**

```bash
uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"     # exercises eager dispatch via enqueue
uv run pytest -v -s -m eval
uv run pytest -v -m integration
# live worker smoke (needs Redis): starts, connects, logs ready
cd worker && timeout 15 uv run --env-file=../.env celery -A jobify_worker.worker_app worker --pool=solo -Q parse,embed,score,notify --loglevel=info 2>&1 | grep -m1 "ready" && echo "WORKER SMOKE OK"; cd ..
```
Expected: all suites green (the eager-mode unit/integration tests prove `enqueue` dispatches correctly through the shared app); worker logs `celery@… ready`. If eager dispatch tests fail with "Task of kind jobify.X is not registered", ensure the eager fixture imports `jobify_worker.tasks` so registration happens in-process.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "refactor(worker): carve jobify_worker package; Celery app in core; dispatch by name"
```

---

### Task 4: Docs, CI, memory, and final verification

**Files:**
- Modify: root `CLAUDE.md`; `api/README.md`, `worker/README.md` (new), `frontend/README.md`; CI workflow `.github/workflows/api.yml`; project memory files
- Create: `worker/README.md`, `.env.example` at root (if not already moved)

- [ ] **Step 1: CI — update `.github/workflows/api.yml`**

Repoint the workflow's working-directory/commands from `api/` to the workspace root: `uv sync` at root; lint/type/test commands become `uv run ruff check core/src api/src worker/src tests`, `uv run ruff format --check …`, `uv run mypy`, `uv run pytest -v -m "not integration and not eval"`, `uv run pytest -v -s -m eval`, `uv run pytest -v -m integration`. Update any `working-directory: api` to the repo root and the alembic step to `cd core && uv run alembic upgrade head` (or root with `-c core/alembic.ini`). Confirm the `paths:` trigger filter includes `core/**`, `api/**`, `worker/**`, `tests/**`, and the workflow file itself.

- [ ] **Step 2: `worker/README.md`**

```markdown
# Jobify Worker

Celery daemon (`jobify_worker`). Shares the domain via the `jobify` core package;
the Celery app config lives in `core` (`jobify.celery_app`). Task code is here.

## Run (from repo root, needs Redis + root .env)

    uv run --env-file=.env celery -A jobify_worker.worker_app worker \
        --pool=solo --concurrency=1 -Q parse,embed,score,notify --loglevel=info

## Beat (scheduler) — INERT today

No periodic tasks are scheduled yet (no beat_schedule). When one is added:

    uv run --env-file=.env celery -A jobify_worker.worker_app beat --loglevel=info

Queues: parse, embed, score, notify. The api dispatches via
`jobify.celery_app.enqueue("jobify.<task>", …)` (by name).
```

- [ ] **Step 3: `api/README.md` + `frontend/README.md`**

In `api/README.md` (moved from core in Task 2, or recreate): update run/test commands to run from repo root via `uv`; point the worker run command at `worker/README.md`; note migrations run from `core/` (`cd core && uv run alembic upgrade head`); update the `.env` location to repo root; note email templates at `core/emails/`. In `frontend/README.md`: update the styleguide line to `frontend/styleguide/`.

- [ ] **Step 4: Root `CLAUDE.md`**

Update "What this repo is" + "Commands + setup": three backend packages in a uv workspace (`core/` = `jobify` domain; `api/` = `jobify_api`; `worker/` = `jobify_worker`); the workspace root holds `pyproject.toml` + tests; `.env` at root; alembic in `core/`; CI verbatim commands run from root. Note `worker/` is the daemon; the Celery app lives in `jobify.celery_app`; dispatch is by task name. Keep it terse; preserve the existing invariant sections (their import paths: `jobify.db.*`, `jobify.integrations.*` are unchanged; route/auth references become `jobify_api.*`, worker references `jobify_worker.*` — update the few code-path mentions that name moved modules).

- [ ] **Step 5: Project memory**

Update `/Users/ahamadshah/.claude/projects/-Users-ahamadshah-ahamed-personal-jobify/memory/`: revise `jobify-web-frontends.md` only if it mentions styleguide path; add a concise `jobify-backend-workspace.md` (three packages, import names, Celery-app-in-core, dispatch-by-name, .env at root, run/test from root) and a one-line `MEMORY.md` pointer. Read existing files first to match frontmatter.

- [ ] **Step 6: Final clean verification from scratch**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
rm -rf .venv uv.lock && uv sync
uv run ruff check core/src api/src worker/src tests
uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration
git status --short   # only intended changes
```
Expected: clean install + all green. `frontend` untouched (`cd frontend && npm run build` still clean — spot check).

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "docs(repo): workspace docs, CI, and memory for core/api/worker split"
```

---

## Self-Review

**1. Spec coverage:**
- uv workspace + 3 packages (`jobify`/`jobify_api`/`jobify_worker`) → Tasks 1–3. ✅
- Module split (core/api/worker authoritative lists) → Task 1 (relocate), Task 2 (api carve), Task 3 (worker carve). ✅
- Celery app in core (bare) + worker registers tasks/signals + `enqueue` dispatch by name → Task 3 Steps 1–5. ✅
- No core→api / api↔worker edges → Task 2 Step 5 grep, Task 3 Step 5/7 greps. ✅
- FastAPI request-deps extracted (`get_session`/`get_storage`) → Task 2 Step 2. ✅
- Dep split (core vs api vs worker) → Task 2 Step 4, Task 3 Step 6. ✅
- Relocations: alembic→core (Task 1 Step 4), emails→core (Task 1 Step 1), styleguide→frontend (Task 1 Step 1), .env→root (Task 1 Step 1), tests→root (Task 1 Step 1). ✅
- Eager-mode dispatch + fixture patch-target updates → Task 3 Step 6, Step 8. ✅
- Docs/CI/memory → Task 4. ✅
- Verification = existing suite green throughout → every task's Step 6/8. ✅

**2. Placeholder scan:** No TBD/TODO. Where file bodies move unchanged, exact `git mv` + `git show HEAD:<path>` recovery is given. The mypy/pytest config copy in Task 1 Step 3 references the verbatim source (`git show HEAD:api/pyproject.toml`).

**3. Type/name consistency:** `jobify.celery_app` exposes `celery_app`, `settings`, `enqueue` (Task 3 Step 1) — consumed verbatim in Task 3 Steps 3–5. `jobify_worker.runtime` exposes `get_session_maker`/`get_embedding_provider`/`get_email_channel`/`get_match_explainer` (Step 2) — consumed in Step 4 task-import fixes and Step 6 fixtures. `jobify_api.dependencies` exposes `get_session`/`get_storage` (Task 2 Step 2) — consumed in Step 3 rewrite. `enqueue("jobify.<task>", …)` names match the `task_routes` keys and the `@celery_app.task(name=…)` registrations.
