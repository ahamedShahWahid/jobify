"""Unit tests for the three structured rule fits + their aggregate."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kpa.scoring.structured import (
    ctc_fit,
    exp_fit,
    location_fit,
    structured_score,
)

# --- location_fit ---


@pytest.mark.parametrize(
    ("app_locs", "job_locs", "expected"),
    [
        (["Bangalore"], ["Bangalore", "Mumbai"], 1.0),
        (["bangalore"], ["Bangalore"], 1.0),
        (["Mumbai"], ["Remote"], 1.0),
        (["Remote"], ["Mumbai"], 1.0),
        (["Mumbai"], ["Bangalore"], 0.0),
        ([], [], 0.5),
        ([], ["Mumbai"], 0.5),
        (["Mumbai"], [], 0.5),
    ],
)
def test_location_fit(app_locs: list[str], job_locs: list[str], expected: float) -> None:
    assert location_fit(app_locs, job_locs) == expected


# --- exp_fit ---


@pytest.mark.parametrize(
    ("years", "job_min", "job_max", "expected"),
    [
        (Decimal("5"), 3, 6, 1.0),  # in band
        (Decimal("3"), 3, 6, 1.0),  # min boundary
        (Decimal("6"), 3, 6, 1.0),  # max boundary
        (Decimal("9"), 3, 6, 0.5),  # over: 1 - (9-6)/6 = 0.5
        (Decimal("12"), 3, 6, 0.0),  # 2x over
        (Decimal("1.5"), 3, 6, 0.5),  # under: 1.5/3 = 0.5
        (Decimal("0"), 3, 6, 0.0),  # zero under
        (Decimal("4"), 0, 2, 0.0),  # past 2x over (job_max=2)
        (None, 3, 6, 0.5),  # unknown applicant years
    ],
)
def test_exp_fit(years: Decimal | None, job_min: int, job_max: int, expected: float) -> None:
    assert exp_fit(years, job_min, job_max) == expected


# --- ctc_fit ---


@pytest.mark.parametrize(
    ("expected_ctc", "job_min", "job_max", "expected"),
    [
        (Decimal("2000000"), Decimal("1500000"), Decimal("2500000"), 1.0),  # in band
        # under: applicant happy with less
        (Decimal("1000000"), Decimal("1500000"), Decimal("2500000"), 1.0),
        # over: 1 - (3M-2.5M)/(0.5*2.5M) = 0.6
        (Decimal("3000000"), Decimal("1500000"), Decimal("2500000"), 0.6),
        (Decimal("5000000"), Decimal("1500000"), Decimal("2500000"), 0.0),  # past 1.5x
        (None, Decimal("1500000"), Decimal("2500000"), 0.5),  # unknown applicant CTC
        (Decimal("2000000"), None, None, 0.5),  # no job CTC bounds
        (Decimal("2000000"), None, Decimal("2500000"), 1.0),  # only max set, in range
    ],
)
def test_ctc_fit(
    expected_ctc: Decimal | None,
    job_min: Decimal | None,
    job_max: Decimal | None,
    expected: float,
) -> None:
    assert ctc_fit(expected_ctc, job_min, job_max) == expected


# --- structured_score ---


def test_structured_score_aggregates_unweighted_mean() -> None:
    score, components = structured_score(
        applicant_locations=["Bangalore"],
        applicant_years=Decimal("4"),
        applicant_expected_ctc=Decimal("2000000"),
        job_locations=["Bangalore"],
        job_min_exp_years=3,
        job_max_exp_years=6,
        job_ctc_min=Decimal("1500000"),
        job_ctc_max=Decimal("2500000"),
    )
    assert components == {"location": 1.0, "exp": 1.0, "ctc": 1.0}
    assert score == 1.0


def test_structured_score_partial_signal() -> None:
    score, components = structured_score(
        applicant_locations=["Mumbai"],
        applicant_years=Decimal("4"),
        applicant_expected_ctc=Decimal("2000000"),
        job_locations=["Bangalore"],
        job_min_exp_years=3,
        job_max_exp_years=6,
        job_ctc_min=Decimal("1500000"),
        job_ctc_max=Decimal("2500000"),
    )
    assert components["location"] == 0.0
    assert components["exp"] == 1.0
    assert components["ctc"] == 1.0
    assert score == pytest.approx((0.0 + 1.0 + 1.0) / 3)
