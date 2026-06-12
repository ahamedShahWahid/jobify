"""Unit tests for the templated match-explanation generator."""

from __future__ import annotations

from decimal import Decimal

from jobify.scoring.explain import templated_explanation


def _kw(**overrides) -> dict:
    base = {
        "components": {"location": 1.0, "exp": 1.0, "ctc": 1.0},
        "vector": 0.9,
        "structured": 1.0,
        "total": 0.94,
        "threshold": 0.55,
        "job_title": "Senior Backend Engineer",
        "job_locations": ["Bangalore"],
        "job_min_exp_years": 5,
        "job_max_exp_years": 9,
        "job_ctc_max": Decimal("4200000"),
        "employer_name": "Acme",
        "applicant_expected_ctc": Decimal("3000000"),
        "applicant_locations": ["Bangalore"],
    }
    base.update(overrides)
    return base


def test_strong_match_all_high() -> None:
    out = templated_explanation(**_kw())
    assert "Strong match" in out["fit"]
    assert "Senior Backend Engineer" in out["fit"]
    assert "Bangalore" in out["fit"]
    assert out["caveat"] == ""
    assert out["generator"] == "templated"
    assert out["generator_version"] == "1"


def test_good_loc_and_exp_weak_ctc() -> None:
    out = templated_explanation(
        **_kw(
            components={"location": 1.0, "exp": 1.0, "ctc": 0.4},
            applicant_expected_ctc=Decimal("5000000"),  # > job_ctc_max
            structured=0.8,
            total=0.88,
        )
    )
    assert "Good location and seniority fit" in out["fit"]
    assert out["caveat"] == "Compensation may be below your expectation."


def test_remote_match() -> None:
    out = templated_explanation(
        **_kw(
            components={"location": 1.0, "exp": 0.5, "ctc": 1.0},
            job_locations=["Remote"],
            applicant_locations=["Mumbai"],
            structured=0.83,
            total=0.87,
        )
    )
    assert "Remote-friendly match" in out["fit"]
    assert "Acme" in out["fit"]
    # exp=0.5 < 0.6 triggers experience caveat
    assert "Experience band" in out["caveat"]
    assert "5-9" in out["caveat"]


def test_below_threshold_message() -> None:
    out = templated_explanation(
        **_kw(
            components={"location": 1.0, "exp": 0.5, "ctc": 0.5},
            total=0.4,
        )
    )
    assert out["fit"] == "Lower-confidence match - surfaced for breadth."
    assert "Experience band" in out["caveat"]


def test_caveat_priority_exp_over_ctc() -> None:
    out = templated_explanation(
        **_kw(
            components={"location": 1.0, "exp": 0.4, "ctc": 0.3},
            applicant_expected_ctc=Decimal("5000000"),
            total=0.88,
        )
    )
    assert "Experience band" in out["caveat"]


def test_caveat_priority_ctc_over_location() -> None:
    out = templated_explanation(
        **_kw(
            components={"location": 0.0, "exp": 1.0, "ctc": 0.3},
            applicant_expected_ctc=Decimal("5000000"),
            applicant_locations=["Mumbai"],
            total=0.88,
        )
    )
    assert "Compensation" in out["caveat"]


def test_caveat_location_mismatch() -> None:
    out = templated_explanation(
        **_kw(
            components={"location": 0.0, "exp": 1.0, "ctc": 1.0},
            applicant_locations=["Mumbai"],
            total=0.83,
        )
    )
    assert "Location mismatch" in out["caveat"]


def test_no_caveat_when_all_above_threshold() -> None:
    out = templated_explanation(**_kw())
    assert out["caveat"] == ""


def test_overlap_location_preferred_for_display() -> None:
    out = templated_explanation(
        **_kw(
            job_locations=["Mumbai", "Bangalore"],
            applicant_locations=["Bangalore"],
        )
    )
    assert "Bangalore" in out["fit"]


def test_output_includes_generator_metadata() -> None:
    out = templated_explanation(**_kw())
    assert out["generator"] == "templated"
    assert out["generator_version"] == "1"
