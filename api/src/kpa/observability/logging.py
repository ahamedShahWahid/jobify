"""Structured logging configuration.

Plain-text `key=value` output by default, compatible with Fluent Bit + ES.
JSON output is available via KPA_LOG_FORMAT=json for environments that prefer it.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

import structlog

from kpa.settings import Settings

_LEVEL_MAP: Final[dict[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging() -> None:
    """Initialize stdlib + structlog. Idempotent: handlers do not stack.

    Reconfigures structlog every call so the logger factory binds to the
    current ``sys.stdout`` (important for tests that patch stdout).
    """
    settings = Settings()
    level = _LEVEL_MAP[settings.log_level]

    # Stdlib root: replace any existing handlers with a single stdout handler.
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(level)

    renderer: structlog.types.Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.processors.KeyValueRenderer(
            key_order=["timestamp", "level", "logger", "event"],
            drop_missing=True,
        )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
