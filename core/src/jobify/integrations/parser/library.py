"""LibraryResumeParser — regex + keyword extraction, no external services.

Best-effort across the full §6.1 schema. Empty arrays where regex can't find
anything. The LLM impl that lands later replaces this with higher-fidelity
extraction behind the same Protocol.
"""

from __future__ import annotations

import re
from typing import Final

from jobify.integrations.parser.base import (
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ParserError,
)
from jobify.integrations.parser.skills_dict import SKILLS
from jobify.integrations.parser.text import extract_text

PARSER_NAME: Final[str] = "library.v1"

# --- Regex patterns ---

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Indian + international phone. Tolerates spaces, dashes, parentheses.
# Requires at least 10 digits in a row (ignoring separators).
_PHONE_RE = re.compile(
    r"""
    (?:                                     # one of:
        \+\d{1,3}[\s\-]?                    #   country code with separator
      | \(\+?\d{1,3}\)[\s\-]?               #   country code in parens
      | (?<![\d])                           #   or no country code (boundary on digit)
    )
    (?:\d[\s\-]?){9,14}\d                   # 10-15 total digits with optional separators
    """,
    re.VERBOSE,
)

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
_YEAR = r"\d{4}"
_DATE = rf"(?:(?:{_MONTH})\s+)?{_YEAR}"
_SEP = "(?:-|\u2013|to|until)"  # hyphen, en-dash (U+2013), or word separators

# "Jan 2020 - Dec 2022" / "2018 to 2020" / "Mar 2021 - Present"
_EXPERIENCE_RANGE_RE = re.compile(
    rf"({_DATE})\s*{_SEP}\s*({_DATE}|Present|present|Current|current)",
)

_DEGREE_RE = re.compile(
    r"\b(B\.?\s*Tech|B\.?\s*E|B\.?\s*Sc|B\.?\s*A|"
    r"M\.?\s*Tech|M\.?\s*Sc|M\.?\s*B\.?\s*A|MBA|PhD|Ph\.D)\b",
    re.IGNORECASE,
)
_YEAR_NEARBY_RE = re.compile(r"\b(19|20)\d{2}\b")

_CERT_LINE_RE = re.compile(r"(certif(?:ied|ication)[^\n]*)", re.IGNORECASE)


class LibraryResumeParser:
    """Regex/keyword-based parser. parser_name='library.v1'."""

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        try:
            raw_text = await extract_text(content=content, content_type=content_type)
        except ParserError as exc:
            # "no_text_extracted" (whitespace-only / image-only) — return a valid
            # ParsedResume with empty fields rather than propagating; the caller
            # can decide whether to surface this as a permanent failure.
            if str(exc) == "no_text_extracted":
                return ParsedResume(
                    parser_name=PARSER_NAME,
                    raw_text="",
                )
            raise

        return ParsedResume(
            parser_name=PARSER_NAME,
            raw_text=raw_text,
            name=_extract_name(raw_text),
            email=_extract_email(raw_text),
            phone=_extract_phone(raw_text),
            skills=_extract_skills(raw_text),
            experience=_extract_experience(raw_text),
            education=_extract_education(raw_text),
            certifications=_extract_certifications(raw_text),
        )


# --- Field extractors ---


def _extract_name(text: str) -> str | None:
    """Heuristic: first non-empty line with ≤5 capitalised words and no digits/@/colons."""
    for line in text.splitlines():
        stripped = line.strip()
        if (
            not stripped
            or "@" in stripped
            or ":" in stripped
            or any(ch.isdigit() for ch in stripped)
        ):
            continue
        tokens = stripped.split()
        if 1 <= len(tokens) <= 5 and all(t[0].isupper() for t in tokens if t.isalpha()):
            return stripped
    return None


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return m.group(0).strip() if m else None


def _extract_skills(text: str) -> list[str]:
    """Case-insensitive containment against the curated SKILLS dictionary."""
    lower = text.lower()
    found = {skill for skill in SKILLS if skill in lower}
    return sorted(found)


def _extract_experience(text: str) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    for match in _EXPERIENCE_RANGE_RE.finditer(text):
        start, end = match.group(1), match.group(2)
        # Grab ±50 chars of surrounding context for `summary`.
        ctx_start = max(0, match.start() - 50)
        ctx_end = min(len(text), match.end() + 50)
        summary = text[ctx_start:ctx_end].strip().replace("\n", " ")
        entries.append(
            ExperienceEntry(company=None, title=None, start=start, end=end, summary=summary)
        )
    return entries


def _extract_education(text: str) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    for match in _DEGREE_RE.finditer(text):
        degree = match.group(1)
        # Find a year within 60 chars after the degree.
        tail = text[match.end() : match.end() + 60]
        year_match = _YEAR_NEARBY_RE.search(tail)
        end_year = int(year_match.group(0)) if year_match else None
        entries.append(
            EducationEntry(institution=None, degree=degree, field=None, end_year=end_year)
        )
    return entries


def _extract_certifications(text: str) -> list[CertificationEntry]:
    entries: list[CertificationEntry] = []
    for match in _CERT_LINE_RE.finditer(text):
        line = match.group(1)
        year_match = _YEAR_NEARBY_RE.search(line)
        year = int(year_match.group(0)) if year_match else None
        entries.append(CertificationEntry(name=line.strip(), issuer=None, year=year))
    return entries
