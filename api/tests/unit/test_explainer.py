"""Unit tests for the ExplainContext + TemplatedExplainer."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from kpa.scoring.explain import templated_explanation
from kpa.scoring.explainer import ExplainContext, TemplatedExplainer


def _ctx(**overrides: object) -> ExplainContext:
    base: dict[str, object] = {
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
    return ExplainContext(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_templated_explainer_matches_pure_function() -> None:
    """TemplatedExplainer.explain(ctx) must return exactly what
    templated_explanation(**fields) returns for the same fields."""
    ctx = _ctx()
    expected = templated_explanation(
        components=ctx.components,
        vector=ctx.vector,
        structured=ctx.structured,
        total=ctx.total,
        threshold=ctx.threshold,
        job_title=ctx.job_title,
        job_locations=ctx.job_locations,
        job_min_exp_years=ctx.job_min_exp_years,
        job_max_exp_years=ctx.job_max_exp_years,
        job_ctc_max=ctx.job_ctc_max,
        employer_name=ctx.employer_name,
        applicant_expected_ctc=ctx.applicant_expected_ctc,
        applicant_locations=ctx.applicant_locations,
    )
    out = await TemplatedExplainer().explain(ctx)
    assert out == expected
    assert out["generator"] == "templated"
    assert out["generator_version"] == "1"


def test_explain_context_is_frozen() -> None:
    """ExplainContext is a frozen dataclass — mutation must raise."""
    ctx = _ctx()
    with pytest.raises(FrozenInstanceError):
        ctx.total = 0.1  # type: ignore[misc]
