"""Bounded-cardinality process-local HTTP request metrics.

A dependency-free substrate: a single in-process counter keyed by
``(method, status)``. Each API process exposes its own counters at ``/metrics``;
aggregation across processes is the scraper's job (the standard Prometheus
model), so there is deliberately no shared store here.

Cardinality is bounded on purpose. Counters use method and status; latency uses
method and the framework's matched route template (never the raw request path).
A 5xx rate is derivable as
``sum(status>=500) / sum(all)`` by the scraper.

Counters live at module scope (incremented once per request via
``record_request``); ``create_app()`` is called per-test, so defining them here
rather than inside the factory keeps a single series set for the process. Under
asyncio's cooperative single thread the ``+=`` increment has no await between
read and write, so it needs no lock — but this holds ONLY on the event loop.
``record_request`` and ``render_prometheus`` must both run there; in particular
the ``/metrics`` handler is ``async`` so ``render_prometheus`` does not iterate
``_REQUEST_COUNTS`` from a threadpool thread while the loop mutates it.
"""

from __future__ import annotations

from typing import Final

_REQUEST_COUNTS: Final[dict[tuple[str, int], int]] = {}
_DURATION_BUCKET_COUNTS: Final[dict[tuple[str, str, float], int]] = {}
_DURATION_SUMS: Final[dict[tuple[str, str], float]] = {}
_DURATION_COUNTS: Final[dict[tuple[str, str], int]] = {}

_METRIC_NAME: Final[str] = "http_requests_total"
_DURATION_NAME: Final[str] = "http_request_duration_seconds"
_DURATION_BUCKETS: Final[tuple[float, ...]] = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)


def record_request(
    method: str,
    status: int,
    *,
    route: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Record one completed request and, when supplied, its route latency."""
    normalized_method = method.upper()
    key = (normalized_method, status)
    _REQUEST_COUNTS[key] = _REQUEST_COUNTS.get(key, 0) + 1
    if route is None or duration_seconds is None:
        return

    duration_key = (normalized_method, route)
    _DURATION_COUNTS[duration_key] = _DURATION_COUNTS.get(duration_key, 0) + 1
    _DURATION_SUMS[duration_key] = _DURATION_SUMS.get(duration_key, 0.0) + max(
        duration_seconds, 0.0
    )
    for boundary in _DURATION_BUCKETS:
        if duration_seconds <= boundary:
            bucket_key = (normalized_method, route, boundary)
            _DURATION_BUCKET_COUNTS[bucket_key] = _DURATION_BUCKET_COUNTS.get(bucket_key, 0) + 1


def _escape_label_value(value: str) -> str:
    # Prometheus exposition: backslash, double-quote and newline are escaped.
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus() -> str:
    """Render the current counters as Prometheus 0.0.4 text exposition."""
    lines = [
        f"# HELP {_METRIC_NAME} Total HTTP requests by method and status code.",
        f"# TYPE {_METRIC_NAME} counter",
    ]
    for (method, status), count in sorted(_REQUEST_COUNTS.items()):
        method_label = _escape_label_value(method)
        lines.append(f'{_METRIC_NAME}{{method="{method_label}",status="{status}"}} {count}')
    lines.extend(
        [
            f"# HELP {_DURATION_NAME} HTTP request duration by matched route template.",
            f"# TYPE {_DURATION_NAME} histogram",
        ]
    )
    for (method, route), count in sorted(_DURATION_COUNTS.items()):
        method_label = _escape_label_value(method)
        route_label = _escape_label_value(route)
        for boundary in _DURATION_BUCKETS:
            bucket_count = _DURATION_BUCKET_COUNTS.get((method, route, boundary), 0)
            lines.append(
                f'{_DURATION_NAME}_bucket{{method="{method_label}",route="{route_label}",'
                f'le="{boundary:g}"}} {bucket_count}'
            )
        lines.append(
            f'{_DURATION_NAME}_bucket{{method="{method_label}",route="{route_label}",'
            f'le="+Inf"}} {count}'
        )
        lines.append(
            f'{_DURATION_NAME}_sum{{method="{method_label}",route="{route_label}"}} '
            f"{_DURATION_SUMS[(method, route)]:.9g}"
        )
        lines.append(
            f'{_DURATION_NAME}_count{{method="{method_label}",route="{route_label}"}} {count}'
        )
    return "\n".join(lines) + "\n"


def reset_metrics() -> None:
    """Clear all counters. Used by tests for per-test isolation of the
    process-global counters; not called on production paths."""
    _REQUEST_COUNTS.clear()
    _DURATION_BUCKET_COUNTS.clear()
    _DURATION_SUMS.clear()
    _DURATION_COUNTS.clear()
