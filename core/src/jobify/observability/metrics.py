"""Prometheus metrics — the single declaration site for every metric.

Declare new metrics HERE, never inline in routes/tasks: one module keeps names,
labels and the cardinality rule reviewable in one place.

**Cardinality rule:** label values come only from closed sets — route
templates, registered task names, literal service/operation strings,
``outcome ∈ {success, error, retry, failure}``, and the bounded HTTP method
set in ``request_context.py`` (unrecognized methods collapse to ``"OTHER"``).
Never ids, raw paths or messages.

**Multiprocess mode.** When ``PROMETHEUS_MULTIPROC_DIR`` is set *before*
``prometheus_client`` is imported, every process writes its values to
memory-mapped files in that directory and :func:`build_registry` returns a fresh
registry whose ``MultiProcessCollector`` aggregates them at scrape time. Each
service needs its OWN directory (a shared one merges API and worker series),
wiped when that service is (re)started. Unset (tests, single-process dev) →
the default ``REGISTRY``. In multiprocess mode the scrape contains ONLY the
metrics declared in this module — ``MultiProcessCollector`` does not ship the
default process/platform collectors (``process_*``, ``python_gc_*``,
``python_info``); single-process mode still includes them via the default
``REGISTRY``.

**Boot-time validation.** :func:`ensure_multiprocess_dir_ready` must be called
once at process startup (API ``create_app()``, worker ``worker_init``)
*before* anything touches a declared metric or :func:`build_registry`. A set
but missing/non-directory ``PROMETHEUS_MULTIPROC_DIR`` otherwise surfaces as a
``FileNotFoundError`` from the first metric write (inside
``RequestContextMiddleware``'s ``finally``, after the access log line) or a
``ValueError`` from the first ``/metrics`` scrape — both far from the actual
misconfiguration.
"""

from __future__ import annotations

import os
from typing import Final

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    disable_created_metrics,
    multiprocess,
)

# `_created` companion series double every counter/histogram for no operational
# value here (multiprocess mode never emits them anyway).
# prometheus-client 0.26 ships py.typed but this function has no annotations;
# under `strict = true` mypy flags the call itself as no-untyped-call.
disable_created_metrics()  # type: ignore[no-untyped-call]

_HTTP_DURATION_BUCKETS: Final[tuple[float, ...]] = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)

HTTP_REQUESTS: Final[Counter] = Counter(
    "http_requests",
    "Total HTTP requests by method and status code.",
    ("method", "status"),
)
HTTP_REQUEST_DURATION: Final[Histogram] = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration by matched route template.",
    ("method", "route"),
    buckets=_HTTP_DURATION_BUCKETS,
)
UNHANDLED_EXCEPTIONS: Final[Counter] = Counter(
    "jobify_unhandled_exceptions",
    "Unhandled exceptions that produced a 500, by matched route template.",
    ("route",),
)
VALIDATION_FAILURES: Final[Counter] = Counter(
    "jobify_http_validation_failures",
    "Request validation failures (422), by matched route template.",
    ("route",),
)

_EXTERNAL_CALL_BUCKETS: Final[tuple[float, ...]] = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)
_TASK_DURATION_BUCKETS: Final[tuple[float, ...]] = (0.1, 0.5, 1, 5, 10, 30, 60, 120, 300)

EXTERNAL_CALLS: Final[Counter] = Counter(
    "jobify_external_calls",
    "External provider calls by service, operation and outcome (success|error).",
    ("service", "operation", "outcome"),
)
EXTERNAL_CALL_DURATION: Final[Histogram] = Histogram(
    "jobify_external_call_duration_seconds",
    "External provider call duration by service and operation.",
    ("service", "operation"),
    buckets=_EXTERNAL_CALL_BUCKETS,
)
TASK_RUNS: Final[Counter] = Counter(
    "jobify_task_runs",
    "Celery task runs by registered task name and outcome (success|retry|failure|error).",
    ("task", "outcome"),
)
TASK_DURATION: Final[Histogram] = Histogram(
    "jobify_task_duration_seconds",
    "Celery task run duration by registered task name.",
    ("task",),
    buckets=_TASK_DURATION_BUCKETS,
)


def multiprocess_enabled() -> bool:
    """True when this process runs in prometheus_client multiprocess mode.

    Mirrors prometheus_client's own predicate (``values.py``/``multiprocess.py``):
    presence of either env var spelling counts, not truthiness of its value —
    an empty-string ``PROMETHEUS_MULTIPROC_DIR`` still turns multiprocess mode
    on (and then fails :func:`ensure_multiprocess_dir_ready`, since "" is not
    a directory). Read per call (not cached) so tests can monkeypatch it.
    """
    return "PROMETHEUS_MULTIPROC_DIR" in os.environ or "prometheus_multiproc_dir" in os.environ


def _multiprocess_dir() -> str | None:
    """The directory prometheus_client itself will resolve to (same precedence:
    uppercase wins whenever it is present, even as ""; else the legacy
    lowercase name; else ``None``)."""
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        return os.environ["PROMETHEUS_MULTIPROC_DIR"]
    return os.environ.get("prometheus_multiproc_dir")


def ensure_multiprocess_dir_ready() -> None:
    """Fail fast if multiprocess mode is on but its directory isn't usable yet.

    Call once at process boot (API ``create_app()``, worker ``worker_init``)
    before any metric write or scrape — see the module docstring for why.
    A no-op when multiprocess mode is off.
    """
    if not multiprocess_enabled():
        return
    path = _multiprocess_dir()
    if not path or not os.path.isdir(path):
        raise RuntimeError(f"PROMETHEUS_MULTIPROC_DIR={path} must be an existing directory")


def build_registry() -> CollectorRegistry:
    """The registry a scrape should render (see module docstring)."""
    if not multiprocess_enabled():
        return REGISTRY
    registry = CollectorRegistry()
    # Same untyped-third-party-call gap as disable_created_metrics above.
    multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
    return registry
