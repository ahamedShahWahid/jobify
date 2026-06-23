"""End-to-end /ready checks against a real Postgres."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_ready_returns_200_when_db_reachable(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", db_url)
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    from jobify_api.app_factory import create_app  # import after env is set

    with TestClient(create_app()) as c:
        response = c.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.integration
def test_ready_returns_503_when_db_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv(
        "JOBIFY_DB_URL",
        "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none",  # unreachable
    )
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    from jobify_api.app_factory import create_app

    # raise_server_exceptions=False is NOT needed — the /ready handler catches all
    # exceptions (including bare OSError from asyncpg) and returns 503 gracefully.
    # Kept False as a safety net so asyncpg teardown noise doesn't fail the test.
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        response = c.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "db" in body.get("checks", {})
