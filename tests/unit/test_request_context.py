"""RequestContextMiddleware: contextvar binding + one structured access line."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from jobify_api.app_factory import create_app
from jobify_api.middleware.request_context import RequestContextMiddleware
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


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.disconnect"}


async def _noop_send(_message: dict[str, Any]) -> None:
    return None


def test_context_cleared_between_calls_in_one_asyncio_context() -> None:
    """Drive RequestContextMiddleware TWICE within one asyncio context directly.

    ``test_context_does_not_bleed_between_requests`` below uses a TestClient,
    whose requests each run in a COPIED contextvars context — it would pass
    even if ``clear_contextvars()`` were deleted from the middleware, since
    the copy alone would isolate them. Calling ``__call__`` twice in a row
    inside one ``asyncio.run()`` shares a single context, so only the
    middleware's own clear can isolate the second call. Confirmed to fail
    (the ``user_id`` assertion) with ``clear_contextvars()`` temporarily
    commented out in ``RequestContextMiddleware.__call__`` — see the fix
    report for that run's output.
    """
    captured: dict[str, Any] = {}

    async def inner_app_first(_scope: dict[str, Any], _receive: object, _send: object) -> None:
        # Simulates current_user binding user_id mid-request.
        structlog.contextvars.bind_contextvars(user_id="leaky-user")

    async def inner_app_second(_scope: dict[str, Any], _receive: object, _send: object) -> None:
        captured["ctx"] = structlog.contextvars.get_contextvars()

    first = RequestContextMiddleware(inner_app_first)  # type: ignore[arg-type]
    second = RequestContextMiddleware(inner_app_second)  # type: ignore[arg-type]

    async def scenario() -> None:
        scope1: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "state": {"request_id": "req-1"},
        }
        await first(scope1, _noop_receive, _noop_send)  # type: ignore[arg-type]

        scope2: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "state": {"request_id": "req-2"},
        }
        await second(scope2, _noop_receive, _noop_send)  # type: ignore[arg-type]

    asyncio.run(scenario())

    ctx = captured["ctx"]
    assert ctx["request_id"] == "req-2"
    assert "user_id" not in ctx


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
        client.get("/definitely/not/a/route/456")
        lines = _access_lines(capsys.readouterr().out)
        # Anchor: a non-probe route's access line IS present at INFO — proves
        # JSON logging is actually configured, so the `/health` assertion
        # below isn't vacuously true because nothing was logged at all.
        assert [line["route"] for line in lines] == ["__unmatched__"]

    _env(monkeypatch, level="DEBUG")
    with TestClient(create_app()) as client:
        capsys.readouterr()
        client.get("/health")
        (access,) = _access_lines(capsys.readouterr().out)
        assert access["level"] == "debug"
        assert access["route"] == "/health"
