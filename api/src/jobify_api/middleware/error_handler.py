"""RFC 7807 problem-detail error handlers.

Replaces FastAPI's default JSON error shape with `application/problem+json`
responses that include the request id for traceability.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, Final

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from jobify.observability.metrics import UNHANDLED_EXCEPTIONS, VALIDATION_FAILURES
from jobify_api.middleware.request_context import route_template
from jobify_api.middleware.request_id import REQUEST_ID_HEADER

_log = structlog.get_logger(__name__)

_MAX_LOC_PART_CHARS: Final = 64
_MAX_LOGGED_FIELDS: Final = 20


def _loc_part(part: object) -> str:
    # extra="forbid" models put the CLIENT's unknown key name in loc — bound it.
    text = str(part)
    return text if len(text) <= _MAX_LOC_PART_CHARS else text[: _MAX_LOC_PART_CHARS - 1] + "…"


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
        if exc.status_code >= 500:
            # A deliberate 5xx is still an outage signal. <500 is recorded by the
            # access line alone (WARNING) — no second event.
            _log.error(
                "http.error",
                status=exc.status_code,
                detail=detail,
                route=route_template(request.scope),
            )
        return _problem(
            status=exc.status_code,
            title=_phrase_for(exc.status_code),
            detail=detail,
            request_id=request_id,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Log-only: the body stays FastAPI's default {"detail": [...]} — both
        # clients parse it, so reshaping it is a cross-package contract change.
        # Shapes, never values: loc + type only; input/msg/ctx echo the payload.
        route = route_template(request.scope)
        errors = exc.errors()
        fields = [
            {"loc": ".".join(_loc_part(part) for part in error["loc"]), "type": error["type"]}
            for error in errors[:_MAX_LOGGED_FIELDS]
        ]
        log_kwargs: dict[str, Any] = {"route": route, "fields": fields}
        truncated = len(errors) - len(fields)
        if truncated > 0:
            log_kwargs["fields_truncated"] = truncated
        _log.warning("http.validation-failed", **log_kwargs)
        VALIDATION_FAILURES.labels(route=route).inc()
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        # The canonical traceback line (uvicorn's duplicate is filtered in
        # configure_logging). Route template, not raw path: bounded, no ids.
        route = route_template(request.scope)
        _log.exception(
            "unhandled-exception",
            request_id=request_id,
            route=route,
            method=request.method,
        )
        UNHANDLED_EXCEPTIONS.labels(route=route).inc()
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
