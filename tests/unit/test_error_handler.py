"""Tests for the RFC 7807 error handler."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from jobify_api.app_factory import create_app
from tests.logging_helpers import json_log_lines, rebind_logging_per_request


@pytest.fixture
def app_with_boom(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

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


class _Body(BaseModel):
    count: int


def _add_validation_route(app: FastAPI) -> None:
    @app.post("/validate/{item_id}")
    async def validate(item_id: int, body: _Body) -> dict[str, int]:
        return {"item_id": item_id, "count": body.count}


@pytest.fixture
def json_app(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "json")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")
    app = create_app()
    _add_validation_route(app)

    @app.get("/boom-503")
    async def boom_503() -> None:
        raise HTTPException(status_code=503, detail="dependency_unavailable")

    @app.get("/boom-404")
    async def boom_404() -> None:
        raise HTTPException(status_code=404, detail="missing")

    @app.get("/boom-unhandled/{item_id}")
    async def boom_unhandled(item_id: str) -> None:
        raise RuntimeError("kaboom")

    with TestClient(app, raise_server_exceptions=False) as client:
        capsys.readouterr()
        rebind_logging_per_request(client, monkeypatch)
        yield client


def test_validation_error_body_is_identical_to_fastapi_default(json_app: TestClient) -> None:
    plain = FastAPI()
    _add_validation_route(plain)
    payload = {"count": "not-a-number-alice@example.com"}

    ours = json_app.post("/validate/7", json=payload)
    default = TestClient(plain).post("/validate/7", json=payload)

    assert ours.status_code == default.status_code == 422
    assert ours.headers["content-type"] == default.headers["content-type"]
    assert ours.content == default.content


def test_validation_error_logs_field_shapes_not_values(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    json_app.post("/validate/7", json={"count": "secret-input-value"})

    output = capsys.readouterr().out
    (line,) = (x for x in json_log_lines(output) if x["event"] == "http.validation-failed")
    assert line["level"] == "warning"
    assert line["route"] == "/validate/{item_id}"
    assert line["fields"] == [{"loc": "body.count", "type": "int_parsing"}]
    assert "secret-input-value" not in output


def test_http_exception_5xx_logs_error(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = json_app.get("/boom-503")

    assert response.status_code == 503
    (line,) = (x for x in json_log_lines(capsys.readouterr().out) if x["event"] == "http.error")
    assert line["level"] == "error"
    assert line["status"] == 503
    assert line["detail"] == "dependency_unavailable"
    assert line["route"] == "/boom-503"
    assert line["request_id"] == response.headers["x-request-id"]


def test_http_exception_4xx_does_not_log_http_error(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    json_app.get("/boom-404")

    assert [x for x in json_log_lines(capsys.readouterr().out) if x["event"] == "http.error"] == []


def test_unhandled_exception_logs_one_traceback_with_route(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = json_app.get("/boom-unhandled/abc-123")

    output = capsys.readouterr().out
    lines = json_log_lines(output)
    (line,) = (x for x in lines if x["event"] == "unhandled-exception")
    assert line["route"] == "/boom-unhandled/{item_id}"
    assert line["request_id"] == response.headers["x-request-id"]
    assert "RuntimeError: kaboom" in line["exception"]
    assert "path" not in line
    assert sum("exception" in x for x in lines) == 1
