"""Health endpoint.

This is a liveness check only — no downstream dependency probes.
DB/Redis readiness probes land in a later plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from pydantic import BaseModel

from kpa import __version__
from kpa.settings import Environment

if TYPE_CHECKING:
    from kpa.settings import Settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    env: Environment


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(request: Request) -> HealthResponse:
    # Settings is parsed once at app startup and stored on app.state;
    # don't re-parse env vars per request.
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=__version__,
        env=settings.env,
    )
