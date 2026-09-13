"""Tests for the logging configuration."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from uuid import uuid4

import pytest
import structlog

from jobify.observability.logging import DropUvicornDuplicateTraceback, configure_logging
from tests.logging_helpers import LogSettings, json_log_lines


def test_configure_logging_text_format_renders_key_equals_value(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    configure_logging()
    log = structlog.get_logger("test")
    log.info("hello", user_id="u-1", path="/health")

    captured = capsys.readouterr().out
    # KeyValueRenderer uses repr() for values, so strings are quoted.
    # Assert on substrings to stay renderer-quoting-agnostic.
    assert "hello" in captured
    assert "user_id" in captured and "u-1" in captured
    assert "path" in captured and "/health" in captured


def test_configure_logging_respects_log_level(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    configure_logging()
    log = structlog.get_logger("test")
    log.info("should-not-appear")
    log.warning("should-appear")

    captured = capsys.readouterr().out
    assert "should-not-appear" not in captured
    assert "should-appear" in captured


def test_configure_logging_does_not_stack_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    configure_logging()
    configure_logging()
    configure_logging()

    # Only one handler regardless of how many times configure_logging() runs.
    assert len(logging.getLogger().handlers) == 1


@pytest.fixture(autouse=True)
def _clear_log_context() -> Iterator[None]:
    # configure_logging() under capsys freezes the capsys capture stream into
    # both the structlog PrintLogger and the root StreamHandler (neither has a
    # "resolve current stdout at print time" escape hatch once bound). Left in
    # place, that stale, closed stream leaks into later test modules that call
    # structlog.get_logger() outside of capsys — restore global logging state
    # so this module's capsys-based tests never escape it. Deviation from the
    # brief's contextvars-only fixture; see task-1-report.md.
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def test_stdlib_records_render_through_structlog_as_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    logging.getLogger("httpx").warning("pool %s exhausted", "primary")

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["event"] == "pool primary exhausted"
    assert line["level"] == "warning"
    assert line["logger"] == "httpx"
    assert "timestamp" in line


def test_contextvars_are_merged_into_stdlib_records(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()
    structlog.contextvars.bind_contextvars(request_id="req-1")

    logging.getLogger("sqlalchemy.engine").error("boom")

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["request_id"] == "req-1"


def test_sensitive_keys_redacted_at_any_depth_case_insensitive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()
    user_id = str(uuid4())

    structlog.get_logger("t").info(
        "signin",
        user_id=user_id,
        id_token="eyJ.secret",
        nested={"Authorization": "Bearer abc", "ok": 1},
        items=[{"EMAIL": "a@b.co"}, {"kind": "x"}],
    )

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["user_id"] == user_id  # UUIDs are correlation handles, kept
    assert line["id_token"] == "[REDACTED]"
    assert line["nested"] == {"Authorization": "[REDACTED]", "ok": 1}
    assert line["items"] == [{"EMAIL": "[REDACTED]"}, {"kind": "x"}]


def test_sensitive_stdlib_extras_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    logging.getLogger("httpx").warning(
        "request failed", extra={"authorization": "Bearer abc", "status_code": 403}
    )

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["authorization"] == "[REDACTED]"
    assert line["status_code"] == 403


def test_emails_scrubbed_from_messages_and_tracebacks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    try:
        raise ValueError("Key (email)=(bob@example.com) already exists")
    except ValueError:
        structlog.get_logger("t").exception("native-failure")
        logging.getLogger("sqlalchemy").exception("stdlib-failure for carol@example.org")

    output = capsys.readouterr().out
    assert "bob@example.com" not in output
    assert "carol@example.org" not in output
    native, stdlib = json_log_lines(output)
    assert "[REDACTED_EMAIL]" in native["exception"]
    assert "[REDACTED_EMAIL]" in stdlib["exception"]
    assert stdlib["event"] == "stdlib-failure for [REDACTED_EMAIL]"


def test_uvicorn_loggers_propagate_to_root_after_configure() -> None:
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.addHandler(logging.StreamHandler(sys.stderr))
    uvicorn_error.propagate = False

    configure_logging(LogSettings())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True


def test_uvicorn_duplicate_asgi_traceback_is_dropped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()
    uvicorn_error = logging.getLogger("uvicorn.error")

    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        uvicorn_error.error("Exception in ASGI application\n", exc_info=True)
    uvicorn_error.info("Application startup complete.")

    lines = json_log_lines(capsys.readouterr().out)
    assert [line["event"] for line in lines] == ["Application startup complete."]


def test_duplicate_filter_only_matches_uvicorn_error() -> None:
    drop = DropUvicornDuplicateTraceback()

    def record(name: str, msg: str) -> logging.LogRecord:
        return logging.LogRecord(name, logging.ERROR, __file__, 1, msg, None, None)

    assert drop.filter(record("uvicorn.error", "Exception in ASGI application\n")) is False
    assert drop.filter(record("myapp", "Exception in ASGI application\n")) is True
    assert drop.filter(record("uvicorn.error", "Shutting down")) is True


def test_uvicorn_color_message_extra_is_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    logging.getLogger("uvicorn.error").info(
        "Started server process", extra={"color_message": "\x1b[1mStarted\x1b[0m"}
    )

    (line,) = json_log_lines(capsys.readouterr().out)
    assert "color_message" not in line
