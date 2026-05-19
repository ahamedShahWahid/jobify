"""Unit tests for canonicalize_profile — determinism, normalization, edge cases.

No I/O, no DB, no network.
"""

from __future__ import annotations

from kpa.integrations.embeddings.canonicalize import canonicalize_profile
from kpa.integrations.parser.base import (
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
)


def _make_resume(**kwargs) -> ParsedResume:
    """Build a ParsedResume with test defaults for required fields."""
    defaults: dict = {"parser_name": "test", "raw_text": ""}
    defaults.update(kwargs)
    return ParsedResume(**defaults)


def test_same_parsed_resume_yields_identical_text_and_hash() -> None:
    """Calling canonicalize_profile twice with the same input must produce the same output."""
    pr = _make_resume(
        name="Alice Smith",
        skills=["Python", "FastAPI"],
        experience=[
            ExperienceEntry(
                company="Acme", title="Eng", start="2020", end="Present", summary="Built stuff"
            )
        ],
        education=[EducationEntry(institution="MIT", degree="B.Tech", field="CS", end_year=2019)],
        certifications=[CertificationEntry(name="AWS SAA", issuer="Amazon", year=2022)],
    )
    text1, hash1 = canonicalize_profile(pr, full_name="Alice Smith")
    text2, hash2 = canonicalize_profile(pr, full_name="Alice Smith")

    assert text1 == text2
    assert hash1 == hash2


def test_skill_reordering_does_not_change_hash() -> None:
    """Skills in different orders must produce the same canonical text and hash."""
    pr1 = _make_resume(skills=["Python", "FastAPI"])
    pr2 = _make_resume(skills=["FastAPI", "Python"])

    _, hash1 = canonicalize_profile(pr1, full_name="Bob")
    _, hash2 = canonicalize_profile(pr2, full_name="Bob")

    assert hash1 == hash2


def test_skill_case_normalized_and_deduped() -> None:
    """Skills in different cases collapse to one entry in canonical text."""
    pr = _make_resume(skills=["Python", "python", "PYTHON"])

    text, _ = canonicalize_profile(pr, full_name="Carol")

    # After normalization and dedup, only 'python' appears (once).
    assert text.count("python") == 1
    # Verify it doesn't appear in any other casing.
    assert "Python" not in text.split("Skills: ", 1)[1].split("\n")[0]


def test_missing_optional_fields_handled() -> None:
    """A ParsedResume with all empty collections must not raise and must produce stable output."""
    pr = _make_resume()

    text, sha = canonicalize_profile(pr, full_name="Empty User")

    assert isinstance(text, str)
    assert len(text) > 0
    assert len(sha) == 64  # sha256 hex digest is always 64 chars


def test_experience_reordering_does_not_change_hash() -> None:
    """Two experience entries in different input orders produce the same hash.

    Same invariant as test_skill_reordering_does_not_change_hash, applied to
    the experience list. Protects against a future regression where someone
    adds an entry and breaks the sort-after-format invariant.
    """
    entry_a = ExperienceEntry(
        company="Acme", title="Engineer", start="2018", end="2020", summary="Built things"
    )
    entry_b = ExperienceEntry(
        company="Globex", title="Senior Engineer", start="2020", end="Present", summary="Led team"
    )

    pr1 = _make_resume(experience=[entry_a, entry_b])
    pr2 = _make_resume(experience=[entry_b, entry_a])

    _, hash1 = canonicalize_profile(pr1, full_name="Eve")
    _, hash2 = canonicalize_profile(pr2, full_name="Eve")

    assert hash1 == hash2


def test_certification_objects_use_name_field() -> None:
    """Certs with name=None are filtered out; non-empty name ends up in canonical text."""
    pr = _make_resume(
        certifications=[
            CertificationEntry(name=None, issuer="Foo", year=2020),
            CertificationEntry(name="", issuer="Bar", year=2021),
            CertificationEntry(name="AWS SAA", issuer="Amazon", year=2022),
        ]
    )

    text, _ = canonicalize_profile(pr, full_name="Dana")

    # Only "AWS SAA" has a non-empty name.
    assert "AWS SAA" in text
    # No blank cert names should sneak into the text.
    certifications_line = next(
        line for line in text.splitlines() if line.startswith("Certifications:")
    )
    assert certifications_line == "Certifications: AWS SAA"
