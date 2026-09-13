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
"""

from __future__ import annotations

import os
from wsgiref.simple_server import WSGIServer

import structlog
from celery.signals import setup_logging, worker_init, worker_process_shutdown
from prometheus_client import multiprocess, start_http_server

from jobify.observability.logging import configure_logging
from jobify.observability.metrics import (
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
