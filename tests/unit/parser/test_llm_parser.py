"""GeminiResumeParser — faked genai client; no network."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from prometheus_client import REGISTRY

from jobify.integrations.parser import LlmParserError, ParserError
from jobify.integrations.parser import llm_parser as llm_parser_module
from jobify.integrations.parser.llm_parser import (
    LLM_PARSER_NAME,
    GeminiResumeParser,
    _raw_shape,
)


def _external_calls(service: str, operation: str, outcome: str) -> float:
    labels = {"service": service, "operation": operation, "outcome": outcome}
    return REGISTRY.get_sample_value("jobify_external_calls_total", labels) or 0.0


_GOOD_JSON = json.dumps(
    {
        "name": "Priya Sharma",
        "email": "priya@example.com",
        "phone": "+91 98765 43210",
        "skills": ["Python", "FastAPI"],
        "experience": [
            {
                "company": "Acme",
                "title": "Engineer",
                "start": "Jan 2020",
                "end": "Present",
                "summary": "Built things.",
            }
        ],
        "education": [
            {
                "institution": "IIT Delhi",
                "degree": "B.Tech",
                "field": "Computer Science",
                "end_year": 2019,
            }
        ],
        "certifications": [],
    }
)


def _client_returning(text: str | None) -> MagicMock:
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=SimpleNamespace(text=text))
    return client


def test_parse_text_happy_path() -> None:
    parser = GeminiResumeParser(client=_client_returning(_GOOD_JSON), model="gemini-2.5-flash")
    parsed = asyncio.run(parser.parse_text("PRIYA SHARMA\npriya@example.com ..."))
    assert parsed.parser_name == LLM_PARSER_NAME
    assert parsed.raw_text.startswith("PRIYA SHARMA")
    assert parsed.name == "Priya Sharma"
    assert parsed.skills == ["Python", "FastAPI"]
    assert parsed.experience[0].company == "Acme"
    assert parsed.education[0].end_year == 2019
    assert parsed.schema_version == 1


def test_empty_response_raises_llm_error() -> None:
    parser = GeminiResumeParser(client=_client_returning(None), model="m")
    with pytest.raises(LlmParserError):
        asyncio.run(parser.parse_text("text"))


def test_invalid_json_raises_llm_error() -> None:
    parser = GeminiResumeParser(client=_client_returning("not json {"), model="m")
    with pytest.raises(LlmParserError):
        asyncio.run(parser.parse_text("text"))


def test_invalid_model_response_logs_rejection_at_warning() -> None:
    """A rejected model response is an operational signal (bad model output,
    prompt drift), not routine diagnostic noise — it must be visible without
    debug-level logging turned up."""
    from structlog.testing import capture_logs

    parser = GeminiResumeParser(client=_client_returning("not json {"), model="m")

    with capture_logs() as logs:
        with pytest.raises(LlmParserError):
            asyncio.run(parser.parse_text("text"))

    (rejected,) = (e for e in logs if e.get("event") == "parse.llm-output-rejected")
    assert rejected["log_level"] == "warning"


def test_schema_invalid_payload_raises_llm_error() -> None:
    # end_year must be an int — a string that pydantic can't coerce fails validation.
    bad = json.dumps({"education": [{"end_year": "two thousand"}]})
    parser = GeminiResumeParser(client=_client_returning(bad), model="m")
    with pytest.raises(LlmParserError):
        asyncio.run(parser.parse_text("text"))


def test_schema_invalid_payload_error_message_scrubs_pii() -> None:
    """A ValidationError's str() embeds pydantic's input_value=... context —
    for ParsedResume that context is the model-echoed resume fields
    themselves. The raised LlmParserError (which fallback.py logs at WARNING)
    must name the failing field but never leak the offending value."""
    leaked_email = "leaked-pii@example.com"
    bad = json.dumps({"education": [{"end_year": leaked_email}]})
    parser = GeminiResumeParser(client=_client_returning(bad), model="m")
    with pytest.raises(LlmParserError) as exc_info:
        asyncio.run(parser.parse_text("text"))
    message = str(exc_info.value)
    assert leaked_email not in message
    assert "education" in message


def test_provider_exception_wrapped_as_llm_error() -> None:
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("503"))
    parser = GeminiResumeParser(client=client, model="m")
    before = _external_calls("gemini", "parse_resume", "error")
    with pytest.raises(LlmParserError):
        asyncio.run(parser.parse_text("text"))
    assert _external_calls("gemini", "parse_resume", "error") == before + 1


async def test_provider_api_error_message_keeps_http_status() -> None:
    from google.genai import errors

    api_error = errors.ClientError(
        429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}}
    )
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=api_error)
    parser = GeminiResumeParser(client=client, model="m")
    before = _external_calls("gemini", "parse_resume", "error")

    with pytest.raises(LlmParserError) as info:
        await parser.parse_text("resume text")

    assert str(info.value) == "llm_call_failed: ClientError 429 RESOURCE_EXHAUSTED"
    assert _external_calls("gemini", "parse_resume", "error") == before + 1


def test_parse_propagates_extraction_error_without_model_call() -> None:
    client = _client_returning(_GOOD_JSON)
    parser = GeminiResumeParser(client=client, model="m")
    # Empty PDF bytes -> extract_text raises a plain ParserError before any model call.
    with pytest.raises(ParserError) as exc_info:
        asyncio.run(parser.parse(content=b"", content_type="application/pdf"))
    assert not isinstance(exc_info.value, LlmParserError)
    client.aio.models.generate_content.assert_not_called()


def _flaky_parsed_resume_factory(*, raise_on_call: int) -> object:
    """Stand-in for ParsedResume that raises RuntimeError (an exception type
    outside _validated_resume's two specific arms) on the Nth invocation and
    otherwise delegates to the real constructor."""
    real_parsed_resume = llm_parser_module.ParsedResume
    call_count = 0

    def _fn(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count == raise_on_call:
            raise RuntimeError("unexpected boom — not Validation/Value/TypeError")
        return real_parsed_resume(*args, **kwargs)

    return _fn


def test_validated_resume_unexpected_exception_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exception outside the two specific arms (ValidationError,
    ValueError/TypeError) — e.g. an unforeseen bug constructing ParsedResume —
    must still be caught by _validated_resume's blanket arm and wrapped as
    LlmParserError, per the module's documented "ANY post-extraction failure
    raises LlmParserError" contract.

    The message must carry the type name ONLY. str(exc) on a pydantic error
    embeds `input_value=`, which for this model is the resume's own PII.
    """
    parser = GeminiResumeParser(client=MagicMock(), model="m")
    monkeypatch.setattr(
        llm_parser_module, "ParsedResume", _flaky_parsed_resume_factory(raise_on_call=1)
    )
    with pytest.raises(LlmParserError) as exc_info:
        parser._validated_resume(_GOOD_JSON, "text")
    assert str(exc_info.value) == "llm_output_invalid: RuntimeError"


# --- _raw_shape: PII-safe debug summary --------------------------------------


def test_raw_shape_never_echoes_response_content() -> None:
    """The whole point of the helper: no field of the returned dict may
    contain any substring of the model's response.

    _GOOD_JSON restates a resume (name, email, phone, employer). Asserting on
    the VALUES rather than on a key allowlist means a future field that leaks
    content fails this test without anyone remembering to update it.
    """
    shape = _raw_shape(_GOOD_JSON)
    rendered = " ".join(str(v) for v in shape.values())
    for secret in ("Priya", "priya@example.com", "98765", "Acme", "IIT Delhi"):
        assert secret not in rendered


def test_raw_shape_reports_schema_fields_but_only_counts_unknown_keys() -> None:
    """Known key NAMES are ours (from the response schema) and safe to log.

    An unrecognised key could itself be model-authored content, so those are
    counted and never named.
    """
    payload = json.dumps({"name": "Priya", "email": "p@e.com", "Priya Sharma": "leak"})
    shape = _raw_shape(payload)
    assert shape["raw_kind"] == "object"
    assert shape["known_keys"] == ["email", "name"]
    assert shape["unknown_key_count"] == 1
    assert "Priya Sharma" not in str(shape)


def test_raw_shape_locates_a_truncated_response() -> None:
    """The most common real failure: max_output_tokens cut the JSON short.

    Position + length are what make that diagnosable without the body.
    """
    shape = _raw_shape('{"name": "Priya", "skills": ["Pyth')
    assert shape["raw_kind"] == "invalid_json"
    assert shape["json_error_pos"] > 0
    assert shape["raw_len"] == 34


@pytest.mark.parametrize(
    ("raw", "expected_kind"),
    [(None, "empty"), ("", "empty"), ("[1, 2]", "list"), ('"a string"', "str")],
)
def test_raw_shape_handles_non_object_responses(raw: str | None, expected_kind: str) -> None:
    assert _raw_shape(raw)["raw_kind"] == expected_kind
