"""Prometheus scrape endpoint.

Renders the process (or, in multiprocess mode, all API processes') metrics from
``jobify.observability.metrics.build_registry()`` plus the DB-backed async-work
gauges from a per-scrape collector. Unversioned and excluded from OpenAPI.
``JOBIFY_METRICS_BEARER_TOKEN`` protects the endpoint and is mandatory in
staging/prod; local development may leave it unset.
"""

from __future__ import annotations

import hmac

import structlog
from fastapi import APIRouter, HTTPException, Request
from prometheus_client import CONTENT_TYPE_PLAIN_0_0_4, CollectorRegistry, generate_latest
from starlette.responses import Response

from jobify.observability.metrics import build_registry
from jobify_api.operational_metrics import (
    AsyncWorkCollector,
    AsyncWorkSnapshot,
    fetch_async_work_snapshot,
)

router = APIRouter()

_log = structlog.get_logger(__name__)


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    configured = request.app.state.settings.metrics_bearer_token
    if configured is not None:
        expected = f"Bearer {configured.get_secret_value()}"
        supplied = request.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="invalid_metrics_token")

    snapshot: AsyncWorkSnapshot | None
    try:
        async with request.app.state.db_sessionmaker() as session:
            snapshot = await fetch_async_work_snapshot(session)
    except Exception:  # noqa: BLE001 — scrape must succeed even when the DB is down (reports jobify_async_metrics_up 0)
        _log.exception("metrics.async-work-query-failed")
        snapshot = None

    # A separate per-scrape registry: the collector holds this scrape's snapshot,
    # and the process registry may be the global REGISTRY (single-process mode).
    scrape_registry = CollectorRegistry()
    scrape_registry.register(AsyncWorkCollector(snapshot))
    body = generate_latest(build_registry()) + generate_latest(scrape_registry)
    return Response(content=body, media_type=CONTENT_TYPE_PLAIN_0_0_4)
