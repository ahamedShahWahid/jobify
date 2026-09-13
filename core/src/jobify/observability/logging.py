"""Structured logging configuration.

Plain-text `key=value` output by default, compatible with Fluent Bit + ES.
JSON output is available via JOBIFY_LOG_FORMAT=json for environments that prefer it.

Two paths, one format:

- structlog events render through the processor chain configured below;
- stdlib records (uvicorn, SQLAlchemy, httpx, Celery — anything using
  ``logging``) reach the single root handler, whose ``ProcessorFormatter`` runs
  the same context merge, redaction and renderer. Without it they print as a
  bare message with no level, timestamp or JSON.

structlog itself deliberately stays on ``PrintLoggerFactory`` (not a full
``structlog.stdlib`` migration): output capture in the existing suite depends on
it, and routing only the foreign records gets the same result.
"""

from __future__ import annotations

import logging
import sys
from typing import Final, Protocol

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

from jobify.observability.redaction import redact_sensitive
from jobify.settings import CoreSettings, LogFormat, LogLevel


class LoggingSettings(Protocol):
    log_level: LogLevel
    log_format: LogFormat


_LEVEL_MAP: Final[dict[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# uvicorn installs its own handlers with propagate=False before importing the
# app; resetting them sends its records through the root handler below.
_UVICORN_LOGGERS: Final[tuple[str, ...]] = ("uvicorn", "uvicorn.error", "uvicorn.access")


class DropUvicornDuplicateTraceback(logging.Filter):
    """Drop uvicorn's copy of an unhandled-exception traceback.

    Starlette's ServerErrorMiddleware always re-raises after our exception
    handler has logged the canonical ``unhandled-exception`` line, and uvicorn
    then logs the same traceback again as "Exception in ASGI application".
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == "uvicorn.error"
            and record.getMessage().startswith("Exception in ASGI application")
        )


def _drop_color_message(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    # uvicorn attaches an ANSI-coloured duplicate of every message as an extra.
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(settings: LoggingSettings | None = None) -> None:
    """Initialize stdlib + structlog. Idempotent: handlers do not stack.

    Reconfigures structlog every call so the logger factory binds to the
    current ``sys.stdout`` (important for tests that patch stdout).
    """
    settings = settings or CoreSettings()
    level = _LEVEL_MAP[settings.log_level]

    renderer: Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.processors.KeyValueRenderer(
            key_order=["timestamp", "level", "logger", "event"],
            drop_missing=True,
        )

    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    # Stdlib root: replace any existing handlers with a single stdout handler.
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[
                *shared,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.ExtraAdder(),
                _drop_color_message,
            ],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                redact_sensitive,
                renderer,
            ],
        )
    )
    handler.addFilter(DropUvicornDuplicateTraceback())
    root.addHandler(handler)
    root.setLevel(level)

    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    structlog.configure(
        processors=[
            *shared,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_sensitive,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
