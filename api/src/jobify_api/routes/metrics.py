"""Prometheus scrape endpoint.

Exposes the process-local HTTP counters as text exposition. Unauthenticated and
unversioned (an ops endpoint, like ``/health`` and ``/ready``) and excluded from
the OpenAPI schema (``include_in_schema=False``) — it's a scrape target, not part
of the public API contract.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import PlainTextResponse

from jobify_api.metrics import render_prometheus

router = APIRouter()

_PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(render_prometheus(), media_type=_PROMETHEUS_CONTENT_TYPE)
