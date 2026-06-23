"""FastAPI request-scoped dependencies (session + storage).

Extracted from jobify.db.session and jobify.integrations.storage.base so
that the core domain package stays FastAPI-free.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.integrations.storage.base import Storage


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, close on exit, rollback on error.

    Pulls the sessionmaker off ``app.state`` so the engine is shared across
    requests. Routes use ``Depends(get_session)`` with no further wiring.
    """
    sm = request.app.state.db_sessionmaker
    async with sm() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_storage(request: Request) -> Storage:
    """FastAPI dependency: pull the configured Storage off ``app.state``."""
    storage: Storage = request.app.state.storage
    return storage
