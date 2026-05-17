"""Request-ID middleware.

Generates a uuid4 per request (or accepts a client-supplied one if it's a valid
uuid4) and exposes it on `request.state.request_id` as well as the response
`X-Request-Id` header. The id is the primary correlation handle in logs.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER: Final[str] = "X-Request-Id"
_UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _looks_like_uuid4(value: str) -> bool:
    return bool(_UUID_V4_RE.match(value))


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and _looks_like_uuid4(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
