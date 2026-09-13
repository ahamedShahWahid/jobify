"""Per-request log context + structured access log.

Pure ASGI (see ``request_id.py`` for why not ``BaseHTTPMiddleware``). Mounted
INSIDE ``RequestIdMiddleware`` — added to the app before it — so
``scope["state"]["request_id"]`` is already set when this runs.

- **Start:** clear structlog contextvars (no bleed between requests) and bind
  ``request_id``. ``current_user`` binds ``user_id`` later in the request.
- **End:** exactly one ``http.request`` event. Never the query string or raw
  path — ``q`` is free text and paths carry unbounded ids — only the matched
  route template.
- **Metrics:** the same end point records ``http_requests_total{method,status}``
  and ``http_request_duration_seconds{method,route}`` (this replaced the old
  ``MetricsMiddleware``; CORS stays outermost, so preflight short-circuits are
  not counted). The ``http.request`` log line is written FIRST, metrics
  recorded AFTER — an unexpected metrics failure (e.g. a misconfigured
  ``PROMETHEUS_MULTIPROC_DIR`` that slipped past the boot-time check) must
  never cost the access line. The ``method`` metric label is bounded to
  ``{GET,HEAD,POST,PUT,PATCH,DELETE,OPTIONS,OTHER}`` (see
  ``_metric_method``) — never unbounded like the log's real method.

Context is deliberately NOT cleared on the way out: Starlette's
``ServerErrorMiddleware`` (outermost) runs the unhandled-exception handler after
this middleware has returned, and that canonical error line must still carry
``request_id``/``user_id``. The next request's clear at start is what isolates.
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Final

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from jobify.observability.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS

_log = structlog.get_logger(__name__)

UNMATCHED_ROUTE: Final[str] = "__unmatched__"
_PROBE_ROUTES: Final[frozenset[str]] = frozenset({"/health", "/ready", "/metrics"})
# Cardinality rule (jobify.observability.metrics): metric label values come
# only from closed sets. HTTP methods are technically unbounded (any token is
# a valid request line), so anything outside this set collapses to "OTHER"
# for METRICS ONLY — the access log always keeps the real method.
_METRIC_METHODS: Final[frozenset[str]] = frozenset(
    {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
)


def route_template(scope: Scope) -> str:
    """The matched route's path template, or ``__unmatched__`` (bounded values only)."""
    path = getattr(scope.get("route"), "path", None)
    return path if isinstance(path, str) else UNMATCHED_ROUTE


def _metric_method(method: str) -> str:
    """Bounded method label for METRICS only — see _METRIC_METHODS."""
    return method if method in _METRIC_METHODS else "OTHER"


def _level_for(status: int, route: str) -> int:
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    if route in _PROBE_ROUTES:
        return logging.DEBUG
    return logging.INFO


class RequestContextMiddleware:
    """Pure-ASGI middleware: bind log context, then log one access line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state: dict[str, Any] = scope.setdefault("state", {})
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=state.get("request_id"))
        started_at = perf_counter()
        status: int | None = None

        async def _send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send_with_status)
        except Exception:
            # Raised before a response started → ServerErrorMiddleware sends 500.
            if status is None:
                status = 500
            raise
        finally:
            # No status (e.g. client disconnect / CancelledError): nothing was
            # served — no access line and no metric sample.
            if status is not None:
                route = route_template(scope)
                method = str(scope.get("method", "")).upper()
                duration_seconds = max(perf_counter() - started_at, 0.0)
                user_id = state.get("current_user_id")
                # Log BEFORE recording metrics: an unexpected metrics failure
                # (e.g. a multiprocess dir that vanished after boot) must not
                # cost the one canonical access line.
                _log.log(
                    _level_for(status, route),
                    "http.request",
                    method=method,
                    route=route,
                    status=status,
                    duration_ms=round(duration_seconds * 1000, 1),
                    user_id=str(user_id) if user_id is not None else None,
                )
                metric_method = _metric_method(method)
                HTTP_REQUESTS.labels(method=metric_method, status=str(status)).inc()
                HTTP_REQUEST_DURATION.labels(method=metric_method, route=route).observe(
                    duration_seconds
                )
