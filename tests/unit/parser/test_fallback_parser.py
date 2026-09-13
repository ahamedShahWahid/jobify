"""FallbackResumeParser — primary/fallback routing and error layering."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from jobify.integrations.parser import (
    FallbackResumeParser,
    LlmParserError,
    ParsedResume,
    ParserError,
    TransientParserError,
)


class _StubParser:
    def __init__(self, *, result: ParsedResume | None = None, raises: Exception | None = None):
        self.calls = 0
        self._result = result
        self._raises = raises

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


def _resume(name: str) -> ParsedResume:
    return ParsedResume(parser_name=name, raw_text="x")


async def _run(parser: FallbackResumeParser) -> ParsedResume:
    return await parser.parse(content=b"pdf-bytes", content_type="application/pdf")


def test_primary_success_never_calls_fallback() -> None:
    import asyncio

    primary = _StubParser(result=_resume("llm.gemini.v1"))
    fallback = _StubParser(result=_resume("library.v1"))
    parsed = asyncio.run(_run(FallbackResumeParser(primary=primary, fallback=fallback)))
    assert parsed.parser_name == "llm.gemini.v1"
    assert fallback.calls == 0


def test_llm_error_falls_back() -> None:
    import asyncio

    primary = _StubParser(raises=LlmParserError("llm_invalid_json"))
    fallback = _StubParser(result=_resume("library.v1"))
    parsed = asyncio.run(_run(FallbackResumeParser(primary=primary, fallback=fallback)))
    assert parsed.parser_name == "library.v1"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_unexpected_exception_falls_back() -> None:
    import asyncio

    primary = _StubParser(raises=RuntimeError("socket burp"))
    fallback = _StubParser(result=_resume("library.v1"))
    parsed = asyncio.run(_run(FallbackResumeParser(primary=primary, fallback=fallback)))
    assert parsed.parser_name == "library.v1"


def test_extraction_parser_error_propagates_uncaught() -> None:
    import asyncio

    primary = _StubParser(raises=ParserError("password_protected"))
    fallback = _StubParser(result=_resume("library.v1"))
    with pytest.raises(ParserError) as exc_info:
        asyncio.run(_run(FallbackResumeParser(primary=primary, fallback=fallback)))
    assert str(exc_info.value) == "password_protected"
    assert fallback.calls == 0


async def test_transient_extraction_error_propagates_for_retry() -> None:
    primary = _StubParser(raises=TransientParserError("storage hiccup"))
    fallback = _StubParser(result=_resume("library.v1"))
    parser = FallbackResumeParser(primary=primary, fallback=fallback)
    with pytest.raises(TransientParserError):
        await parser.parse(content=b"x", content_type="application/pdf")
    assert fallback.calls == 0


async def test_llm_degrade_logs_class_without_message_or_traceback() -> None:
    primary = _StubParser(
        raises=LlmParserError("llm_output_invalid: validation failed on ['name']")
    )
    fallback = _StubParser(result=_resume("library.v1"))
    parser = FallbackResumeParser(primary=primary, fallback=fallback)
    with capture_logs() as logs:
        await parser.parse(content=b"x", content_type="application/pdf")
    (line,) = (e for e in logs if e["event"] == "parse.llm-failed")
    assert line["error_class"] == "LlmParserError"
    assert line["reason"] == "llm_output_invalid: validation failed on ['name']"
    assert "exc_info" not in line


async def test_unexpected_degrade_logs_class_only() -> None:
    primary = _StubParser(raises=RuntimeError("contains alice@example.com and resume text"))
    fallback = _StubParser(result=_resume("library.v1"))
    parser = FallbackResumeParser(primary=primary, fallback=fallback)
    with capture_logs() as logs:
        await parser.parse(content=b"x", content_type="application/pdf")
    (line,) = (e for e in logs if e["event"] == "parse.llm-failed")
    assert line["error_class"] == "RuntimeError"
    assert "reason" not in line and "exc_info" not in line
