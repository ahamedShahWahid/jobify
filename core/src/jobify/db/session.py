"""Async SQLAlchemy session wiring.

Single-engine, single-schema (`jobify`). R/W routing is out of scope for this
plan — see IMPLEMENTATION_SPEC.md §5 for the eventual split design.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_SCHEMA = "jobify"


class DatabaseSettings(Protocol):
    db_url: str
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout_seconds: float
    db_pool_recycle_seconds: int
    db_command_timeout_seconds: float


def create_engine_from_settings(
    settings: DatabaseSettings | None = None,
    *,
    poolclass: Any = None,
) -> AsyncEngine:
    """Construct the application's async engine.

    Pool size, overflow, wait/recycle, and asyncpg command timeout are
    environment-configurable. Tune their defaults from load-test evidence.
    """
    if settings is None:
        from jobify.settings import CoreSettings

        settings = CoreSettings()
    kwargs: dict[str, Any] = {
        "echo": False,
        "pool_pre_ping": True,
        "connect_args": {
            "server_settings": {"search_path": _SCHEMA},
            "command_timeout": settings.db_command_timeout_seconds,
        },
    }
    if poolclass is not None:
        kwargs["poolclass"] = poolclass
    else:
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
        )
    return create_async_engine(settings.db_url, **kwargs)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
