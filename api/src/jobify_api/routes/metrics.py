"""Prometheus scrape endpoint.

Exposes process-local HTTP counters as text exposition. It is unversioned and
excluded from OpenAPI. ``JOBIFY_METRICS_BEARER_TOKEN`` protects the endpoint and
is mandatory in staging/prod; local development may leave it unset.
"""

from __future__ import annotations

import hmac

import structlog
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import PlainTextResponse

from jobify_api.metrics import render_prometheus
from jobify_api.operational_metrics import render_async_work_metrics

router = APIRouter()

_PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
_log = structlog.get_logger(__name__)


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> PlainTextResponse:
    # async on purpose: a sync handler runs in a threadpool, where
    # render_prometheus iterating _REQUEST_COUNTS would race the event loop's
    # record_request mutating it ("dictionary changed size during iteration").
    # Staying on the event loop keeps render's lock-free iteration atomic.
    configured = request.app.state.settings.metrics_bearer_token
    if configured is not None:
        expected = f"Bearer {configured.get_secret_value()}"
        supplied = request.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="invalid_metrics_token")
    process_metrics = render_prometheus()
    try:
        async with request.app.state.db_sessionmaker() as session:
            queue_metrics = await render_async_work_metrics(session)
    except Exception:
        _log.exception("metrics.async-work-query-failed")
        queue_metrics = "jobify_async_metrics_up 0\n"
    return PlainTextResponse(
        process_metrics + queue_metrics,
        media_type=_PROMETHEUS_CONTENT_TYPE,
    )
