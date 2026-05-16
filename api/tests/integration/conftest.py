"""Integration test fixtures — real Postgres 16 from local Homebrew.

Per-test isolation strategy: each test gets an ``AsyncSession`` bound to a
connection that holds an outer transaction. The session uses SQLAlchemy 2.0's
``join_transaction_mode="create_savepoint"`` so test code can freely call
``await session.commit()`` — that commits a savepoint, not the outer txn — and
the fixture rolls back the outer transaction at teardown. No truncation, no
container churn, fast.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration


DEFAULT_TEST_DB_URL = "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa_test"


@pytest.fixture(scope="session")
def db_url() -> str:
    """Connection URL for the integration test database.

    Defaults to the local Homebrew Postgres set up in the README. Override
    via ``KPA_TEST_DB_URL`` in CI (where Postgres runs as a service
    container) or on a teammate's machine with a different layout.
    """
    return os.environ.get("KPA_TEST_DB_URL", DEFAULT_TEST_DB_URL)


@pytest.fixture(scope="session")
def monkeypatch_session() -> Iterator[pytest.MonkeyPatch]:
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="session")
def migrated_db(db_url: str, monkeypatch_session: pytest.MonkeyPatch) -> str:
    """Apply alembic upgrade head against the test database once per session."""
    monkeypatch_session.setenv("KPA_ENV", "local")
    monkeypatch_session.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch_session.setenv("KPA_DB_URL", db_url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    return db_url


@pytest_asyncio.fixture
async def session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """Per-test session with savepoint-based rollback isolation.

    Uses NullPool so that every test gets a fresh asyncpg connection bound to
    the current test's event loop. This avoids the ``attached to a different
    loop`` error that arises when a session-scoped engine's connection pool
    holds asyncpg connections tied to a previous test's event loop.
    """
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    async with engine.connect() as connection:
        trans = await connection.begin()
        sm = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with sm() as s:
            yield s
        await trans.rollback()
    await engine.dispose()


@pytest.fixture
def client(
    session: AsyncSession,
    db_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Sync test client for non-async tests.

    Uses TestClient (Starlette sync portal). Suitable only for routes that do
    NOT exercise asyncpg via a shared ``session`` fixture, because TestClient
    runs the ASGI app in a separate anyio event loop which conflicts with the
    asyncpg connection bound to the pytest-asyncio test-function event loop.

    For async tests that share a ``session``, use the ``async_client`` fixture.
    """
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _shared_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(
    session: AsyncSession,
    db_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client for async tests that share a ``session``.

    Uses httpx.AsyncClient with ASGITransport so the ASGI app executes in the
    same event loop as the async test function. This avoids the asyncpg
    ``Future attached to a different loop`` error that arises when TestClient's
    blocking portal creates its own event loop.
    """
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _shared_session

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
