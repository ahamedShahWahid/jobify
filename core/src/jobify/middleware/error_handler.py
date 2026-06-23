"""RFC 7807 problem-detail error handlers.

Replaces FastAPI's default JSON error shape with `application/problem+json`
responses that include the request id for traceability.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from jobify.middleware.request_id import REQUEST_ID_HEADER

_log = structlog.get_logger(__name__)


def _problem(
    *,
    status: int,
    title: str,
    detail: str,
    request_id: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id,
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


def _phrase_for(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        request_id = getattr(request.state, "request_id", "unknown")
        return _problem(
            status=exc.status_code,
            title=_phrase_for(exc.status_code),
            detail=detail,
            request_id=request_id,
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        _log.exception(
            "unhandled-exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        response = _problem(
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
            request_id=request_id,
        )
        # Starlette's ServerErrorMiddleware is outside RequestIdMiddleware, so a
        # response produced here never re-enters the middleware that would
        # normally attach the header. Set it explicitly to preserve correlation.
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
