"""Tests for the logging configuration."""

from __future__ import annotations

import logging

import pytest
import structlog

from kpa.observability.logging import configure_logging


def test_configure_logging_text_format_renders_key_equals_value(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

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
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

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
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    configure_logging()
    configure_logging()
    configure_logging()

    # Only one handler regardless of how many times configure_logging() runs.
    assert len(logging.getLogger().handlers) == 1
