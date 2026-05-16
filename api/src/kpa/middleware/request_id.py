"""Request-ID middleware.

Generates a uuid4 per request (or accepts a client-supplied one if it's a valid
uuid4) and exposes it on `request.state.request_id` as well as the response
`X-Request-Id` header. The id is the primary correlation handle in logs.

Implemented as a pure ASGI middleware (not BaseHTTPMiddleware) to avoid the
known event-loop mismatch that BaseHTTPMiddleware introduces when used alongside
asyncpg connections in tests and production.
"""

from __future__ import annotations

import re
import uuid
from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER: Final[str] = "X-Request-Id"
_UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _looks_like_uuid4(value: str) -> bool:
    return bool(_UUID_V4_RE.match(value))


class RequestIdMiddleware:
    """Pure-ASGI request-ID middleware.

    Avoids BaseHTTPMiddleware's internal task-group wrapping, which can cause
    asyncpg connections to detect a mismatched event loop.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_incoming = headers.get(REQUEST_ID_HEADER.lower().encode(), b"").decode()
        request_id = (
            raw_incoming if raw_incoming and _looks_like_uuid4(raw_incoming) else str(uuid.uuid4())
        )

        # Expose on scope so routes can read it via request.state
        scope.setdefault("state", {})["request_id"] = request_id

        async def _send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers_mut = MutableHeaders(scope=message)
                headers_mut.append(REQUEST_ID_HEADER, request_id)
            await send(message)

        await self.app(scope, receive, _send_with_header)
