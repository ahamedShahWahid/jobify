"""FastAPI application factory.

`create_app()` builds a fresh app on every call so tests get isolation.
"""

from __future__ import annotations

from fastapi import FastAPI

from kpa import __version__
from kpa.middleware.error_handler import register_error_handlers
from kpa.middleware.request_id import RequestIdMiddleware
from kpa.observability.logging import configure_logging
from kpa.routes import health
from kpa.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()  # validated; raises on misconfiguration
    configure_logging()
    app = FastAPI(
        title="Khan Placement Agency API",
        version=__version__,
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    # /health is intentionally not under /v1 — ALB and Kubernetes probes target
    # it directly. Versioned API routes will be mounted with prefix="/v1" later.
    app.include_router(health.router)
    return app
