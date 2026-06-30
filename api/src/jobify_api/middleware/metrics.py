"""HTTP metrics middleware.

Records exactly one ``(method, status)`` counter increment per completed HTTP
request (see ``jobify_api.metrics``). Implemented as pure ASGI — like
``RequestIdMiddleware`` — rather than ``BaseHTTPMiddleware``, whose internal
task-group wrapping triggers the asyncpg "Future attached to a different loop"
failure alongside DB connections.

If the inner app raises before sending a response (an exception that propagates
past the registered handlers), it is counted as a 500 and re-raised — so the 5xx
series reflects unhandled failures, not just clean error responses.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from jobify_api.metrics import record_request


class MetricsMiddleware:
    """Pure-ASGI middleware that counts responses by method + status code."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        seen: dict[str, int] = {}

        async def _send_with_metrics(message: Message) -> None:
            if message["type"] == "http.response.start":
                seen["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send_with_metrics)
        except Exception:
            record_request(method, seen.get("status", 500))
            raise
        else:
            record_request(method, seen.get("status", 500))
