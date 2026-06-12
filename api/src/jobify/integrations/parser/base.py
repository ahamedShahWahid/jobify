"""Parser contract — Protocol + canonical ParsedResume schema + error types.

Stored in `jobify.resumes.parsed_json` via :meth:`ParsedResume.model_dump`. Any
future parser (LLM, vendor service) MUST produce values that validate against
:class:`ParsedResume`. Bump :attr:`ParsedResume.schema_version` on any breaking
change and own a re-parse migration in the same plan.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ExperienceEntry(BaseModel):
    """One job/role entry. Free-form date strings — parsers don't normalize."""

    company: str | None = None
    title: str | None = None
    start: str | None = None  # "Jan 2020" / "2020" / "01/2020" — free-form
    end: str | None = None  # "Present" / "Dec 2022" / null
    summary: str | None = None


class EducationEntry(BaseModel):
    """One education entry."""

    institution: str | None = None
    degree: str | None = None  # "B.Tech", "M.Sc", "MBA"
    field: str | None = None  # "Computer Science"
    end_year: int | None = None


class CertificationEntry(BaseModel):
    """One certification entry."""

    name: str | None = None
    issuer: str | None = None
    year: int | None = None


class ParsedResume(BaseModel):
    """Canonical parsed-resume payload. Stored verbatim in resumes.parsed_json."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    parser_name: str  # provenance: "library.v1" / "llm.anthropic.v1" / ...
    raw_text: str  # full extracted text, truncated to 64 KB by the extractor

    name: str | None = None
    email: str | None = None
    phone: str | None = None

    skills: list[str] = []
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    certifications: list[CertificationEntry] = []


class ResumeParser(Protocol):
    """Async parser: content bytes + mime type in, :class:`ParsedResume` out.

    Raises :class:`ParserError` on permanent failures (corrupt input, unsupported
    type). Raises :class:`TransientParserError` on recoverable failures (transient
    library exceptions, storage hiccups) — the worker autoretries those.
    """

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume: ...


class ParserError(Exception):
    """Permanent failure — worker marks parse_status='failed' immediately, no retry.

    Message string is a stable slug (e.g. "doc_legacy_not_supported",
    "password_protected", "no_text_extracted", "unsupported_content_type") so it
    can be surfaced verbatim in parse_error without leaking PII.
    """


class TransientParserError(Exception):
    """Recoverable failure — worker autoretries up to 3 times with exponential backoff."""
