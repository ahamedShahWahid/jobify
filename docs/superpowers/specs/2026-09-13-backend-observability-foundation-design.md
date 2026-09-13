# Backend observability foundation — design

**Date:** 2026-09-13 · **Status:** approved, not yet implemented
**Parent:** "Make sure all errors and exceptions are logged; improve
observability" — sub-project 1 of 3. Follow-ups (own specs): Flutter client
error capture, React frontend error capture. A hosted error tracker (Sentry
etc.) is out of scope for all three until an account/DSN exists.

## Why

A 2026-09-13 survey of `core`/`api`/`worker` found errors that are invisible
or uncorrelatable:

- **Worker logging is never configured.** `configure_logging()` is called only
  by the API (`app_factory.py`); `WorkerSettings.log_level/log_format` are dead
  config, so `JOBIFY_LOG_FORMAT=json` does nothing in the worker.
- **stdlib loggers bypass structlog.** The root handler uses a bare
  `Formatter("%(message)s")` — uvicorn, SQLAlchemy, httpx and Celery (incl.
  `celery.app.trace` task tracebacks) emit no level/timestamp/JSON.
- **`request_id` is not bound into log context.** Only `unhandled-exception`
  carries it; nothing carries `user_id` or Celery `task_id`.
- **Error classes that never log:** `RequestValidationError` (422s),
  `HTTPException` with status ≥500, Starlette 404/405 for unmatched routes.
- **~10 silent `except` blocks** (e.g. rate-limiter Redis outage → 503 with no
  log in `routes/auth.py`; SES failure → `ChannelResult.failed` in
  `notifications/ses.py`; `TransientParserError` not subclassing `ParserError`
  so it falls silently to the library parser in `parser/fallback.py`) and
  **~10 that log without the traceback** (`embed.py`/`embed_job.py`
  `error=str(exc)`; `sweep_outbox.py` logs `error_type` with no task name;
  `llm_parser.py` failures at DEBUG; `llm_call_failed: {type}` loses the HTTP
  status that separates 429 from 403).
- **No external-call telemetry** — Gemini, SES, S3, Google JWKS log no latency,
  status or outcome.
- **Metrics are API-only and hand-rolled.** The worker — where most external
  calls happen — exposes nothing, and the in-process exporter cannot aggregate
  the multiple processes the deploy model implies (`IMPLEMENTATION_SPEC.md`:
  "uvicorn workers"; `worker/README.md`: solo → prefork).
- **No redaction.** Existing leaks: `grant_admin.py` logs emails, SES error text
  (may contain addresses) is logged by `sweep_notifications.py`, the explainer
  logs `raw_text[:200]` of model output. uvicorn's access log writes the search
  `q` verbatim.

## Decisions (made during brainstorming)

| Question | Decision |
|---|---|
| Scope of this spec | Backend only (core/api/worker). Logs-first, no hosted tracker. |
| Metrics depth | Logs + targeted metrics, no tracing. |
| Metrics implementation | **`prometheus_client`** replacing the hand-rolled exporter, multiprocess-capable. |
| PII policy | **Shapes, never values**, plus a global redaction processor as a safety net; fix existing leaks. |
| Access log | Own structlog access log; uvicorn's disabled. |
| 422 response body | **Unchanged** (log-only handler) — reshaping it is a client contract change. |
| `_created` series | Disabled. |
| Worker metrics port | Off unless `JOBIFY_WORKER_METRICS_PORT` is set. |
| Task success | Metric only, no log line. |
| UUIDs in logs | Allowed (`user_id`, `applicant_id`, …) — needed for correlation. |

## Architecture

### Shared — `core/src/jobify/observability/`

**`logging.py` (extended)**

- Keep structlog's own path on `PrintLoggerFactory` (a full `structlog.stdlib`
  migration would change output capture across the existing suite for no gain).
