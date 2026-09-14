# Jobify Worker

Celery daemon (`jobify_worker`). Shares domain code via `jobify`; worker-only
settings, Celery routing/beat configuration, runtime factories, and tasks live here.

## Run (from repo root, needs Redis + root .env)

Two processes, not one — `scripts/start-all.sh` runs both:

    uv run --env-file=.env celery -A jobify_worker.worker_app worker \
        --pool=solo --concurrency=1 -Q parse,embed,score --hostname=worker-fast@%h

    uv run --env-file=.env celery -A jobify_worker.worker_app worker \
        --pool=solo --concurrency=1 -Q notify,outbox --hostname=worker-io@%h

- **Why split:** on one process across all five queues, a slow parse/score
  batch (a multi-second Gemini call, or a chained score continuation) blocks
  `notify`/`outbox` behind it — email delivery and dispatch of the *next*
  pipeline stage stall for that batch's full duration, since `sweep_outbox`
  (the only thing that publishes a staged task) can't run until the batch
  ahead of it in the same process finishes. Splitting keeps that small,
  latency-sensitive path off the queue that can carry a long provider call.
- `--hostname` gives each process a distinct Celery node name. Without it,
  two processes on the same host both default to `celery@<hostname>` —
  identical node names make `celery inspect`/`celery control` unable to
  target one process without the other.
- `--pool=solo`: single-concurrency for MVP. Switch to `--pool=prefork` when
  load justifies parallelism — note this also makes `task_soft_time_limit`/
  `task_time_limit` actually apply (the solo pool ignores them), but
  `task_acks_late=True` means a killed task on a degraded provider can be
  redelivered and re-attempt the same timeout; add a bounded-retry guard on
  the score tasks before flipping this in production.
- For a single first run, one process on all five queues also works — see
  `INSTALLATION.md` §4.8.
- Log level/format come from `JOBIFY_LOG_LEVEL`/`JOBIFY_LOG_FORMAT`; Celery's `--loglevel` has no effect once the `setup_logging` receiver is connected (`jobify_worker/observability.py`).

## Beat (scheduler)

`sweep_notifications` runs every `JOBIFY_NOTIFY_SWEEP_INTERVAL_SECONDS` seconds
(default 60) via `celery_app.conf.beat_schedule`. Beat must run as its own
process alongside the worker — it only enqueues, it doesn't execute:

    uv run --env-file=.env celery -A jobify_worker.worker_app beat

## Metrics

Opt-in Prometheus endpoint: set `JOBIFY_WORKER_METRICS_PORT` (e.g. `9101`) and scrape
`http://<host>:<port>/metrics`. It binds `JOBIFY_WORKER_METRICS_HOST` (default
`127.0.0.1`; the endpoint has no auth). For `--pool=prefork` (several processes) also
set `PROMETHEUS_MULTIPROC_DIR` to a directory **owned by the worker alone**; it
**must already exist and be emptied before the worker starts** — deploy entrypoints
own that (`scripts/start-all.sh` does it locally), never the worker itself. The
worker refuses to boot (raises during `worker_init`, before the port check) if this
is set but not an existing directory. In this mode the scrape carries only the
metrics this worker declares — no `process_*`/`python_gc_*`/`python_info` (those
come from the default single-process registry only).

`sweep_outbox` runs every `JOBIFY_OUTBOX_SWEEP_INTERVAL_SECONDS` seconds
(default 5). API and worker transactions write task dispatch and blob cleanup
intents to `outbox_events`; the sweeper delivers them with leases and retries.
Both durable sweepers claim one row immediately before its side effect, then
repeat up to the configured batch size. This prevents later rows from spending
their lease waiting behind a slow provider or broker call.
After fixing the cause of terminal failures, requeue them with:

    uv run --env-file=.env jobify-requeue-outbox --dry-run
    uv run --env-file=.env jobify-requeue-outbox --limit 100

`cleanup_outbox` runs every 86400 seconds. Each run loops batches of
`JOBIFY_OUTBOX_CLEANUP_BATCH_SIZE` (default 1000) until one comes back short,
deleting live `completed`/`failed` rows older than `JOBIFY_OUTBOX_RETENTION_DAYS`
(default 30 days) — a backlog too large to clear within
`JOBIFY_OUTBOX_CLEANUP_MAX_BATCHES` (default 1000) batches stops and logs a
warning rather than holding the `outbox` queue's worker indefinitely.

`cleanup_refresh_tokens` runs every 86400 seconds, same loop-until-empty shape.
Deletes naturally expired rows immediately and revoked rows after
`JOBIFY_REFRESH_TOKEN_RETENTION_DAYS` (default 7) — long enough past any
plausible attacker replay window to preserve the reuse-detection signal
`AuthService.refresh` relies on (a revoked row found on replay triggers family
revocation), short enough to bound the table's growth.

## Queues

| Queue    | Tasks                                                                    |
|----------|---------------------------------------------------------------------------|
| `parse`  | `jobify.parse_resume`                                                    |
| `embed`  | `jobify.embed_applicant`, `jobify.embed_job`                             |
| `score`  | `jobify.score_applicant`, `jobify.score_job`                             |
| `notify` | `jobify.sweep_notifications`                                             |
| `outbox` | `jobify.sweep_outbox`, `jobify.cleanup_outbox`, `jobify.cleanup_refresh_tokens` |

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
| `JOBIFY_OUTBOX_RETENTION_DAYS` | `30` | Terminal outbox retention before cleanup |
| `JOBIFY_OUTBOX_CLEANUP_BATCH_SIZE` | `1000` | Terminal rows physically deleted per cleanup run |
| `JOBIFY_SCORE_BATCH_SIZE` | `100` | Applicant/job pairs processed per task batch |
| `JOBIFY_RESUME_PARSER` | `llm` | Resume parser: `llm` (Gemini with library fallback) or `library` (deterministic, no network). Keyless + `llm` degrades to library with a warning. |
| `JOBIFY_RESUME_PARSER_MODEL` | `gemini-3.1-flash-lite` | Gemini model for resume parsing (chosen on the extraction yardstick, see `core/data/parse_eval/LLM_EVAL_REPORT.md`). |
| `JOBIFY_WORKER_METRICS_PORT` | unset (disabled) | Opt-in Prometheus scrape port for the worker (`1`-`65535`); unset disables the endpoint entirely. |
| `JOBIFY_WORKER_METRICS_HOST` | `127.0.0.1` | Bind host for the metrics endpoint. No auth — keep on loopback unless behind a private network. |

### Notification lease rollout

Migration `0023` keeps notification rows already in `dispatching` state and
quarantines them for 7,500 seconds. That interval exceeds the maximum supported
7,200-second worker hard limit plus a five-minute rollout margin, so a new
token-aware worker cannot immediately duplicate a non-idempotent send still
running in a pre-token worker. The rows retain a null token and become eligible
for ordinary lease recovery only after the quarantine expires. Deploy the
migration before replacing the old worker pool.

`JOBIFY_GEMINI_API_KEY` is required for Gemini embeddings or the LLM explainer.
SES additionally requires `JOBIFY_EMAIL_CHANNEL=ses` and a verified
`JOBIFY_EMAIL_FROM_ADDRESS`.

## Eager mode (tests)

Set `JOBIFY_CELERY_TASK_ALWAYS_EAGER=true` to run tasks synchronously in-process (no Redis required).
Used by integration test fixtures; never set in production.
