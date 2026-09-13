"""Helpers for tests that assert on real rendered log output.

Use these with the REAL ``configure_logging`` chain + ``capsys`` — never
``structlog.testing.capture_logs()``, which replaces the processor chain and so
cannot prove redaction or stdlib routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LogSettings:
    """Satisfies ``jobify.observability.logging.LoggingSettings``."""

    log_level: str = "INFO"
    log_format: str = "json"


def json_log_lines(output: str) -> list[dict[str, Any]]:
    """Parse every JSON log line in captured stdout (non-JSON lines skipped)."""
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]
