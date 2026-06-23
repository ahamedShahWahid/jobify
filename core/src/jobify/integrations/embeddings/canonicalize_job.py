"""Canonicalize a Job + Employer name to a deterministic text representation.

Stable ordering and normalization is critical: the sha256 of the output is the
idempotency key on ``job_embeddings.canonicalized_text_hash``. Reordering
locations or copy-pasting a description with different line endings must NOT
change the hash.

Distinct from ``canonicalize.py`` (the applicant-side canonicalizer): different
input shape, different fields, no shared internals. The two canonicalizers are
intentionally siblings, not subclasses of a shared abstraction — the
similarity is shallow and the boundaries would be wrong.
"""

from __future__ import annotations

import hashlib
from typing import Protocol


class _JobLike(Protocol):
    """Structural type for canonicalize_job — accepts an ORM Job or any
    duck-typed object with these attrs (used in unit tests)."""

    title: str
    description: str
    locations: list[str]
    min_exp_years: int
    max_exp_years: int


def canonicalize_job(job: _JobLike, *, employer_name: str) -> tuple[str, str]:
    """Return ``(canonicalized_text, sha256_hex_hash)``.

    Determinism guarantees:
    - Locations are sorted case-insensitively (case preserved in output).
    - Description line endings normalized (CRLF / CR → LF).
    - Free-form strings (title, employer) are stripped of leading/trailing whitespace.
    - Empty locations omits the ``Locations:`` line entirely.
    - When ``min_exp_years == max_exp_years``, format is ``N years`` (no range).
    """
    title = job.title.strip()
    emp = employer_name.strip()
    desc = job.description.strip().replace("\r\n", "\n").replace("\r", "\n")
    locs = sorted(
        (loc.strip() for loc in (job.locations or []) if loc.strip()),
        key=str.lower,
    )
    if job.min_exp_years == job.max_exp_years:
        exp = f"{job.min_exp_years} years"
    else:
        exp = f"{job.min_exp_years}-{job.max_exp_years} years"

    lines = [f"title: {title} at {emp} | text: {desc}"]
    if locs:
        lines.append(f"Locations: {', '.join(locs)}")
    lines.append(f"Experience: {exp}")

    text = "\n".join(lines)
    hash_hex = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, hash_hex
