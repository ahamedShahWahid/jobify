"""Tests for the RFC 7807 error handler."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from kpa.app_factory import create_app


@pytest.fixture
def app_with_boom(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    app = create_app()

    @app.get("/boom-unhandled")
    def boom_unhandled() -> None:
        raise RuntimeError("kaboom")

    @app.get("/boom-http")
    def boom_http() -> None:
        raise HTTPException(status_code=404, detail="missing")

    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_problem_json(app_with_boom: TestClient) -> None:
    response = app_with_boom.get("/boom-unhandled")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["title"] == "Internal Server Error"
    assert body["status"] == 500
    assert body["type"] == "about:blank"
    assert body["request_id"] == response.headers["x-request-id"]
    # Internal error detail must not leak.
    assert "kaboom" not in body["detail"]


def test_http_exception_returns_problem_json(app_with_boom: TestClient) -> None:
    response = app_with_boom.get("/boom-http")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["detail"] == "missing"
    assert body["request_id"] == response.headers["x-request-id"]
