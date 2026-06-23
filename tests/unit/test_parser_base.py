"""Unit tests for the parser contract layer — no I/O, no DB."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jobify.integrations.parser.base import (
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ParserError,
    TransientParserError,
)


def test_parsed_resume_defaults_are_safe() -> None:
    """A parser that can only extract raw_text must still produce a valid ParsedResume."""
    pr = ParsedResume(parser_name="library.v1", raw_text="hello world")
    assert pr.schema_version == 1
    assert pr.parser_name == "library.v1"
    assert pr.raw_text == "hello world"
    assert pr.name is None
    assert pr.email is None
    assert pr.phone is None
    assert pr.skills == []
    assert pr.experience == []
    assert pr.education == []
    assert pr.certifications == []


def test_parsed_resume_is_frozen() -> None:
    """Frozen so callers can't mutate after parse — easier to reason about caching later."""
    pr = ParsedResume(parser_name="library.v1", raw_text="x")
    with pytest.raises(ValidationError):  # pydantic ValidationError on frozen mutation
        pr.email = "x@y.com"  # type: ignore[misc]


def test_parsed_resume_round_trips_through_model_dump() -> None:
    """parsed_json is stored via model_dump(mode='json'); ensure round-trip is stable."""
    pr = ParsedResume(
        parser_name="library.v1",
        raw_text="hello",
        name="Ahamed Wahid",
        email="ahamed@example.com",
        phone="+91-9876543210",
        skills=["python", "fastapi"],
        experience=[
            ExperienceEntry(
                company=None, title=None, start="2020", end="Present", summary="some text"
            )
        ],
        education=[EducationEntry(institution=None, degree="B.Tech", field=None, end_year=2018)],
        certifications=[CertificationEntry(name="AWS SAA", issuer="Amazon", year=2022)],
    )
    dumped = pr.model_dump(mode="json")
    revived = ParsedResume.model_validate(dumped)
    assert revived == pr


def test_parser_error_carries_message() -> None:
    err = ParserError("doc_legacy_not_supported")
    assert str(err) == "doc_legacy_not_supported"


def test_transient_parser_error_is_distinct_class() -> None:
    """Worker autoretry list switches on TransientParserError; ensure it's not a ParserError."""
    err = TransientParserError("storage_timeout")
    assert isinstance(err, TransientParserError)
    assert not isinstance(err, ParserError)
