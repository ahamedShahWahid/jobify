"""Validation tests for the seed_jobs CLI — no DB."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jobify.scripts.seed_jobs import SeedPayload, normalize_name


def _minimal_payload(**overrides) -> dict:
    base = {
        "version": 1,
        "employers": [{"name": "Acme", "gst": None, "verified": False}],
        "jobs": [
            {
                "employer_name": "Acme",
                "title": "Engineer",
                "description": "Build things.",
                "locations": [],
                "min_exp_years": 0,
                "max_exp_years": 2,
                "ctc_min": None,
                "ctc_max": None,
                "status": "open",
                "posted_days_ago": 0,
            }
        ],
    }
    base.update(overrides)
    return base


def test_valid_minimal_json_parses() -> None:
    payload = SeedPayload.model_validate(_minimal_payload())
    assert payload.version == 1
    assert payload.employers[0].name == "Acme"
    assert payload.jobs[0].title == "Engineer"


def test_unknown_version_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        SeedPayload.model_validate(_minimal_payload(version=2))
    assert "unsupported version" in str(exc.value)


def test_job_references_unknown_employer() -> None:
    bad = _minimal_payload()
    bad["jobs"][0]["employer_name"] = "Nope"
    with pytest.raises(ValidationError) as exc:
        SeedPayload.model_validate(bad)
    assert "unknown employer" in str(exc.value)


def test_max_exp_less_than_min_exp() -> None:
    bad = _minimal_payload()
    bad["jobs"][0]["min_exp_years"] = 5
    bad["jobs"][0]["max_exp_years"] = 3
    with pytest.raises(ValidationError) as exc:
        SeedPayload.model_validate(bad)
    assert "max_exp_years" in str(exc.value)


def test_ctc_max_less_than_ctc_min() -> None:
    bad = _minimal_payload()
    bad["jobs"][0]["ctc_min"] = 1_500_000
    bad["jobs"][0]["ctc_max"] = 800_000
    with pytest.raises(ValidationError) as exc:
        SeedPayload.model_validate(bad)
    assert "ctc_max" in str(exc.value)


def test_name_norm_collapses_whitespace_and_lowercases() -> None:
    assert normalize_name("  Acme   Corp ") == "acme corp"
    assert normalize_name("ACME") == "acme"
    assert normalize_name("foo\t  bar") == "foo bar"


def test_locations_empty_array_allowed() -> None:
    payload = SeedPayload.model_validate(_minimal_payload())
    assert payload.jobs[0].locations == []


def test_status_defaults_to_open() -> None:
    base = _minimal_payload()
    del base["jobs"][0]["status"]
    payload = SeedPayload.model_validate(base)
    assert payload.jobs[0].status == "open"


def test_posted_days_ago_rejects_negative() -> None:
    bad = _minimal_payload()
    bad["jobs"][0]["posted_days_ago"] = -1
    with pytest.raises(ValidationError):
        SeedPayload.model_validate(bad)
