"""RequestContextMiddleware: contextvar binding + one structured access line."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from jobify_api.app_factory import create_app
from tests.logging_helpers import json_log_lines, rebind_logging_per_request

_log = structlog.get_logger("test.request_context")


def _env(monkeypatch: pytest.MonkeyPatch, *, level: str = "INFO") -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", level)
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "json")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")


def _add_routes(app: FastAPI) -> None:
    @app.get("/_t/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        _log.info("inside-handler")
        return {"id": item_id}

    @app.get("/_t/bind-user")
    async def bind_user() -> dict[str, str]:
        # Simulates current_user's binding to prove the NEXT request starts clean.
        structlog.contextvars.bind_contextvars(user_id="leaky-user")
        return {}

    @app.get("/_t/missing")
    async def missing() -> None:
        raise HTTPException(status_code=404, detail="nope")

    @app.get("/_t/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")


@pytest.fixture
def app_client(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """A TestClient whose requests always log through the CALL-phase stream.

    See ``tests.logging_helpers.rebind_logging_per_request`` for why this is
    necessary — the same reason ``test_probe_access_lines_are_debug`` (which
    calls ``create_app()`` directly in the test body) never hits this. This
    suite additionally asserts the raw path + query string never appear,
    which is exactly what that helper's httpx silencing protects.
    """
    _env(monkeypatch)
    app = create_app()
    _add_routes(app)
    structlog.contextvars.clear_contextvars()
    with TestClient(app, raise_server_exceptions=False) as client:
        capsys.readouterr()
        rebind_logging_per_request(client, monkeypatch)
        yield client
    structlog.contextvars.clear_contextvars()


def _access_lines(output: str) -> list[dict[str, Any]]:
    return [line for line in json_log_lines(output) if line["event"] == "http.request"]


def test_one_access_line_with_route_template_and_request_id(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = app_client.get("/_t/items/abc?q=secret-search")

    output = capsys.readouterr().out
    (access,) = _access_lines(output)
    assert access["method"] == "GET"
    assert access["route"] == "/_t/items/{item_id}"
    assert access["status"] == 200
    assert access["level"] == "info"
    assert access["request_id"] == response.headers["x-request-id"]
    assert access["user_id"] is None
    assert isinstance(access["duration_ms"], int | float)
    # Never the query string or the raw path.
    assert "secret-search" not in output
    assert "/_t/items/abc" not in output


def test_handler_logs_carry_request_id(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = app_client.get("/_t/items/abc")

    lines = json_log_lines(capsys.readouterr().out)
    (inside,) = (line for line in lines if line["event"] == "inside-handler")
    assert inside["request_id"] == response.headers["x-request-id"]


def test_context_does_not_bleed_between_requests(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/_t/bind-user")
    second = app_client.get("/_t/items/abc")

    lines = json_log_lines(capsys.readouterr().out)
    (inside,) = (line for line in lines if line["event"] == "inside-handler")
    assert inside["request_id"] == second.headers["x-request-id"]
    assert "user_id" not in inside


def test_4xx_access_line_is_warning(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/_t/missing")

    (access,) = _access_lines(capsys.readouterr().out)
    assert access["status"] == 404
    assert access["level"] == "warning"


def test_unmatched_route_is_logged_with_placeholder(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/definitely/not/a/route/123")

    (access,) = _access_lines(capsys.readouterr().out)
    assert access["route"] == "__unmatched__"
    assert access["status"] == 404


def test_unhandled_exception_access_line_is_error_500(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/_t/boom")

    (access,) = _access_lines(capsys.readouterr().out)
    assert access["status"] == 500
    assert access["level"] == "error"
    assert access["route"] == "/_t/boom"


def test_probe_access_lines_are_debug(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(monkeypatch, level="INFO")
    with TestClient(create_app()) as client:
        capsys.readouterr()
        client.get("/health")
        assert _access_lines(capsys.readouterr().out) == []

    _env(monkeypatch, level="DEBUG")
    with TestClient(create_app()) as client:
        capsys.readouterr()
        client.get("/health")
        (access,) = _access_lines(capsys.readouterr().out)
        assert access["level"] == "debug"
        assert access["route"] == "/health"
