"""Match-explanation Protocol + frozen context + templated impl.

Wraps the pure-function ``templated_explanation`` from ``jobify.scoring.explain`` in
an async Protocol so the score workers can route between templated and LLM impls
behind a single call site. The LLM impl lives in ``jobify.scoring.llm_explainer``
so importing this module does not pull in ``google.genai``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from jobify.scoring.explain import templated_explanation


@dataclass(frozen=True, slots=True)
class ExplainContext:
    """Frozen bundle of the 13 fields ``templated_explanation`` accepts.

    Workers build this once per match between the score computation and the
    UPSERT, then hand it to whichever ``MatchExplainer`` is configured.
    """

    components: dict[str, float]
    vector: float
    structured: float
    total: float
    threshold: float
    job_title: str
    job_locations: list[str]
    job_min_exp_years: int
    job_max_exp_years: int
    job_ctc_max: Decimal | None
    employer_name: str
    applicant_expected_ctc: Decimal | None
    applicant_locations: list[str]


@runtime_checkable
class MatchExplainer(Protocol):
    """Returns the 4-key explanation dict stored on matches.explanation."""

    async def explain(self, ctx: ExplainContext) -> dict[str, str]: ...


def _templated_from_ctx(ctx: ExplainContext) -> dict[str, str]:
    """Shared helper — both TemplatedExplainer and the LLM impl's fallback call this."""
    return templated_explanation(
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


class TemplatedExplainer:
    """Async wrapper over the pure templated_explanation function.

    The ``async`` is interface uniformity; the body is sync.
    """

    async def explain(self, ctx: ExplainContext) -> dict[str, str]:
        return _templated_from_ctx(ctx)
