"""Match-explanation Protocol + frozen context + templated impl.

Wraps the pure-function ``templated_explanation`` from ``jobify.scoring.explain`` in
an async Protocol so the score workers can route between templated and LLM impls
behind a single call site. The LLM impl lives in ``jobify.scoring.llm_explainer``
so importing this module does not pull in ``google.genai``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from jobify.scoring.explain import GENERATOR_VERSION as _TEMPLATED_GENERATOR_VERSION
from jobify.scoring.explain import templated_explanation


@dataclass(frozen=True, slots=True)
class ExplainContext:
    """Frozen bundle of the 14 fields ``templated_explanation`` accepts.

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
    language: str = "en"


@runtime_checkable
class MatchExplainer(Protocol):
    """Returns the 4-key explanation dict stored on matches.explanation."""

    #: Static per-instance tag (never derived from a response). Callers use
    #: this to build a cache-key candidate BEFORE calling explain() — see
    #: explanation_cache_key(). A generator_version bump (a deliberate
    #: prompt/template change) therefore invalidates every previously cached
    #: explanation automatically, since it's part of the key.
    generator_version: str

    async def explain(self, ctx: ExplainContext) -> dict[str, str]: ...


def explanation_cache_key(ctx: ExplainContext, *, generator_version: str) -> str:
    """Content-address the inputs that actually vary an LLM explanation.

    Deliberately excludes vector/structured/total scores: only the three
    rounded components (location/exp/ctc, at the same 2-decimal precision
    GeminiMatchExplainer's prompt uses) plus the static job/applicant facts
    feed the prompt text. A job's description-only edit re-embeds it (moves
    the vector score) without changing any of this — so a batch re-run after
    one produces the same key and can skip the LLM call entirely.

    Only meaningful for a surfaced (>= threshold) pair headed for the LLM
    explainer; callers gate on that before using this (a below-threshold ctx
    always short-circuits to templated regardless of any cache).
    """
    parts = [
        generator_version,
        ctx.language,
        ctx.job_title,
        "|".join(ctx.job_locations),
        str(ctx.job_min_exp_years),
        str(ctx.job_max_exp_years),
        str(ctx.job_ctc_max) if ctx.job_ctc_max is not None else "",
        ctx.employer_name,
        str(ctx.applicant_expected_ctc) if ctx.applicant_expected_ctc is not None else "",
        "|".join(ctx.applicant_locations),
        f"{ctx.components.get('location', 0.5):.2f}",
        f"{ctx.components.get('exp', 0.5):.2f}",
        f"{ctx.components.get('ctc', 0.5):.2f}",
    ]
    digest_input = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


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
        language=ctx.language,
    )


class TemplatedExplainer:
    """Async wrapper over the pure templated_explanation function.

    The ``async`` is interface uniformity; the body is sync.
    """

    generator_version = _TEMPLATED_GENERATOR_VERSION

    async def explain(self, ctx: ExplainContext) -> dict[str, str]:
        return _templated_from_ctx(ctx)
