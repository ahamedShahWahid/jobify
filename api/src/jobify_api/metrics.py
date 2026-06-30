"""Process-local HTTP request metrics in Prometheus text-exposition format.

A dependency-free substrate: a single in-process counter keyed by
``(method, status)``. Each API process exposes its own counters at ``/metrics``;
aggregation across processes is the scraper's job (the standard Prometheus
model), so there is deliberately no shared store here.

Cardinality is bounded on purpose — we label only by HTTP ``method`` and numeric
``status`` code, never by path (path templates are unbounded and would explode
the series count). A 5xx rate is derivable as
``sum(status>=500) / sum(all)`` by the scraper.

Counters live at module scope (incremented once per request via
``record_request``); ``create_app()`` is called per-test, so defining them here
rather than inside the factory keeps a single series set for the process. Under
asyncio's cooperative single thread the ``+=`` increment has no await between
read and write, so it needs no lock.
"""

from __future__ import annotations

from typing import Final

_REQUEST_COUNTS: Final[dict[tuple[str, int], int]] = {}

_METRIC_NAME: Final[str] = "http_requests_total"


def record_request(method: str, status: int) -> None:
    """Increment the counter for one completed request."""
    key = (method.upper(), status)
    _REQUEST_COUNTS[key] = _REQUEST_COUNTS.get(key, 0) + 1


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
    return "\n".join(lines) + "\n"


def reset_metrics() -> None:
    """Clear all counters (test-support; not used in production paths)."""
    _REQUEST_COUNTS.clear()