- Attach `structlog.stdlib.ProcessorFormatter` to the root stdlib handler with a
  `foreign_pre_chain` (level, timestamp, logger name, `ExtraAdder`, contextvars,
  redaction) so every stdlib logger renders in the same key=value/JSON format.
- **Redaction processor** — runs last before the renderer on both paths. Masks
  values to `"[REDACTED]"` for keys matched case-insensitively, at any depth in
  dicts and lists: `email`, `recipient`, `to`, `token`, `access_token`,
  `refresh_token`, `id_token`, `authorization`, `password`, `secret`,
  `api_key`, `raw_text`, `resume_text`, `text`, `body`, `payload`. The key list
  is a module constant; additions are reviewed like invariants.
- **Exception-text scrub.** Key-based redaction cannot see PII *inside*
  exception messages, and tracebacks render those messages. Two guards:
  - `create_async_engine(..., hide_parameters=True)` in `db/session.py`, so
    SQLAlchemy errors never embed bound parameter values
    (`[parameters: …]`).
  - A regex scrub over the rendered `exception` field and all string values
    masks email addresses (Postgres `Key (email)=(a@b.c)` details, provider
    error text) to `[REDACTED_EMAIL]`.
  Where an exception's *message* is known to carry PII and can't be scrubbed
  by pattern (SES send errors), the call site logs `error_type` without
  `exc_info`.
- A `logging.Filter` on `uvicorn.error` drops the duplicate
  "Exception in ASGI application" record (Starlette's `ServerErrorMiddleware`
  always re-raises after our handler has logged the canonical traceback).

**`metrics.py` (new — the single declaration site for every metric)**

- Declares all metrics (catalog below) at module scope.
- `build_registry() -> CollectorRegistry`: when `PROMETHEUS_MULTIPROC_DIR` is
  set, a fresh registry with `multiprocess.MultiProcessCollector`; otherwise the
  default `REGISTRY`. Tests run single-process; `start-all.sh` and prod set the
  directory. The env var must be set before `prometheus_client` is imported.
- `PROMETHEUS_DISABLE_CREATED_SERIES=True` suppresses `_created` series.
- `api/src/jobify_api/metrics.py` (hand-rolled) is deleted.

**`external.py` (new)**

```python
with observe_external_call("gemini", "embed"):
    ...
```

Measures duration; increments `jobify_external_calls_total{service,operation,
outcome}` and observes `jobify_external_call_duration_seconds`; logs one
`external.call` event with `service`, `operation`, `outcome`, `http_status`
(extracted from the exception/response when available), `error_type`,
`duration_ms`. Failure: WARNING with traceback, then **re-raise** — it never
swallows. Success: DEBUG. `service`/`operation` are literal strings at call
sites (bounded cardinality).

### API — `jobify_api`

**`RequestContextMiddleware`** (new, pure ASGI; replaces `MetricsMiddleware`).
Added in `create_app` *before* `RequestIdMiddleware` so it sits inside it and
can read `request_id`. Order, outermost first:
`ServerErrorMiddleware → CORS → RequestIdMiddleware → RequestContextMiddleware → router`.

- Request start: `structlog.contextvars.clear_contextvars()`, then
  `bind_contextvars(request_id=...)`.
- `current_user` (`auth/dependencies.py`) adds one
  `bind_contextvars(user_id=str(user.id))` next to its existing
  `request.state.current_user_id` assignment.
- Request end (in `finally`, mirroring today's `MetricsMiddleware`
  try/except/re-raise shape): one `http.request` event — `method`, `route`
  (matched template or `__unmatched__`), `status` (500 if the app raised before
  starting a response), `duration_ms`, `request_id`, `user_id` (read from
  `scope["state"]`, which is where Starlette's `request.state` writes land).
  **No query string, no raw path.** Level: ≥500 ERROR, ≥400 WARNING, else INFO;
  `/health`, `/ready`, `/metrics` at DEBUG.
- Records `http_requests_total{method,status}` and
  `http_request_duration_seconds{method,route}` (same label sets as today).

**Error handlers** (`middleware/error_handler.py`)

- `RequestValidationError` → WARNING `http.validation-failed` with
  `fields=[{"loc": "body.locations.0", "type": "string_too_short"}, …]` — never
  `input`/`msg`/`ctx`. Increments `jobify_http_validation_failures_total{route}`.
  Returns **exactly** FastAPI's default response (delegate to
  `fastapi.exception_handlers.request_validation_exception_handler`).
