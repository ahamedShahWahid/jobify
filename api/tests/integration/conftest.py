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
from dataclasses import dataclass

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from kpa.auth.google_verifier import (
    GoogleClaims,
    InvalidGoogleTokenError,
    get_google_verifier,
)

pytestmark = pytest.mark.integration


@dataclass
class FakeGoogleIdTokenVerifier:
    """Test double: opaque token strings → canned :class:`GoogleClaims`.

    Use this via the ``google_verifier`` fixture; the integration ``client``
    and ``async_client`` fixtures override
    ``app.dependency_overrides[get_google_verifier]`` to return it.
    """

    canned: dict[str, GoogleClaims]

    async def verify(self, id_token: str) -> GoogleClaims:
        if id_token in self.canned:
            return self.canned[id_token]
        raise InvalidGoogleTokenError()


@pytest.fixture
def google_verifier() -> FakeGoogleIdTokenVerifier:
    """A fresh fake per test, with no canned tokens.

    Tests populate ``.canned`` to register their tokens, e.g.:

        google_verifier.canned["applicant_a_token"] = GoogleClaims(...)
    """
    return FakeGoogleIdTokenVerifier(canned={})


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
    monkeypatch_session.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch_session.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )
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
    monkeypatch: pytest.MonkeyPatch,
    google_verifier: FakeGoogleIdTokenVerifier,
) -> Iterator[TestClient]:
    """TestClient wired to the per-test DB session + fake Google verifier."""
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _shared_session
    app.dependency_overrides[get_google_verifier] = lambda: google_verifier

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(
    session: AsyncSession,
    db_url: str,
    monkeypatch: pytest.MonkeyPatch,
    google_verifier: FakeGoogleIdTokenVerifier,
) -> AsyncIterator[AsyncClient]:
    """AsyncClient wired to the per-test DB session + fake Google verifier."""
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _shared_session
    app.dependency_overrides[get_google_verifier] = lambda: google_verifier

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
