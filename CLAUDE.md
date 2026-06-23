# CLAUDE.md

Guidance for Claude Code working in this repo. **This root file is intentionally minimal** — package-specific invariants live in per-package `CLAUDE.md` files, each auto-loaded when you work in that subtree:

| File | Covers |
|------|--------|
| `core/CLAUDE.md` | `jobify` domain package — soft-delete model, audit logs, consent, DSR data, parse-F1 eval, seeding, match explainer |
| `api/CLAUDE.md` | `jobify_api` FastAPI — app wiring, middleware, error handling, auth/JWT, resume/feed/applications/recruiter/admin/DSR route invariants |
| `worker/CLAUDE.md` | `jobify_worker` Celery — parse, embed, score, notifications-sweep tasks + runtime |
| `tests/CLAUDE.md` | test harness — conftests, markers, savepoint isolation, the three HTTP clients |
| `app/CLAUDE.md` | Flutter client (iOS/Android/web) |
| `frontend/CLAUDE.md` | unified Vite + React web app (three HashRouter surfaces) |

When working across packages, read the relevant package file(s) — a single session loads every file whose subtree it touches.

## What this repo is

Jobify — an early-stage placement platform.

- **Backend — uv workspace (3 packages, all from repo root):**
  - `core/` — `jobify` domain package. DB models + Alembic migrations (`core/alembic.ini`), integrations (storage, parser, embeddings, email, scoring, explainer), consent/DSR/audit, seeding CLI, Celery bare app (`jobify.celery_app`). Email templates at `core/emails/`.
  - `api/` — `jobify_api` FastAPI service. App factory, routes, auth, middleware, DSR/admin routes, employer/invite routes. Entry point `jobify_api.main:app`. Scripts: `jobify-seed-jobs`, `jobify-seed-consents`, `jobify-grant-admin`.
  - `worker/` — `jobify_worker` Celery daemon. Tasks (parse, embed, score, sweep_notifications), runtime singletons, worker entry point `jobify_worker.worker_app`. See `worker/README.md`.
  - `tests/` — all tests at repo root (`tests/unit/`, `tests/integration/`, `tests/eval/`).
  - Root `pyproject.toml` is the workspace (`[tool.uv.workspace] members = [core, api, worker]`). `.env` lives at repo root.
- `IMPLEMENTATION_SPEC.md` — **how** we build it (engineering spec, v0.2 MVP-first).
- `docs/prd/KPA_Enhanced_BRD_v1_1.pdf` — **what** we build (product BRD; scope source of truth).
- `docs/superpowers/specs/` — per-slice design docs (the **why** behind each invariant). Their spent step-by-step build plans were removed once shipped — recoverable from git history if ever needed.
- `app/` — Flutter mobile + web client. The spec overrides the BRD's React Native + Next.js stack.
- `frontend/` — unified Vite + React + TS web app; three route-prefixed surfaces under one HashRouter (`/` applicant/public, `/employers` recruiter marketing, `/console` admin + recruiter ops). `npm run build` = `tsc -b && vite build`. See `frontend/README.md` for the surface→route/file map. Static `frontend/styleguide/` has no build step.

Scope vs "how" conflict: BRD wins on product behavior; spec wins on tech.

## Commands + setup

All backend commands run from the **repo root** (`pyproject.toml` + `uv.lock` live there). `.env` at repo root. **Operational reference in READMEs** — `api/README.md` (run, tests, migrations, DB/Redis/pgvector setup, seeding, full `JOBIFY_*` env-var table, endpoint docs), `worker/README.md` (worker run + beat command, queues), `app/README.md` (Flutter run/test, web OAuth origins), `frontend/README.md` (Vite dev/build, env vars, surface→route map). Boot rules:

- App refuses to boot if a required `JOBIFY_*` var is missing/invalid (`settings.py` in `jobify_api`); `JOBIFY_DB_URL` **must** use `postgresql+asyncpg://` (enforced in `Settings._enforce_async_driver`).
- Integration fixtures inject `JOBIFY_JWT_SECRET="x"*32` + `JOBIFY_GOOGLE_OAUTH_CLIENT_IDS=test.apps.googleusercontent.com` — match these for new apps under test.
- **Alembic runs from `core/`:** `cd core && uv run alembic upgrade head` (alembic.ini lives in `core/`).
- **Worker runs from repo root:** `uv run --env-file=.env celery -A jobify_worker.worker_app worker --pool=solo --concurrency=1 -Q parse,embed,score,notify --loglevel=info`. Dispatch by task name via `jobify.celery_app.enqueue("jobify.<task>", …)`.
- **CI verbatim** (run these exact commands from repo root before claiming green) — backend: `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -s -m eval` · `uv run pytest -v -m integration`; app: `dart format --set-exit-if-changed lib test` · `flutter analyze` · `flutter test`.

## Conventions (apply everywhere)

- **uv only** (don't `pip install` — bypasses `uv.lock`). **No Docker for MVP** (Homebrew `postgresql@16`).
- **Soft delete everywhere** — every domain table has `deleted_at TIMESTAMPTZ NULL`; live queries filter `deleted_at IS NULL`; uniqueness via partial indexes `WHERE deleted_at IS NULL`; reuse the `Annotated` types in `db/models.py`. Full rules (incl. the `AuditLog` exception) in `core/CLAUDE.md`.
- **Hand-written migrations** in `core/src/jobify/db/migrations/versions/` (autogenerate off; excluded from mypy). Edit the revision before `upgrade head`.
- **structlog only** — `structlog.get_logger(__name__)`, context as kwargs; no `print`/`logging.getLogger`. `JOBIFY_LOG_FORMAT=json` for prod.
- **All handlers `async def`.** Versioned routes under `/v1` except bare `/health` + `/ready` (probes). SQLAlchemy models are never response schemas (see `api/CLAUDE.md`).
- **Branch workflow → `WORKFLOW.md`.** One short-lived branch per feature off latest `origin/main`; `scripts/new-feature.sh <name>` to start, `scripts/sync-with-main.sh` to reconcile after a squash-merge (it auto-`rebase --onto`s past already-merged commits — never restack new work on a merged branch).
- **Doc ownership.** Operational content (commands, env vars, setup, endpoint docs) → READMEs; code-invariants → the relevant package `CLAUDE.md` ("why it's shaped this way / what breaks if changed") with a spec pointer per section; rationale → `docs/superpowers/specs/`. Keep each `CLAUDE.md` well under 40k — every file in a touched subtree is loaded into context and truncates silently past the limit.
