"""Log redaction — the last processor before rendering.

Runs on BOTH paths configured in :mod:`jobify.observability.logging`: native
structlog events and stdlib records rendered through ``ProcessorFormatter``.

Two guards, because key-based masking alone cannot see PII inside free text:

- values under a sensitive key (any depth, dicts and lists, case-insensitive)
  are replaced wholesale;
- email addresses in ANY string value — including the rendered ``exception``
  traceback, which carries exception messages such as Postgres
  ``Key (email)=(a@b.c)`` details — are masked in place.

The rule for new log calls stays "log shapes, never values"; this is the safety
net, not the policy. Adding a key here is reviewed like an invariant. A false
positive shows up as ``[REDACTED]`` and is fixed by renaming the log key.
"""

from __future__ import annotations

import re
from typing import Any, Final

from structlog.types import EventDict, WrappedLogger

SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "email",
        "recipient",
        "to",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "password",
        "secret",
        "api_key",
        "raw_text",
        "resume_text",
        "text",
        "body",
        "payload",
    }
)
REDACTED: Final[str] = "[REDACTED]"
REDACTED_EMAIL: Final[str] = "[REDACTED_EMAIL]"
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _redact_item(key: object, value: Any) -> Any:
    if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    return _scrub(value)


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return _EMAIL_RE.sub(REDACTED_EMAIL, value)
    if isinstance(value, dict):
        return {key: _redact_item(key, item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_scrub(item) for item in value]
    return value


def redact_sensitive(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """structlog processor: mask sensitive keys and email addresses.

    Underscore-prefixed keys are processor metadata (``_record``,
    ``_from_structlog``) and pass through untouched. On the stdlib path,
    ``ProcessorFormatter.remove_processors_meta`` already strips these before
    this processor runs; the guard here covers the native structlog path,
    where they are still present when a bound logger's context carries them.
    """
    return {
        key: value if key.startswith("_") else _redact_item(key, value)
        for key, value in event_dict.items()
    }
