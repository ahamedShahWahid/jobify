"""Async SQLAlchemy session wiring.

Single-engine, single-schema (`jobify`). R/W routing is out of scope for this
plan — see IMPLEMENTATION_SPEC.md §5 for the eventual split design.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from jobify.settings import Settings

_SCHEMA = "jobify"


def create_engine_from_settings(
    settings: Settings | None = None,
    *,
    poolclass: Any = None,
) -> AsyncEngine:
    """Construct the application's async engine.

    Pool tuning is intentionally minimal here — production sizing happens via
    env vars in a later plan once we have load-test data.
    """
    settings = settings or Settings()
    kwargs: dict[str, Any] = {
        "echo": False,
        "pool_pre_ping": True,
        "connect_args": {"server_settings": {"search_path": _SCHEMA}},
    }
    if poolclass is not None:
        kwargs["poolclass"] = poolclass
    return create_async_engine(settings.db_url, **kwargs)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, close on exit, rollback on error.

    Pulls the sessionmaker off ``app.state`` so the engine is shared across
    requests. Routes use ``Depends(get_session)`` with no further wiring.
    """
    sm: async_sessionmaker[AsyncSession] = request.app.state.db_sessionmaker
    async with sm() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
