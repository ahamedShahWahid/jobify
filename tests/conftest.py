"""Shared test fixtures + collection-time env defaults."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from jobify.app_factory import create_app


def pytest_configure(config: object) -> None:
    """Set env-var defaults before pytest collects and imports test modules.

    Modules like ``jobify.workers.celery_app`` call ``Settings()`` at import time,
    which requires JOBIFY_* env vars to be present *before* collection. ``monkeypatch``
    runs after collection, so it's too late for module-level Settings calls.
    ``os.environ.setdefault`` only writes when the key is absent — real shell
    env vars (e.g. CI overrides) are never shadowed.
    """
    os.environ.setdefault("JOBIFY_ENV", "local")
    os.environ.setdefault("JOBIFY_SERVICE_NAME", "jobify-api")
    os.environ.setdefault(
        "JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify_test"
    )
    os.environ.setdefault("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("JOBIFY_JWT_SECRET", "x" * 32)
    os.environ.setdefault("JOBIFY_GEMINI_API_KEY", "test-gemini-key")
    os.environ.setdefault(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient bound to a freshly created app with deterministic settings."""

    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    app = create_app()
    with TestClient(app) as c:
        yield c
