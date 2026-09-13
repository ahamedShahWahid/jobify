"""Primary-with-fallback composite over two ResumeParser impls.

Policy in one testable place: try the primary; if it fails for any reason
OTHER than a plain extraction :class:`ParserError` or a :class:`TransientParserError`
(corrupt file, password protected — permanent regardless of parser; transient
extraction/storage hiccup — retried by Celery), log and run the fallback on
the same input. :class:`LlmParserError` is deliberately caught BEFORE its
parent ``ParserError`` — order matters.
"""

from __future__ import annotations

import structlog

from jobify.integrations.parser.base import (
    LlmParserError,
    ParsedResume,
    ParserError,
    ResumeParser,
    TransientParserError,
)

_log = structlog.get_logger(__name__)


class FallbackResumeParser:
    """Try ``primary``; degrade to ``fallback`` unless extraction itself failed."""

    def __init__(self, *, primary: ResumeParser, fallback: ResumeParser) -> None:
        self._primary = primary
        self._fallback = fallback

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        try:
            return await self._primary.parse(content=content, content_type=content_type)
        except TransientParserError:
            # Transient extraction/storage failure: let Celery retry the whole
            # parse (LLM path included) instead of silently degrading.
            raise
        except LlmParserError as exc:
            # Our own slug messages are PII-free; no traceback — the chained
            # cause can be a ValidationError whose text is the resume itself.
            _log.warning("parse.llm-failed", error_class=type(exc).__name__, reason=str(exc))
        except ParserError:
            # Extraction failure — permanent for the fallback too; re-raise.
            raise
        except Exception as exc:  # noqa: BLE001 — degradation boundary by design
            _log.warning("parse.llm-failed", error_class=type(exc).__name__)
        return await self._fallback.parse(content=content, content_type=content_type)
