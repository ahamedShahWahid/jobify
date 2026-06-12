"""Canonicalize a parsed resume to a deterministic text representation.

Stable ordering and normalization is critical: the sha256 of the output is the
idempotency key on ``applicant_embeddings.canonicalized_text_hash``. A reordering
of skills or a different rendering of the same content must NOT change the hash.
"""

from __future__ import annotations

import hashlib

from jobify.integrations.parser.base import EducationEntry, ExperienceEntry, ParsedResume


def canonicalize_profile(parsed: ParsedResume, *, full_name: str) -> tuple[str, str]:
    """Return ``(canonicalized_text, sha256_hex_hash)``.

    Deterministic: same ``ParsedResume`` + ``full_name`` always yields the same
    text and hash. Skills are normalized to lowercase, deduped, and sorted.
    Free-form string fields are stripped. Missing optional fields are rendered
    as ``?``.
    """
    skills = sorted({s.strip().lower() for s in parsed.skills if s and s.strip()})

    experience_lines = sorted(_format_experience(r) for r in parsed.experience)
    education_lines = sorted(_format_education(e) for e in parsed.education)
    certification_names = sorted(
        {c.name.strip() for c in parsed.certifications if c.name and c.name.strip()}
    )

    lines = [
        full_name.strip(),
        "Skills: " + ", ".join(skills),
        "Experience:",
        *experience_lines,
        "Education:",
        *education_lines,
        "Certifications: " + ", ".join(certification_names),
    ]
    text = "\n".join(lines)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _format_experience(r: ExperienceEntry) -> str:
    title = (r.title or "?").strip()
    company = (r.company or "?").strip()
    start = (r.start or "?").strip()
    end = (r.end or "present").strip()
    summary = (r.summary or "").strip()
    head = f"- {title} @ {company} ({start}-{end})"
    return f"{head}: {summary}" if summary else head


def _format_education(e: EducationEntry) -> str:
    degree = (e.degree or "?").strip()
    field = (e.field or "").strip()
    institution = (e.institution or "?").strip()
    end_year = f" ({e.end_year})" if e.end_year else ""
    head = f"- {degree}" + (f" {field}" if field else "") + f", {institution}"
    return head + end_year