- `HTTPException` status ≥500 → ERROR `http.error` (status, detail slug). <500
  unchanged (the access line records it at WARNING).
- `Exception` → unchanged canonical `unhandled-exception` with traceback, plus
  `jobify_unhandled_exceptions_total{route}`.

**`/metrics`** (`routes/metrics.py`) returns
`generate_latest(build_registry())` with `CONTENT_TYPE_LATEST`. The DB-backed
async-work gauges (`operational_metrics.py`) become a custom Collector. Because
`Collector.collect()` is synchronous and the query is async, the route runs the
query first, then hands the fetched rows to a per-scrape collector registered
on the per-scrape registry. On DB failure it logs
`metrics.async-work-query-failed` (existing) and the collector yields
`jobify_async_metrics_up 0`. Bearer-token check unchanged.

**uvicorn** runs with `--no-access-log` in `scripts/start-all.sh` and the
`api/README.md` run commands.

### Worker — `jobify_worker`

- **Logging:** connect Celery's `setup_logging` signal →
  `configure_logging(WorkerSettings())`. Connecting this signal stops Celery
  configuring logging itself, so Celery's tracebacks reach the root handler —
  this **must ship with** the stdlib-routing change above or worker tracebacks
  get worse.
- **Task signals** (new `jobify_worker/observability.py`, imported by
  `worker_app.py`):
  - `task_prerun` → `bind_contextvars(task_id, task_name, retries)`, start timer.
  - `task_retry` → WARNING `task.retry` (`error_type`); outcome `retry`.
  - `task_failure` → ERROR `task.failed` with traceback; outcome `failure`.
  - `task_success` → outcome `success` (no log).
  - `task_postrun` → observe duration, `clear_contextvars()`.
  - **Task args/kwargs are never logged.**
- **Metrics server:** `worker_init` (main process) calls
  `prometheus_client.start_http_server(port)` when `JOBIFY_WORKER_METRICS_PORT`
  is set; in multiprocess mode it serves a `MultiProcessCollector` registry.
  `worker_process_shutdown` calls `multiprocess.mark_process_dead(pid)` so
  prefork children don't leave stale live-gauge files.
- New `WorkerSettings.metrics_port: int | None = None`.

### Call-site remediation (all packages)

Each item is either fixed to log with traceback and context, or kept
intentionally silent with `# noqa: BLE001 — <reason>`. The implementation plan
re-verifies every line reference against the code before editing.

**Silent → logged**

| Site | Fix |
|---|---|
| `api/.../routes/auth.py` rate-limiter `except Exception` → 503 | `_log.exception("auth.rate-limiter-unavailable")` before the 503 |
| `api/.../routes/ready.py` DB/Redis probes | WARNING with traceback per failed dependency |
| `core/.../notifications/ses.py` `except Exception` | route through `observe_external_call("ses","send")`; failed result keeps `error_type` only |
| `worker/.../sweep_notifications.py` failed send | log retry-scheduled (WARNING) and max-attempts (ERROR) with `channel`, `attempt`, `error_type` — **no traceback/error text** (SES messages can carry addresses) |
| `core/.../parser/fallback.py` | `TransientParserError` logged before library fallback (and made visible — see LLM parser below) |
| `core/.../parser/library.py` no text extracted | WARNING `parse.no-text-extracted` (shape only) |
| `api/.../auth/google_verifier.py` JWT errors | WARNING `google.id-token-rejected` with `error_type` (no token) |
| IntegrityError → 409 (`team_service.py`, `routes/invites.py`, `routes/employers/core.py`) | INFO `…-conflict` with constraint name |

