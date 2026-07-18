# Jobify Worker

Celery daemon (`jobify_worker`). Shares domain code via `jobify`; worker-only
settings, Celery routing/beat configuration, runtime factories, and tasks live here.

## Run (from repo root, needs Redis + root .env)

    uv run --env-file=.env celery -A jobify_worker.worker_app worker \
        --pool=solo --concurrency=1 -Q parse,embed,score,notify,outbox --loglevel=info

- `--pool=solo`: single-concurrency for MVP. Switch to `--pool=prefork` when load justifies parallelism.
- `-Q parse,embed,score,notify,outbox`: consume from all queues. Pin a second worker to a single queue for isolation.

## Beat (scheduler)

`sweep_notifications` runs every `JOBIFY_NOTIFY_SWEEP_INTERVAL_SECONDS` seconds
(default 60) via `celery_app.conf.beat_schedule`. Beat must run as its own
process alongside the worker — it only enqueues, it doesn't execute:

    uv run --env-file=.env celery -A jobify_worker.worker_app beat --loglevel=info

`sweep_outbox` runs every `JOBIFY_OUTBOX_SWEEP_INTERVAL_SECONDS` seconds
(default 5). API and worker transactions write task dispatch and blob cleanup
intents to `outbox_events`; the sweeper delivers them with leases and retries.
After fixing the cause of terminal failures, requeue them with:

    uv run --env-file=.env jobify-requeue-outbox --dry-run
    uv run --env-file=.env jobify-requeue-outbox --limit 100

## Queues

| Queue    | Tasks                                          |
|----------|------------------------------------------------|
| `parse`  | `jobify.parse_resume`                          |
| `embed`  | `jobify.embed_applicant`, `jobify.embed_job`   |
| `score`  | `jobify.score_applicant`, `jobify.score_job`   |
| `notify` | `jobify.sweep_notifications`                   |
| `outbox` | `jobify.sweep_outbox`                         |

The API and pipeline tasks persist task-name + args in `outbox_events` in the
same database transaction as the business change. `sweep_outbox` publishes the
task by name. Task routing is configured in `worker/src/jobify_worker/celery_app.py`.

## Dependencies

- **Redis** (`JOBIFY_REDIS_URL`) — broker + result backend. Run `brew services start redis` locally.
- **Root `.env`** — all `JOBIFY_*` vars read from `.env` at repo root (pass via `--env-file=.env`).
- **Postgres** — tasks open their own DB connections via `NullPool` (fresh asyncio loop per task).

## Worker configuration

In addition to database, Redis, storage, and logging variables in `.env`:

| Variable | Default | Purpose |
|---|---:|---|
| `JOBIFY_TASK_SOFT_TIME_LIMIT_SECONDS` | `240` | Celery cooperative task deadline |
| `JOBIFY_TASK_TIME_LIMIT_SECONDS` | `300` | Celery hard task deadline |
| `JOBIFY_PROVIDER_CONNECT_TIMEOUT_SECONDS` | `5` | Gemini/AWS connection deadline |
| `JOBIFY_PROVIDER_READ_TIMEOUT_SECONDS` | `30` | Gemini/AWS response deadline |
| `JOBIFY_NOTIFY_BATCH_SIZE` | `50` | Notifications claimed per sweep |
| `JOBIFY_NOTIFY_SWEEP_INTERVAL_SECONDS` | `60` | Notification beat interval |
| `JOBIFY_NOTIFY_LEASE_SECONDS` | `300` | Dispatch lease before crash recovery |
| `JOBIFY_NOTIFY_MAX_ATTEMPTS` | `5` | Notification terminal-failure threshold |
| `JOBIFY_OUTBOX_BATCH_SIZE` | `100` | Durable events claimed per sweep |
| `JOBIFY_OUTBOX_SWEEP_INTERVAL_SECONDS` | `5` | Durable outbox beat interval |
| `JOBIFY_OUTBOX_LEASE_SECONDS` | `300` | Outbox processing lease |
| `JOBIFY_OUTBOX_MAX_ATTEMPTS` | `10` | Outbox terminal-failure threshold |
| `JOBIFY_SCORE_BATCH_SIZE` | `100` | Applicant/job pairs processed per task batch |

`JOBIFY_GEMINI_API_KEY` is required for Gemini embeddings or the LLM explainer.
SES additionally requires `JOBIFY_EMAIL_CHANNEL=ses` and a verified
`JOBIFY_EMAIL_FROM_ADDRESS`.

## Eager mode (tests)

Set `JOBIFY_CELERY_TASK_ALWAYS_EAGER=true` to run tasks synchronously in-process (no Redis required).
Used by integration test fixtures; never set in production.
