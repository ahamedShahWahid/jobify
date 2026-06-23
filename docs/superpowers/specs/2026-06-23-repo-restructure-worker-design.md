# Repo restructure — `worker/` daemon folder + 3 product folders — design

**Date:** 2026-06-23
**Status:** Approved (design); implementation plan to follow.

## Goal

Make the repo root cleanly express its parts: three product folders (`api`, `app`,
`frontend`) plus an explicit top-level home for the background daemon(s)
(`worker/`). Relocate the two stray static web dirs (`emails/`, `styleguide/`) to
their functional homes so the root isn't cluttered.

This is an **organizational reorg with no code-behavior change** — no new features,
no logic changes. The only edits beyond file moves are repointing path references
(all in docs today) and adding thin shell entrypoints + READMEs.

## Decisions taken during brainstorming

- **Driver = clearer org** (not an independent deployable, not a shared-core split).
  One Python package (`jobify`); the worker is a separate deployable *entrypoint*,
  not separate code.
- **Daemon layout = top-level `worker/` entrypoint.** The heavy task code STAYS in
  the `jobify` package (`api/src/jobify/workers/`) because it is domain code — it
  imports `jobify.db.models`, `jobify.scoring.*`, `jobify.integrations.*`,
  `jobify.settings`, `jobify.consent`, `jobify.db.session`. `worker/` holds only the
  run/deploy surface.
- **`emails/` → `api/emails/`** — server-rendered templates mailed by the
  notification system; their eventual consumer is the email channel in
  `jobify.integrations.email` (SES later). Keeping them in `api/` keeps the backend
  self-contained.
- **`styleguide/` → `frontend/styleguide/`** — a static brand/design reference;
  belongs with the web frontend. Stays standalone static (NOT part of the Vite
  build).
- **Include an inert `run-beat.sh` now** — the "schedulers/cron" surface made
  explicit, documented as inert until a `beat_schedule` is defined (no feature
  invented).

## Current state (why this is low-risk)

- Worker code: `api/src/jobify/workers/celery_app.py` + `tasks/{parse,embed,embed_job,
  score_applicant,score_job,sweep_notifications}.py`. Deeply coupled to the `jobify`
  package — must stay in it.
- No `beat_schedule` is configured today; `sweep_notifications` is dispatched on the
  `notify` queue but not periodically scheduled.
- The ONLY live references to `emails/` / `styleguide/` paths are in docs:
  `CLAUDE.md`, `frontend/README.md`, `emails/README.md`, `styleguide/README.md`.
  No Python/TS code loads from either dir (the notification email channel is the
  `LoggingEmailChannel` stub — it logs, it does not read templates yet).

## Target root layout

```
api/                FastAPI service — the jobify package (code location UNCHANGED)
  src/jobify/workers/   task code stays here (parse, embed, score, sweep, celery_app)
  emails/               ← moved from repo root
app/                Flutter client (unchanged)
frontend/           unified Vite web app (unchanged)
  styleguide/           ← moved from repo root
worker/             ← NEW daemon run-surface (entrypoints + README, no domain code)
docs/  scripts/     tooling (unchanged)
```

## Components

### `worker/` (new)

- **`worker/run-worker.sh`** — wraps the canonical worker command, executed from the
  `api/` workspace so `uv`, `.env`, and the `jobify` package resolve:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  cd "$(dirname "$0")/../api"
  exec uv run --env-file=.env celery -A jobify.workers.celery_app worker \
      --pool=solo --concurrency=1 -Q parse,embed,score,notify --loglevel=info
  ```
- **`worker/run-beat.sh`** — Celery beat entrypoint, same `cd api` + `uv run` shape,
  `celery -A jobify.workers.celery_app beat --loglevel=info`. INERT today (no
  periodic tasks scheduled); the README says so explicitly.
- **`worker/README.md`** — run instructions (worker + beat), the `parse,embed,score,
  notify` queue list, the Redis + `api/.env` dependency, and a pointer: "task code
  lives in `api/src/jobify/workers/`; this folder is the run/deploy surface only."
- Both scripts are `chmod +x`.

### Moves

- `git mv emails api/emails`
- `git mv styleguide frontend/styleguide`
- Repoint the doc references found in the pre-scan:
  - `CLAUDE.md` "What this repo is" — add `worker/`, relocate emails/styleguide
    mentions (emails under `api/`, styleguide under `frontend/`).
  - `frontend/README.md:33` — `styleguide/` → `frontend/styleguide/`.
  - `emails/README.md` (now `api/emails/README.md`) — `open emails/…` →
    `open api/emails/…`.
  - `styleguide/README.md` (now `frontend/styleguide/README.md`) — `open
    styleguide/…` → `open frontend/styleguide/…`.

### Doc updates

- `api/README.md` — replace the inline worker run command with a pointer to
  `worker/run-worker.sh` (and mention `worker/run-beat.sh`); note `api/emails/`.
- Root `CLAUDE.md` — structure section reflects the new root + `worker/`.
- Project memory — `jobify-web-frontends.md` (styleguide now under frontend) + a
  short worker-structure note; update `MEMORY.md` pointers.

## Out of scope

- Defining an actual `beat_schedule` / periodic tasks (run-beat.sh stays inert).
- Any change to worker task logic, queues, or the FastAPI app.
- Wiring the email channel to read `api/emails/` templates (SES work is separate).
- Containerization (Dockerfile/Procfile) — the README notes `worker/` as the future
  home, but none is added now.

## Verification (no behavior change — pure reorg)

- `git mv` preserves history; a grep proves zero dangling references to the old
  `emails/` / `styleguide/` paths in code, config, or docs.
- API unchanged → `uv run pytest -v -m "not integration and not eval"` green;
  `worker/run-worker.sh` smoke-starts and connects to Redis (logs `celery@… ready`).
- `frontend` unchanged → `npm run build` clean; `frontend/styleguide/index.html`
  still opens as static HTML.
