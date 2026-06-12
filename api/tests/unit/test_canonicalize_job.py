"""Determinism + format tests for canonicalize_job — pure function, no DB."""

from __future__ import annotations

from dataclasses import dataclass

from jobify.integrations.embeddings.canonicalize_job import canonicalize_job


@dataclass
class _JobLike:
    """Stand-in for a Job ORM instance — canonicalize_job only reads attrs."""

    title: str
    description: str
    locations: list[str]
    min_exp_years: int
    max_exp_years: int


def _job(**overrides) -> _JobLike:
    base = {
        "title": "Backend Engineer",
        "description": "Build APIs.",
        "locations": ["Bangalore", "Remote"],
        "min_exp_years": 3,
        "max_exp_years": 6,
    }
    base.update(overrides)
    return _JobLike(**base)


def test_canonical_format_basic() -> None:
    text, hash_hex = canonicalize_job(_job(), employer_name="Acme Co")
    assert text == (
        "title: Backend Engineer at Acme Co | text: Build APIs.\n"
        "Locations: Bangalore, Remote\n"
        "Experience: 3-6 years"
    )
    assert len(hash_hex) == 64
    assert all(c in "0123456789abcdef" for c in hash_hex)


def test_hash_is_deterministic_across_calls() -> None:
    a = canonicalize_job(_job(), employer_name="Acme Co")
    b = canonicalize_job(_job(), employer_name="Acme Co")
    assert a == b


def test_locations_order_does_not_affect_hash() -> None:
    a = canonicalize_job(_job(locations=["Remote", "bangalore"]), employer_name="Acme")
    b = canonicalize_job(_job(locations=["bangalore", "Remote"]), employer_name="Acme")
    assert a[1] == b[1]


def test_locations_case_insensitive_sort() -> None:
    text, _ = canonicalize_job(
        _job(locations=["Remote", "bangalore", "Mumbai"]),
        employer_name="Acme",
    )
    assert "Locations: bangalore, Mumbai, Remote" in text


def test_empty_locations_omits_line() -> None:
    text, _ = canonicalize_job(_job(locations=[]), employer_name="Acme")
    assert "Locations:" not in text
    hash_empty = canonicalize_job(_job(locations=[]), employer_name="Acme")[1]
    hash_with = canonicalize_job(_job(locations=["Mumbai"]), employer_name="Acme")[1]
    assert hash_empty != hash_with


def test_min_eq_max_uses_single_number() -> None:
    text, _ = canonicalize_job(_job(min_exp_years=5, max_exp_years=5), employer_name="Acme")
    assert "Experience: 5 years" in text
    assert "5-5" not in text


def test_description_crlf_normalized() -> None:
    crlf = canonicalize_job(
        _job(description="line one\r\nline two"),
        employer_name="Acme",
    )
    lf = canonicalize_job(
        _job(description="line one\nline two"),
        employer_name="Acme",
    )
    assert crlf[1] == lf[1]


def test_employer_change_changes_hash() -> None:
    a = canonicalize_job(_job(), employer_name="Acme")
    b = canonicalize_job(_job(), employer_name="Beta")
    assert a[1] != b[1]


def test_title_case_preserved_in_output_but_strip_applied() -> None:
    text, _ = canonicalize_job(_job(title="  Senior Engineer  "), employer_name="Acme")
    assert "title: Senior Engineer at Acme" in text
    assert "Senior Engineer  " not in text
