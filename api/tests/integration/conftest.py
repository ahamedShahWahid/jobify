"""Integration test fixtures — real Postgres 16 from local Homebrew.

Per-test isolation strategy: each test gets an ``AsyncSession`` bound to a
connection that holds an outer transaction. The session uses SQLAlchemy 2.0's
``join_transaction_mode="create_savepoint"`` so test code can freely call
``await session.commit()`` — that commits a savepoint, not the outer txn — and
the fixture rolls back the outer transaction at teardown. No truncation, no
container churn, fast.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
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
from kpa.integrations.embeddings import EmbeddingResult, EmbeddingTask

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


@dataclass
class FakeEmbeddingProvider:
    """Deterministic 1536-dim vector derived from sha256 of input text.

    Each call appends a tuple (text, task, title) to ``.calls`` so tests can
    assert on call count and exact arguments.
    """

    calls: list[tuple[str, EmbeddingTask, str | None]] = field(default_factory=list)
    model_name: str = "fake-test-model"

    async def encode(
        self,
        *,
        text: str,
        task: EmbeddingTask,
        title: str | None = None,
    ) -> EmbeddingResult:
        self.calls.append((text, task, title))
        h = hashlib.sha256(text.encode()).digest()
        # Tile 32 bytes into 1536 floats in [-1, 1] — deterministic, no randomness.
        values = [((b / 255.0) * 2.0 - 1.0) for b in (h * 48)][:1536]
        return EmbeddingResult(
            values=values,
            model_name=self.model_name,
            input_tokens=max(1, len(text) // 4),
        )


@pytest.fixture
def embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def patched_embedding_provider(
    monkeypatch: pytest.MonkeyPatch,
    embedding_provider: FakeEmbeddingProvider,
) -> FakeEmbeddingProvider:
    """Patch get_embedding_provider() to return the fake so eager-mode Celery
    embed tasks use the fake without hitting the network.

    Two patches are needed because embed.py imports get_embedding_provider by
    name at module load time (``from kpa.workers.celery_app import
    get_embedding_provider``), creating a local reference that is not affected
    by patching the celery_app module attribute alone.  We therefore patch both
    the celery_app attribute and the embed-module local reference.  We also set
    the module-level ``_embedding_provider`` cache directly so that the original
    (unpatched) function body, if somehow reached, also returns the fake.
    """
    import kpa.workers.celery_app as cel
    import kpa.workers.tasks.embed as embed_mod

    monkeypatch.setattr(cel, "get_embedding_provider", lambda: embedding_provider)
    monkeypatch.setattr(embed_mod, "get_embedding_provider", lambda: embedding_provider)
    # Also seed the module-level cache so the original function body short-circuits.
    monkeypatch.setattr(cel, "_embedding_provider", embedding_provider)
    return embedding_provider


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
    monkeypatch_session.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch_session.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch_session.setenv("KPA_GEMINI_API_KEY", "test-gemini-key")
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    google_verifier: FakeGoogleIdTokenVerifier,
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
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GEMINI_API_KEY", "test-gemini-key")
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    google_verifier: FakeGoogleIdTokenVerifier,
) -> AsyncIterator[AsyncClient]:
    """Async HTTP client for async tests that share a ``session``.

    Uses httpx.AsyncClient with ASGITransport so the ASGI app executes in the
    same event loop as the async test function. This avoids the asyncpg
    ``Future attached to a different loop`` error that arises when TestClient's
    blocking portal creates its own event loop.
    """
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GEMINI_API_KEY", "test-gemini-key")
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def concurrent_async_client(
    migrated_db: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    google_verifier: FakeGoogleIdTokenVerifier,
) -> AsyncIterator[AsyncClient]:
    """AsyncClient that uses a real connection pool (no shared session override).

    Required for concurrency tests: each HTTP request gets its own DB
    connection so ``SELECT … FOR UPDATE`` actually serialises concurrent callers
    on the same token.  Uses NullPool for the cleanup engine so there is no
    pool-reuse interference with the app's own pool.

    Isolation: the fixture truncates all auth-related tables after the test so
    subsequent tests start clean (same guarantee as the savepoint rollback
    strategy used by the other fixtures, just achieved differently).
    """
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", migrated_db)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    from kpa.app_factory import create_app

    app = create_app()
    app.dependency_overrides[get_google_verifier] = lambda: google_verifier

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await app.state.db_engine.dispose()

    # Truncate in FK-safe order so subsequent tests start with a clean slate.
    cleanup_engine = create_async_engine(migrated_db, poolclass=NullPool)
    async with cleanup_engine.connect() as conn:
        await conn.execute(
            text(
                "TRUNCATE kpa.jobs, kpa.employers, kpa.resumes, kpa.refresh_tokens,"
                " kpa.oauth_identities, kpa.applicant_embeddings, kpa.applicants,"
                " kpa.users RESTART IDENTITY CASCADE"
            )
        )
        await conn.commit()
    await cleanup_engine.dispose()
