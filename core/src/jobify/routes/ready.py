"""Readiness endpoint — distinct from /health.

/health = liveness (process alive, can answer HTTP). No deps.
/ready  = readiness (downstream deps OK). Checked by load balancers and
          rolling-deploy gates; failing /ready takes the pod out of rotation
          without restarting it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.get("/ready", tags=["meta"])
async def ready(request: Request) -> JSONResponse:
    checks: dict[str, str] = {}
    overall_ok = True

    sm = request.app.state.db_sessionmaker
    try:
        async with sm() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except SQLAlchemyError as exc:
        # SQLAlchemy-wrapped driver errors (e.g. auth failure, unknown host via DNS).
        checks["db"] = f"error: {type(exc).__name__}"
        overall_ok = False
    except Exception as exc:  # asyncpg raises raw OSError, not SQLAlchemyError
        # asyncpg surfaces network-level failures (connection refused, unreachable host)
        # as raw OSError subclasses rather than wrapping them in SQLAlchemyError.
        # We catch Exception here deliberately at this boundary so a transient network
        # error returns 503 instead of propagating as an unhandled 500.
        checks["db"] = f"error: {type(exc).__name__}"
        overall_ok = False

    body: dict[str, Any] = {
        "status": "ready" if overall_ok else "not_ready",
        "checks": checks,
    }
    return JSONResponse(
        body,
        status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