**Traceback lost → kept**

| Site | Fix |
|---|---|
| `worker/.../tasks/embed.py`, `embed_job.py` `_log.error(error=str(exc))` | `_log.exception(...)` |
| `worker/.../tasks/sweep_outbox.py` failure warning | add `task_name`, `exc_info=True` |
| `core/.../parser/fallback.py` warnings `error=str(exc)` | `exc_info=True`, drop `str(exc)` |
| `api/.../auth/google_verifier.py` JWKS fetch warning | `exc_info=True` |
| `api/.../scripts/seed_jobs.py` | `_log.exception(...)` |
| `worker/.../tasks/parse.py` `parse.failed` | include `error_type` + traceback |
| `core/.../parser/llm_parser.py` failure logs at DEBUG | → WARNING; `llm_call_failed` wrapping keeps `http_status` |

**External calls wrapped in `observe_external_call`:** Gemini embeddings
(`embeddings/gemini.py`), LLM parser, LLM explainer, SES send, S3
put/get/delete (`storage/s3.py`), Google JWKS fetch.

**PII leaks fixed** (deliberate test reversals):

- `llm_explainer.py` stops logging `raw_text[:200]`; `test_llm_explainer.py`
  assertion flips to "raw text not logged".
- `grant_admin.py` logs `user_id`, not email.
- `sweep_notifications.py` stops logging SES error text.
- `logging_email.py` (dev-only channel) keeps logging for local use, but via
  keys the redactor masks; `test_logging_email_channel.py` updated.

**Lint guard:** add `BLE001` (blind except) and `TRY400` (`error` inside
`except` instead of `exception`) to `[tool.ruff.lint] select`. `S110` is
already on. Every remaining suppression carries a reason.

## Metric catalog

| Metric | Type | Labels | Emitted by |
|---|---|---|---|
| `http_requests_total` | counter | method, status | API |
| `http_request_duration_seconds` | histogram | method, route | API |
| `jobify_unhandled_exceptions_total` | counter | route | API |
| `jobify_http_validation_failures_total` | counter | route | API |
| `jobify_external_calls_total` | counter | service, operation, outcome | API + worker |
| `jobify_external_call_duration_seconds` | histogram | service, operation | API + worker |
| `jobify_task_runs_total` | counter | task, outcome | worker |
| `jobify_task_duration_seconds` | histogram | task | worker |
| `jobify_async_items` | gauge (collector) | queue, status | API scrape |
| `jobify_async_oldest_actionable_age_seconds` | gauge (collector) | queue | API scrape |
| `jobify_async_metrics_up` | gauge (collector) | — | API scrape |

**Cardinality rule:** label values come only from closed sets — route templates,
registered task names, literal service/operation strings, and
`outcome ∈ {success, error, retry, failure}`. Never ids, raw paths or messages.

## Log levels

| Level | Meaning | Examples |
|---|---|---|
| ERROR | Broken, needs a human | `unhandled-exception`, `http.error` (≥500), `task.failed`, metrics query failure |
| WARNING | Handled but noteworthy | 4xx access line, `http.validation-failed`, `task.retry`, external-call failure, LLM→library degrade, JWKS stale cache |
| INFO | Normal lifecycle | 2xx/3xx access line, 409 conflicts |
| DEBUG | Noise | probe access lines, external-call success |

## Testing

