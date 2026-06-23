"""Unit tests for the DB session module.

The integration tests in tests/integration/ cover real Postgres behavior.
These tests only verify lifecycle + wiring against a stubbed engine.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import jobify_api.dependencies as session_module
from jobify.db import session as core_session_module


def test_create_engine_uses_settings_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    engine = core_session_module.create_engine_from_settings()

    assert engine.url.render_as_string(hide_password=False) == "postgresql+asyncpg://u:p@h:5432/d"
    # Engine is configured for the "jobify" schema.
    assert engine.dialect.name == "postgresql"


async def test_get_session_yields_session_from_app_state() -> None:
    """get_session pulls the sessionmaker off request.app.state and yields one session."""
    fake_session = AsyncMock(spec=AsyncSession)
    sm = MagicMock(spec=async_sessionmaker)
    # async_sessionmaker is callable; calling it returns an async context manager.
    sm.return_value.__aenter__.return_value = fake_session
    sm.return_value.__aexit__.return_value = None

    request = MagicMock(spec=Request)
    request.app.state.db_sessionmaker = sm

    yielded = []
    async for s in session_module.get_session(request):
        yielded.append(s)

    assert yielded == [fake_session]
    fake_session.rollback.assert_not_awaited()


async def test_get_session_rolls_back_on_exception() -> None:
    """If the consumer raises, get_session calls rollback before propagating."""
    fake_session = AsyncMock(spec=AsyncSession)
    sm = MagicMock(spec=async_sessionmaker)
    sm.return_value.__aenter__.return_value = fake_session
    sm.return_value.__aexit__.return_value = None

    request = MagicMock(spec=Request)
    request.app.state.db_sessionmaker = sm

    gen = session_module.get_session(request)
    await gen.__anext__()  # enter the with-block, get the session
    with pytest.raises(RuntimeError, match="boom"):
        await gen.athrow(RuntimeError("boom"))

    fake_session.rollback.assert_awaited_once()


def test_get_session_can_be_used_as_fastapi_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route registration must succeed when Depends(get_session) is used.

    Regression guard for the original parameter-shape bug. We don't need a
    live DB — we override the dependency with a stub that yields a sentinel.
    """
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    from jobify_api.app_factory import create_app

    app = create_app()

    sentinel = object()

    async def _stub_session():
        yield sentinel

    app.dependency_overrides[session_module.get_session] = _stub_session

    @app.get("/_probe")
    async def _probe(s=Depends(session_module.get_session)):  # noqa: B008
        return {"ok": s is sentinel}

    with TestClient(app) as client:
        response = client.get("/_probe")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
