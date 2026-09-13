"""Helpers for tests that assert on real rendered log output.

Use these with the REAL ``configure_logging`` chain + ``capsys`` — never
``structlog.testing.capture_logs()``, which replaces the processor chain and so
cannot prove redaction or stdlib routing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jobify.observability.logging import configure_logging


@dataclass(frozen=True)
class LogSettings:
    """Satisfies ``jobify.observability.logging.LoggingSettings``."""

    log_level: str = "INFO"
    log_format: str = "json"


def json_log_lines(output: str) -> list[dict[str, Any]]:
    """Parse every JSON log line in captured stdout (non-JSON lines skipped)."""
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def rebind_logging_per_request(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a TestClient's requests always log through the CALL-phase stream.

    pytest's ``capsys`` tears down and recreates its capture buffer between
    the setup and call phases (``CaptureManager.item_capture`` calls
    ``deactivate_fixture``/``activate_fixture`` around every phase). Building
    the app in a fixture (setup phase) binds ``configure_logging()``'s
    ``PrintLoggerFactory``/root handler to that phase's (about-to-be-closed)
    stream; making requests from the test body (call phase) against that
    stale binding raises ``ValueError: I/O operation on closed file`` inside
    the access-log call. Re-running ``configure_logging()`` immediately
    before each request rebinds it to the live call-phase stream.

    httpx's own request-line log (INFO, propagates to root) is silenced here
    too — it would otherwise print the raw path + query string, and it's a
    TestClient-only artifact (no httpx client exists in the request path
    production serves). The level is restored after the test via
    ``monkeypatch``, unlike an ad hoc set that never resets it.
    """
    httpx_logger = logging.getLogger("httpx")
    monkeypatch.setattr(httpx_logger, "level", logging.WARNING)
    real_request = client.request

    def _request(*args: Any, **kwargs: Any) -> Any:
        configure_logging()
        return real_request(*args, **kwargs)

    monkeypatch.setattr(client, "request", _request, raising=False)
