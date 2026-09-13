"""Prometheus metrics — the single declaration site for every metric.

Declare new metrics HERE, never inline in routes/tasks: one module keeps names,
labels and the cardinality rule reviewable in one place.

**Cardinality rule:** label values come only from closed sets — route
templates, registered task names, literal service/operation strings, and
``outcome ∈ {success, error, retry, failure}``. Never ids, raw paths or
messages.

**Multiprocess mode.** When ``PROMETHEUS_MULTIPROC_DIR`` is set *before*
``prometheus_client`` is imported, every process writes its values to
memory-mapped files in that directory and :func:`build_registry` returns a fresh
registry whose ``MultiProcessCollector`` aggregates them at scrape time. Each
service needs its OWN directory (a shared one merges API and worker series),
wiped on start. Unset (tests, single-process dev) → the default ``REGISTRY``.
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


def multiprocess_enabled() -> bool:
    """True when this process runs in prometheus_client multiprocess mode."""
    return bool(os.environ.get("PROMETHEUS_MULTIPROC_DIR"))


def build_registry() -> CollectorRegistry:
    """The registry a scrape should render (see module docstring)."""
    if not multiprocess_enabled():
        return REGISTRY
    registry = CollectorRegistry()
    # Same untyped-third-party-call gap as disable_created_metrics above.
    multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
    return registry
