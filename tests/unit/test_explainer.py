"""Unit tests for the ExplainContext + TemplatedExplainer."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from jobify.scoring.explain import templated_explanation
from jobify.scoring.explainer import (
    ExplainContext,
    TemplatedExplainer,
    _templated_from_ctx,
    explanation_cache_key,
)


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


def test_templated_explanation_hindi() -> None:
    ctx = _ctx(language="hi")  # the file's existing builder, with the new field
    result = _templated_from_ctx(ctx)
    assert result["generator"] == "templated"
    # Hindi fit text is Devanagari — assert script, not exact copy.
    assert any("ऀ" <= ch <= "ॿ" for ch in result["fit"])


def test_templated_explanation_hindi_caveat() -> None:
    """Caveat path is separate from fit — exercise it too (weak exp -> exp caveat)."""
    ctx = _ctx(
        language="hi",
        components={"location": 1.0, "exp": 0.4, "ctc": 1.0},
    )
    result = _templated_from_ctx(ctx)
    assert any("ऀ" <= ch <= "ॿ" for ch in result["caveat"])
    # {}-slots must survive .format() in the Hindi string.
    assert "5-9" in result["caveat"]


def test_templated_explanation_default_language_unchanged() -> None:
    ctx = _ctx()  # no language arg -> "en" default
    result = _templated_from_ctx(ctx)
    assert not any("ऀ" <= ch <= "ॿ" for ch in result["fit"])


# --- explanation_cache_key (PERF-01) ---------------------------------------


def test_cache_key_is_deterministic() -> None:
    ctx = _ctx()
    assert explanation_cache_key(ctx, generator_version="2") == explanation_cache_key(
        ctx, generator_version="2"
    )


def test_cache_key_changes_with_generator_version() -> None:
    """A deliberate prompt/template bump must invalidate every cached row —
    it's the whole mechanism, not a config knob to work around."""
    ctx = _ctx()
    assert explanation_cache_key(ctx, generator_version="2") != explanation_cache_key(
        ctx, generator_version="3"
    )


def test_cache_key_changes_with_language() -> None:
    en = explanation_cache_key(_ctx(language="en"), generator_version="2")
    hi = explanation_cache_key(_ctx(language="hi"), generator_version="2")
    assert en != hi


@pytest.mark.parametrize(
    "override",
    [
        {"job_title": "Staff Backend Engineer"},
        {"job_locations": ["Mumbai"]},
        {"job_min_exp_years": 3},
        {"job_max_exp_years": 12},
        {"job_ctc_max": Decimal("5000000")},
        {"employer_name": "Different Co"},
        {"applicant_expected_ctc": Decimal("3500000")},
        {"applicant_locations": ["Pune"]},
    ],
)
def test_cache_key_changes_when_a_prompt_input_changes(override: dict[str, object]) -> None:
    base_key = explanation_cache_key(_ctx(), generator_version="2")
    changed_key = explanation_cache_key(_ctx(**override), generator_version="2")
    assert base_key != changed_key


def test_cache_key_ignores_raw_scores_not_in_the_prompt() -> None:
    """vector/structured/total never reach the LLM prompt (only the three
    rounded components do) — a description-only job edit that moves the
    vector score must not change the key, or the whole point of the cache
    (skip re-explaining a batch a description edit re-triggers) is lost."""
    base_key = explanation_cache_key(_ctx(), generator_version="2")
    moved_score_key = explanation_cache_key(
        _ctx(vector=0.2, structured=0.5, total=0.5), generator_version="2"
    )
    assert base_key == moved_score_key


def test_cache_key_rounds_components_to_the_same_precision_as_the_prompt() -> None:
    """The prompt formats components as f'{value:.2f}' — two component
    values that round to the same two decimals must produce the same key,
    since the actual LLM input text would be byte-identical."""
    a = explanation_cache_key(
        _ctx(components={"location": 0.601, "exp": 1.0, "ctc": 1.0}), generator_version="2"
    )
    b = explanation_cache_key(
        _ctx(components={"location": 0.604, "exp": 1.0, "ctc": 1.0}), generator_version="2"
    )
    assert a == b


def test_cache_key_changes_when_rounded_component_differs() -> None:
    a = explanation_cache_key(
        _ctx(components={"location": 0.60, "exp": 1.0, "ctc": 1.0}), generator_version="2"
    )
    b = explanation_cache_key(
        _ctx(components={"location": 0.70, "exp": 1.0, "ctc": 1.0}), generator_version="2"
    )
    assert a != b


def test_cache_key_handles_none_ctc_values() -> None:
    """job_ctc_max / applicant_expected_ctc are both optional — must not raise."""
    key = explanation_cache_key(
        _ctx(job_ctc_max=None, applicant_expected_ctc=None), generator_version="2"
    )
    assert isinstance(key, str) and len(key) == 64  # sha256 hex digest


def test_templated_explainer_carries_the_templated_generator_version() -> None:
    """The whole cache-skip-on-fallback safety property
    (_scoring_common.explain_scores) depends on a templated fallback's
    generator_version being a fixed, LLM-distinct tag — never derived from
    whatever explainer happened to be configured."""
    assert TemplatedExplainer.generator_version == "1"
