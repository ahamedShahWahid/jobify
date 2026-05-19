"""Shared test fixtures + collection-time env defaults."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kpa.app_factory import create_app


def pytest_configure(config: object) -> None:
    """Set env-var defaults before pytest collects and imports test modules.

    Modules like ``kpa.workers.celery_app`` call ``Settings()`` at import time,
    which requires KPA_* env vars to be present *before* collection. ``monkeypatch``
    runs after collection, so it's too late for module-level Settings calls.
    ``os.environ.setdefault`` only writes when the key is absent — real shell
    env vars (e.g. CI overrides) are never shadowed.
    """
    os.environ.setdefault("KPA_ENV", "local")
    os.environ.setdefault("KPA_SERVICE_NAME", "kpa-api")
    os.environ.setdefault(
        "KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa_test"
    )
    os.environ.setdefault("KPA_REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient bound to a freshly created app with deterministic settings."""

    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")

    app = create_app()
    with TestClient(app) as c:
        yield c
