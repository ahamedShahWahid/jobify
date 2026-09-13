"""Telemetry for calls to external providers (Gemini, SES, S3, Google JWKS).

    with observe_external_call("gemini", "embed"):
        resp = await client.aio.models.embed_content(...)

Records ``jobify_external_calls_total{service,operation,outcome}`` and
``jobify_external_call_duration_seconds{service,operation}``, and logs one
``external.call`` event: DEBUG on success, WARNING on failure. It NEVER swallows —
the exception propagates unchanged.

``service``/``operation`` must be literal strings from the closed set documented
in core/CLAUDE.md (metric cardinality). Pass ``log_traceback=False`` when the
provider's exception message can carry request/user content (e.g. SES errors
echo recipient addresses): the event then carries ``error_type`` and
``http_status`` only.

BaseExceptions (cancellation, KeyboardInterrupt) propagate without being
counted as provider errors.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

import structlog

from jobify.observability.metrics import EXTERNAL_CALL_DURATION, EXTERNAL_CALLS

_log = structlog.get_logger(__name__)


def http_status_of(exc: BaseException) -> int | None:
    """Best-effort HTTP status from the provider exception shapes we use."""
    response: Any = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)  # httpx.HTTPStatusError
    if isinstance(status, int):
        return status
    if isinstance(response, dict):  # botocore ClientError
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("HTTPStatusCode"), int):
            return int(metadata["HTTPStatusCode"])
    code = getattr(exc, "code", None)  # google.genai.errors.APIError
    return code if isinstance(code, int) and not isinstance(code, bool) else None


@contextmanager
def observe_external_call(
    service: str, operation: str, *, log_traceback: bool = True
) -> Iterator[None]:
    started_at = perf_counter()
    try:
        yield
    except Exception as exc:
        duration_seconds = max(perf_counter() - started_at, 0.0)
        EXTERNAL_CALLS.labels(service=service, operation=operation, outcome="error").inc()
        EXTERNAL_CALL_DURATION.labels(service=service, operation=operation).observe(
            duration_seconds
        )
        _log.warning(
            "external.call",
            service=service,
            operation=operation,
            outcome="error",
            error_type=type(exc).__name__,
            http_status=http_status_of(exc),
            duration_ms=round(duration_seconds * 1000, 1),
            **({"exc_info": True} if log_traceback else {}),
        )
        raise
    duration_seconds = max(perf_counter() - started_at, 0.0)
    EXTERNAL_CALLS.labels(service=service, operation=operation, outcome="success").inc()
    EXTERNAL_CALL_DURATION.labels(service=service, operation=operation).observe(duration_seconds)
    _log.debug(
        "external.call",
        service=service,
        operation=operation,
        outcome="success",
        duration_ms=round(duration_seconds * 1000, 1),
    )
