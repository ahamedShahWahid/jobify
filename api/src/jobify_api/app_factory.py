"""FastAPI application factory.

`create_app()` builds a fresh app on every call so tests get isolation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware

from jobify import __version__
from jobify.db.session import create_engine_from_settings, make_sessionmaker
from jobify.integrations.storage import create_storage
from jobify.observability.logging import configure_logging
from jobify_api.auth.google_verifier import JwksGoogleIdTokenVerifier
from jobify_api.middleware.error_handler import register_error_handlers
from jobify_api.middleware.metrics import MetricsMiddleware
from jobify_api.middleware.request_id import RequestIdMiddleware
from jobify_api.rate_limit import RedisRateLimiter
from jobify_api.routes import (
    admin,
    applicants,
    applications,
    auth,
    consents,
    dsr,
    employers,
    feed,
    health,
    invites,
    jobs,
    me,
    metrics,
    notifications,
    ready,
    resumes,
    saved_jobs,
)
from jobify_api.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()  # validated; raises on misconfiguration
    configure_logging(settings)
    engine = create_engine_from_settings(settings)
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await redis_client.aclose()
        await engine.dispose()  # release asyncpg connections on shutdown

    app = FastAPI(
        title="Jobify API",
        version=__version__,
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.db_engine = engine
    app.state.db_sessionmaker = make_sessionmaker(engine)
    app.state.redis = redis_client
    app.state.rate_limiter = RedisRateLimiter(redis_client)
    app.state.storage = create_storage(settings)
    app.state.google_verifier = JwksGoogleIdTokenVerifier(
        jwks_url=settings.google_jwks_url,
        accepted_client_ids=list(settings.google_oauth_client_ids),
        cache_ttl_seconds=settings.google_jwks_cache_ttl_seconds,
    )
    app.add_middleware(RequestIdMiddleware)
    # MetricsMiddleware wraps RequestIdMiddleware (counts real routed requests,
    # including HTTPException/500 responses) but stays INSIDE CORS below, so CORS
    # preflight (OPTIONS) short-circuits are not counted. Pure-ASGI (see metrics.py).
    app.add_middleware(MetricsMiddleware)
    # Added after RequestIdMiddleware so it wraps it (outermost): CORS handles the
    # browser preflight (OPTIONS) and stamps Access-Control-* on every response,
    # including errors. Starlette's CORSMiddleware is pure-ASGI, so it's safe
    # alongside RequestIdMiddleware (see the BaseHTTPMiddleware note in CLAUDE.md).
    # Bearer-token auth (no cookies) → allow_credentials stays False.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    register_error_handlers(app)
    # /health is intentionally not under /v1 — ALB and Kubernetes probes target
    # it directly. Versioned API routes will be mounted with prefix="/v1" later.
    app.include_router(health.router)
    app.include_router(ready.router)
    app.include_router(metrics.router)  # /metrics — ops scrape, include_in_schema=False
    app.include_router(resumes.router)
    app.include_router(applicants.router)
    app.include_router(employers.router)
    app.include_router(invites.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(feed.router)
    app.include_router(jobs.router)
    app.include_router(applications.router)
    app.include_router(saved_jobs.router)
    app.include_router(notifications.router)
    app.include_router(consents.router)
    app.include_router(dsr.router)
    app.include_router(admin.router)

    return app
