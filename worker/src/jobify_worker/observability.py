"""Worker observability wiring — imported by ``worker_app`` for its signal side effects.

- ``setup_logging`` → ``configure_logging``. Connecting it makes Celery skip its
  own logging setup, so Celery's records — including ``celery.app.trace``
  task-failure tracebacks — reach the root handler and render (and get redacted)
  like every other line. Both ``celery worker`` and ``celery beat`` send it.
- ``worker_init`` (main process, before any fork) → first validates
  ``PROMETHEUS_MULTIPROC_DIR`` is ready (raises if multiprocess mode is on but
  the directory doesn't exist — a bad directory silently drops every metric
  sample, so unlike a busy port it is NOT tolerated), then starts an opt-in
  Prometheus scrape endpoint on ``JOBIFY_WORKER_METRICS_PORT``. In
  multiprocess mode it serves a ``MultiProcessCollector`` registry, so
  prefork children's samples appear. NOTE: Celery's ``Signal.send`` catches
  and merely logs exceptions raised by receivers (it does not re-raise them
  to the caller), so this raise is fail-fast for direct calls (as tested)
  but is not proven to abort `celery worker` startup end-to-end — see
  worker/CLAUDE.md.
- ``worker_process_shutdown`` (sent by each prefork child itself as it exits
  normally — billiard's ``Worker._do_exit`` → ``on_exit`` — never for a
  SIGKILL'd or OOM-killed child) → ``multiprocess.mark_process_dead(pid)`` so
  dead children's live-gauge files stop reporting.

None of these fire for eager tasks in tests — call the receivers directly.

- task_prerun/postrun/retry/failure → task context in logs, jobify_task_runs_total +
  jobify_task_duration_seconds; task args are never logged.
"""

from __future__ import annotations

import os
from contextvars import Token
from time import perf_counter
from typing import Any
from wsgiref.simple_server import WSGIServer

import structlog
from celery.signals import (
    setup_logging,
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    worker_init,
    worker_process_shutdown,
)
from prometheus_client import multiprocess, start_http_server

from jobify.observability.logging import configure_logging
from jobify.observability.metrics import (
    TASK_DURATION,
    TASK_RUNS,
    build_registry,
    ensure_multiprocess_dir_ready,
    multiprocess_enabled,
)
from jobify_worker.celery_app import settings

_log = structlog.get_logger(__name__)


@setup_logging.connect  # type: ignore[untyped-decorator]
def configure_worker_logging(**_kwargs: object) -> None:
    """Ignore the signal's ``loglevel``/``logfile``/``format`` kwargs on purpose.

    ``JOBIFY_LOG_LEVEL``/``JOBIFY_LOG_FORMAT`` are the single control for
    worker log level/format (same as the API) — Celery's own ``--loglevel``
    flag has no effect once this receiver is connected.
    """
    configure_logging(settings)


@worker_init.connect  # type: ignore[untyped-decorator]
def start_worker_metrics_server(**_kwargs: object) -> WSGIServer | None:
    """Validate the multiprocess dir (raises — fatal), then start the scrape
    endpoint when configured. A PORT BIND failure alone must never stop task
    processing (caught below); a misconfigured multiprocess directory is a
    different class of failure — it would silently drop every metric sample
    from this process, so that check runs first and is allowed to raise.
    """
    ensure_multiprocess_dir_ready()
    port = settings.worker_metrics_port
    if port is None:
        return None
    try:
        server, _thread = start_http_server(
            port, addr=settings.worker_metrics_host, registry=build_registry()
        )
    except OSError:
        # Metrics are non-critical: a busy port must not stop task processing.
        _log.exception("worker.metrics-server-failed", port=port)
        return None
    _log.info(
        "worker.metrics-server-started",
        host=settings.worker_metrics_host,
        port=server.server_port,
        multiprocess=multiprocess_enabled(),
    )
    return server


@worker_process_shutdown.connect  # type: ignore[untyped-decorator]
def mark_worker_process_dead(pid: int | None = None, **_kwargs: object) -> None:
    if multiprocess_enabled():
        # prometheus-client 0.26 ships py.typed but this function has no
        # annotations; under `strict = true` mypy flags the call itself.
        multiprocess.mark_process_dead(  # type: ignore[no-untyped-call]
            pid if pid is not None else os.getpid()
        )


# Per-run state keyed by task id. Celery signals also fire for EAGER tasks (tests,
# and any code path that calls .apply()), possibly inside an API request — so
# receivers restore exactly the contextvars they bound instead of clearing.
_TASK_OUTCOMES = {"SUCCESS": "success", "RETRY": "retry", "FAILURE": "failure"}
# An entry leaks only if task_postrun never fires for a started task (hard-killed
# process — which discards this dict anyway); postrun fires on success, retry and failure.
_task_runs: dict[str, tuple[float, dict[str, Token[Any]]]] = {}


@task_prerun.connect  # type: ignore[untyped-decorator]
def bind_task_context(task_id: str, task: Any, **_kwargs: object) -> None:
    tokens = structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task.name,
        task_retries=getattr(task.request, "retries", 0),
    )
    _task_runs[task_id] = (perf_counter(), dict(tokens))


@task_postrun.connect  # type: ignore[untyped-decorator]
def record_task_run(task_id: str, task: Any, state: str | None = None, **_kwargs: object) -> None:
    started_at, tokens = _task_runs.pop(task_id, (None, {}))
    # state is also None under eager mode with task_eager_propagates=True (this worker's
    # setting): celery.app.trace.on_error re-raises before handle_error_state runs, so a
    # raising eager task never reaches RETRY/FAILURE state here and is counted as "error"
    # (task_retry/task_failure don't fire either — see worker/CLAUDE.md). Real (non-eager)
    # workers always pass a real state.
    outcome = _TASK_OUTCOMES.get(state or "", "error")
    TASK_RUNS.labels(task=task.name, outcome=outcome).inc()
    if started_at is not None:
        TASK_DURATION.labels(task=task.name).observe(max(perf_counter() - started_at, 0.0))
    if tokens:
        structlog.contextvars.reset_contextvars(**tokens)


@task_retry.connect  # type: ignore[untyped-decorator]
def log_task_retry(request: Any, reason: object = None, **_kwargs: object) -> None:
    # Celery's real handle_retry sends `reason=` a celery.exceptions.Retry
    # wrapper, not the underlying exception — unwrap `reason.exc` (may be
    # None) to get the real cause; fall back to `reason` itself for a plain
    # exception (autoretry_for) or string reason.
    cause = getattr(reason, "exc", None) or reason
    _log.warning(
        "task.retry",
        task_id=getattr(request, "id", None),
        task_name=getattr(request, "task", None),
        retries=getattr(request, "retries", None),
        error_type=type(cause).__name__ if isinstance(cause, BaseException) else None,
    )


@task_failure.connect  # type: ignore[untyped-decorator]
def log_task_failure(
    sender: Any = None,
    task_id: str | None = None,
    exception: BaseException | None = None,
    **_kwargs: object,
) -> None:
    # celery.app.trace already logs the canonical ERROR line WITH the traceback
    # (structured + redacted since PR 1); this adds task context, no second copy.
    _log.error(
        "task.failed",
        task_id=task_id,
        task_name=getattr(sender, "name", None),
        error_type=type(exception).__name__ if exception is not None else None,
    )
