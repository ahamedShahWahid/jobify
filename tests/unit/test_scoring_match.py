"""Unit tests for score_match composition + threshold logic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from jobify.scoring.match import score_match


def _kw(**overrides) -> dict:
    base = {
        "applicant_embedding": [1.0, 0.0, 0.0],
        "job_embedding": [1.0, 0.0, 0.0],
        "applicant_locations": ["Bangalore"],
        "applicant_years": Decimal("4"),
        "applicant_expected_ctc": Decimal("2000000"),
        "job_locations": ["Bangalore"],
        "job_min_exp_years": 3,
        "job_max_exp_years": 6,
        "job_ctc_min": Decimal("1500000"),
        "job_ctc_max": Decimal("2500000"),
        "vector_weight": 0.6,
        "threshold": 0.55,
    }
    base.update(overrides)
    return base


def test_score_match_components_recorded() -> None:
    result = score_match(**_kw())
    assert set(result.components.keys()) == {"location", "exp", "ctc"}
    assert result.components["location"] == 1.0


def test_total_is_weighted_sum() -> None:
    result = score_match(**_kw())
    expected = 0.6 * result.vector + 0.4 * result.structured
    assert result.total == pytest.approx(expected)


def test_crosses_threshold_at_boundary() -> None:
    # Construct inputs to make total exactly == threshold.
    # vector=1.0, structured=1.0, weight=0.6 → total=1.0; threshold=1.0 → crosses.
    result = score_match(**_kw(threshold=1.0))
    assert result.total == pytest.approx(1.0)
    assert result.crosses_threshold is True


def test_crosses_threshold_just_below() -> None:
    # Force structured to be lower so total < threshold.
    result = score_match(
        **_kw(
            applicant_locations=["Mumbai"],  # location_fit = 0.0
            threshold=0.95,
        )
    )
    assert result.crosses_threshold is False


def test_negative_cosine_clipped_to_zero() -> None:
    result = score_match(
        **_kw(
            applicant_embedding=[1.0, 0.0],
            job_embedding=[-1.0, 0.0],
        )
    )
    assert result.vector == 0.0


def test_vector_weight_zero_is_pure_structured() -> None:
    result = score_match(**_kw(vector_weight=0.0))
    assert result.total == pytest.approx(result.structured)
