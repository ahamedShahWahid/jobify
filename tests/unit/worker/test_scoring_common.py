"""Unit tests for explain_scores' explanation cache (PERF-01).

Pure — no DB, no genai. score_match's inputs are chosen so the pair is
comfortably surfaced (total well above threshold) without depending on the
exact scoring formula's magnitude.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from jobify.scoring.explainer import ExplainContext
from jobify_worker.tasks._scoring_common import ScoringInput, explain_scores

pytestmark = pytest.mark.asyncio

_THRESHOLD = 0.3  # low enough that the identical-embedding pair below surfaces
_VECTOR_WEIGHT = 0.6


@dataclass
class _FakeExplainer:
    """Records every call; returns a marker dict tagged with its own version."""

    generator_version: str = "llm-v2"
    calls: list[ExplainContext] = field(default_factory=list)
    fit: str = "fake fit"

    async def explain(self, ctx: ExplainContext) -> dict[str, str]:
        self.calls.append(ctx)
        return {
            "fit": self.fit,
            "caveat": "",
            "generator": "llm",
            "generator_version": self.generator_version,
        }


def _input(**overrides: object) -> ScoringInput:
    base: dict[str, object] = {
        "applicant_id": uuid.uuid4(),
        "job_id": uuid.uuid4(),
        "applicant_embedding": [1.0, 0.0],
        "applicant_embedding_model": "test-model",
        "applicant_locations": ["Bangalore"],
        "applicant_years": 5,
        "applicant_expected_ctc": 3_000_000,
        "job_embedding": [1.0, 0.0],
        "job_embedding_model": "test-model",
        "job_title": "Senior Backend Engineer",
        "job_locations": ["Bangalore"],
        "job_min_exp_years": 3,
        "job_max_exp_years": 8,
        "job_ctc_min": 2_000_000,
        "job_ctc_max": 4_000_000,
        "employer_name": "Acme",
        "language": "en",
    }
    base.update(overrides)
    return ScoringInput(**base)  # type: ignore[arg-type]


async def test_first_run_calls_the_explainer_and_stores_a_key() -> None:
    explainer = _FakeExplainer()
    inp = _input()

    [scored] = await explain_scores(
        explainer, [inp], vector_weight=_VECTOR_WEIGHT, threshold=_THRESHOLD
    )

    assert len(explainer.calls) == 1
    assert scored.explanation["fit"] == "fake fit"
    assert scored.explanation_key is not None


async def test_identical_rerun_hits_the_cache_and_skips_the_explainer() -> None:
    explainer = _FakeExplainer()
    inp = _input()

    [first] = await explain_scores(
        explainer, [inp], vector_weight=_VECTOR_WEIGHT, threshold=_THRESHOLD
    )
    existing = {(inp.applicant_id, inp.job_id): (first.explanation_key, first.explanation)}

    [second] = await explain_scores(
        explainer,
        [inp],
        vector_weight=_VECTOR_WEIGHT,
        threshold=_THRESHOLD,
        existing_explanations=existing,
    )

    assert len(explainer.calls) == 1  # still one — the rerun never called explain()
    assert second.explanation == first.explanation
    assert second.explanation_key == first.explanation_key


async def test_a_changed_job_title_misses_the_cache_and_calls_again() -> None:
    """A job title edit is exactly the kind of real content change the
    explanation should regenerate for — the cache must not paper over it."""
    explainer = _FakeExplainer()
    inp = _input()

    [first] = await explain_scores(
        explainer, [inp], vector_weight=_VECTOR_WEIGHT, threshold=_THRESHOLD
    )
    existing = {(inp.applicant_id, inp.job_id): (first.explanation_key, first.explanation)}

    changed = _input(
        applicant_id=inp.applicant_id, job_id=inp.job_id, job_title="Staff Backend Engineer"
    )
    [second] = await explain_scores(
        explainer,
        [changed],
        vector_weight=_VECTOR_WEIGHT,
        threshold=_THRESHOLD,
        existing_explanations=existing,
    )

    assert len(explainer.calls) == 2


async def test_llm_failure_fallback_is_never_cached() -> None:
    """A templated fallback (generator_version != the LLM's) must not be
    served as if it were a valid cached LLM answer — the next rescore must
    retry the LLM, not lock in the degraded text."""

    @dataclass
    class _DegradedExplainer:
        generator_version: str = "llm-v2"

        async def explain(self, ctx: ExplainContext) -> dict[str, str]:
            # Simulates GeminiMatchExplainer's own fallback: reports the
            # TEMPLATED generator_version, not its own.
            return {
                "fit": "templated fallback",
                "caveat": "",
                "generator": "templated",
                "generator_version": "1",
            }

    explainer = _DegradedExplainer()
    inp = _input()

    [scored] = await explain_scores(
        explainer, [inp], vector_weight=_VECTOR_WEIGHT, threshold=_THRESHOLD
    )

    assert scored.explanation_key is None


async def test_below_threshold_pair_never_stores_a_key() -> None:
    """explain_scores only computes a candidate cache key when ctx.total >=
    threshold — a below-threshold pair stores no key even if the configured
    explainer's response happens to look LLM-tagged (the real
    GeminiMatchExplainer itself never calls the LLM below threshold; this
    pins the caller-side half of that contract independently of the
    explainer implementation)."""
    explainer = _FakeExplainer()
    inp = _input(job_min_exp_years=50, job_max_exp_years=60)  # applicant_years=5, way outside band

    [scored] = await explain_scores(explainer, [inp], vector_weight=_VECTOR_WEIGHT, threshold=0.99)

    assert len(explainer.calls) == 1  # explain_scores calls explain() unconditionally
    assert scored.explanation_key is None


async def test_no_prior_row_is_a_cache_miss_not_an_error() -> None:
    explainer = _FakeExplainer()
    inp = _input()

    [scored] = await explain_scores(
        explainer,
        [inp],
        vector_weight=_VECTOR_WEIGHT,
        threshold=_THRESHOLD,
        existing_explanations={},
    )

    assert len(explainer.calls) == 1
    assert scored.explanation_key is not None