| Area | Test |
|---|---|
| Redaction | Run the **real** `configure_logging` (not `capture_logs`, which bypasses the chain) and assert on captured stdout: nested dict/list/case variants masked; UUIDs kept; stdlib `extra={"authorization": …}` masked; an exception whose message contains an email renders `[REDACTED_EMAIL]` in the traceback. |
| DB error params | Integration: a forced `IntegrityError` rendered via `_log.exception` contains no bound values (`hide_parameters=True`). |
| stdlib routing | `logging.getLogger("httpx").warning(...)` renders as JSON with level + timestamp under `log_format=json`. |
| Context binding | Integration: authenticated request logging inside the handler carries `request_id` + `user_id`; two sequential requests don't bleed context. |
| Access log | One `http.request` per request; `?q=secret` absent; probe at DEBUG; unmatched route logs `route=__unmatched__`, 404. |
| 422 | Body byte-identical to FastAPI's default; log has `loc` + `type`, not the submitted value; counter increments. |
| 5xx | `HTTPException(503)` logs ERROR; unhandled exception yields exactly one traceback line (uvicorn duplicate filtered) and increments the counter. |
| `/metrics` | Existing `test_metrics.py` rewritten for `prometheus_client` output; multiprocess registry tested in a subprocess with `tmp_path` as `PROMETHEUS_MULTIPROC_DIR`; bearer token enforced; DB failure → `jobify_async_metrics_up 0`. OpenAPI snapshot unaffected (`include_in_schema=False`). |
| `observe_external_call` | success; failure re-raises; `http_status` extracted; outcome counter labels. |
| Celery hooks | Call signal handlers directly with fake sender/task objects — **not** via eager tasks (`task_always_eager` does not fire the same signal path). |
| Call-site fixes | One targeted test per behavior change (e.g. rate-limiter Redis outage logs; transient parser error logs before fallback). |
| Lint guard | `uv run ruff check` green with `BLE001`/`TRY400`. |

CI gate unchanged (root `CLAUDE.md` verbatim commands).

## Rollout — one spec, three PRs

Each PR branches off latest `origin/main`.

1. **Logging substrate** — `logging.py` stdlib routing + redaction + uvicorn
   duplicate filter + exception-text email scrub; `hide_parameters=True`;
   worker `setup_logging`; `RequestContextMiddleware` context
   binding + access log (metrics still via the old module in this PR);
   `current_user` binding; 422/5xx handlers; `--no-access-log`.
2. **Metrics on `prometheus_client`** — dependency in `core/pyproject.toml`;
   `observability/metrics.py`; access middleware records via it; `/metrics`
   rewrite + async-work collector; worker metrics server + `mark_process_dead`;
   `PROMETHEUS_MULTIPROC_DIR` create-and-wipe in `start-all.sh`; hand-rolled
   module deleted.
3. **Call sites** — `observe_external_call` + wiring; Celery task signals; the
   `except` remediation tables; LLM parser levels/status; PII leak fixes; ruff
   `BLE001`/`TRY400`.

PR 2 precedes PR 3 because external-call and task metrics need the metrics
module.

## Docs

- `api/CLAUDE.md`: replace the "uvicorn access log writes `q` verbatim" note
  with the access-log invariant; 422 log-only/body-unchanged rule; middleware
  order.
- `core/CLAUDE.md`: shapes-not-values rule + redaction key list;
  `observe_external_call` required for external calls; metrics declared only in
  `observability/metrics.py` + cardinality rule.
- `worker/CLAUDE.md`: signal hooks, never log task args, multiprocess shutdown.
- `api/README.md` / `worker/README.md`: `PROMETHEUS_MULTIPROC_DIR`,
  `JOBIFY_WORKER_METRICS_PORT`, `--no-access-log` run commands.

## Risks

- **Routing stdlib loggers through structlog may change output that existing
  tests capture.** Run the full integration suite immediately after the PR 1
  logging change, before layering anything else.
- **Multiprocess files accumulate** in dev/prod. `start-all.sh` wipes the
  directory at start; prod entrypoints must do the same (noted in READMEs).
- **Redaction over-matches generic keys** (`text`, `body`, `to`). Acceptable:
  masking a harmless value is cheaper than leaking PII; a false positive shows
  up as `[REDACTED]` in a log and is fixed by renaming the log key.

## Out of scope

Hosted error tracker; OpenTelemetry tracing; changing the 422 response shape;
Flutter and React error capture (sub-projects 2 and 3); log shipping/retention
infrastructure.
