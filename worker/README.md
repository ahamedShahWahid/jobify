# Jobify Worker

Celery daemon (`jobify_worker`). Shares the domain via the `jobify` core package;
the Celery app config lives in `core` (`jobify.celery_app`). Task code is here.

## Run (from repo root, needs Redis + root .env)

    uv run --env-file=.env celery -A jobify_worker.worker_app worker \
        --pool=solo --concurrency=1 -Q parse,embed,score,notify --loglevel=info

- `--pool=solo`: single-concurrency for MVP. Switch to `--pool=prefork` when load justifies parallelism.
- `-Q parse,embed,score,notify`: consume from all queues. Pin a second worker to a single queue for isolation.

## Beat (scheduler) — INERT today

No periodic tasks are scheduled yet (no beat_schedule). When one is added:

    uv run --env-file=.env celery -A jobify_worker.worker_app beat --loglevel=info

## Queues

| Queue    | Tasks                                          |
|----------|------------------------------------------------|
| `parse`  | `jobify.parse_resume`                          |
| `embed`  | `jobify.embed_applicant`, `jobify.embed_job`   |
| `score`  | `jobify.score_applicant`, `jobify.score_job`   |
| `notify` | `jobify.sweep_notifications`                   |

The api dispatches via `jobify.celery_app.enqueue("jobify.<task>", …)` (by task name).
Task routing is configured in `core/src/jobify/celery_app.py`.

## Dependencies

- **Redis** (`JOBIFY_REDIS_URL`) — broker + result backend. Run `brew services start redis` locally.
- **Root `.env`** — all `JOBIFY_*` vars read from `.env` at repo root (pass via `--env-file=.env`).
- **Postgres** — tasks open their own DB connections via `NullPool` (fresh asyncio loop per task).

## Eager mode (tests)

Set `JOBIFY_CELERY_TASK_ALWAYS_EAGER=true` to run tasks synchronously in-process (no Redis required).
Used by integration test fixtures; never set in production.
