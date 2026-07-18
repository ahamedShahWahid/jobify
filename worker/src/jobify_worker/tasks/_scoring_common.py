"""Shared compute + UPSERT logic for score_applicant/score_job.

score_applicant paginates jobs for one fixed applicant; score_job paginates
applicants for one fixed job. Once each task has resolved its batch of
(applicant, job) scoring inputs, the compute -> explain -> UPSERT steps are
identical (both tasks used to hand-copy this) — this module is the one copy.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from jobify.db.models import Match
from jobify.outbox import enqueue_task
from jobify.scoring.explainer import ExplainContext
from jobify.scoring.match import MatchScore, TransientScoringError, score_match

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from jobify.scoring.explainer import MatchExplainer

# Upper bound on concurrent explain() calls per batch (LLM impl hits Gemini).
EXPLAIN_CONCURRENCY = 10


@dataclass(frozen=True, slots=True)
class ScoringInput:
    """One (applicant, job) pair's scalars needed to compute + explain a match."""

    applicant_id: UUID
    job_id: UUID
    applicant_embedding: list[float]
    applicant_embedding_model: str
    applicant_locations: list[str]
    applicant_years: Any
    applicant_expected_ctc: Any
    job_embedding: list[float]
    job_embedding_model: str
    job_title: str
    job_locations: list[str]
    job_min_exp_years: Any
    job_max_exp_years: Any
    job_ctc_min: Any
    job_ctc_max: Any
    employer_name: str


@dataclass(frozen=True, slots=True)
class ScoredMatch:
    """One computed + explained match, ready for the UPSERT."""

    applicant_id: UUID
    job_id: UUID
    score: MatchScore
    model_versions: dict[str, Any]
    explanation: dict[str, str]


def _compute(
    inp: ScoringInput, *, vector_weight: float, threshold: float
) -> tuple[MatchScore, ExplainContext]:
    """Pure (no I/O) match score + explain context for one pair."""
    ms = score_match(
        applicant_embedding=inp.applicant_embedding,
        job_embedding=inp.job_embedding,
        applicant_locations=inp.applicant_locations,
        applicant_years=inp.applicant_years,
        applicant_expected_ctc=inp.applicant_expected_ctc,
        job_locations=inp.job_locations,
        job_min_exp_years=inp.job_min_exp_years,
        job_max_exp_years=inp.job_max_exp_years,
        job_ctc_min=inp.job_ctc_min,
        job_ctc_max=inp.job_ctc_max,
        vector_weight=vector_weight,
        threshold=threshold,
    )
    ctx = ExplainContext(
        components=ms.components,
        vector=ms.vector,
        structured=ms.structured,
        total=ms.total,
        threshold=threshold,
        job_title=inp.job_title,
        job_locations=inp.job_locations,
        job_min_exp_years=inp.job_min_exp_years,
        job_max_exp_years=inp.job_max_exp_years,
        job_ctc_max=inp.job_ctc_max,
        employer_name=inp.employer_name,
        applicant_expected_ctc=inp.applicant_expected_ctc,
        applicant_locations=inp.applicant_locations,
    )
    return ms, ctx


async def explain_scores(
    explainer: MatchExplainer,
    inputs: list[ScoringInput],
    *,
    vector_weight: float,
    threshold: float,
) -> list[ScoredMatch]:
    """Compute + explain a batch, bounded so a large batch doesn't stampede the LLM API."""
    pending = [
        (inp, *_compute(inp, vector_weight=vector_weight, threshold=threshold)) for inp in inputs
    ]
    sem = asyncio.Semaphore(EXPLAIN_CONCURRENCY)

    async def _explain_bounded(ctx: ExplainContext) -> dict[str, str]:
        async with sem:
            return await explainer.explain(ctx)

    explanations = await asyncio.gather(*(_explain_bounded(ctx) for _, _, ctx in pending))
    return [
        ScoredMatch(
            applicant_id=inp.applicant_id,
            job_id=inp.job_id,
            score=ms,
            model_versions={
                "applicant_model": inp.applicant_embedding_model,
                "job_model": inp.job_embedding_model,
                "vector_weight": vector_weight,
                "threshold": threshold,
            },
            explanation=explanation,
        )
        for (inp, ms, _ctx), explanation in zip(pending, explanations, strict=True)
    ]


def match_upsert_statement(scored: ScoredMatch) -> Any:
    """The UPSERT both scoring tasks run per matched pair — same conflict target,
    same coalesce-guarded ``surfaced_at`` (never unset once set, see worker/CLAUDE.md
    -> Scoring worker)."""
    ms = scored.score
    return (
        pg_insert(Match)
        .values(
            applicant_id=scored.applicant_id,
            job_id=scored.job_id,
            vector_score=ms.vector,
            structured_score=ms.structured,
            total_score=ms.total,
            score_components=ms.components,
            model_versions=scored.model_versions,
            surfaced_at=func.now() if ms.crosses_threshold else None,
            explanation=scored.explanation,
        )
        .on_conflict_do_update(
            index_elements=["applicant_id", "job_id"],
            index_where=sa.text("deleted_at IS NULL"),
            set_={
                "vector_score": ms.vector,
                "structured_score": ms.structured,
                "total_score": ms.total,
                "score_components": ms.components,
                "model_versions": scored.model_versions,
                "surfaced_at": func.coalesce(
                    Match.surfaced_at,
                    sa.case(
                        (sa.literal(ms.crosses_threshold), func.now()),
                        else_=None,
                    ),
                ),
                "explanation": scored.explanation,
                "updated_at": func.now(),
            },
        )
    )


async def persist_score_batch(
    session_maker: async_sessionmaker[AsyncSession],
    scores: list[ScoredMatch],
    *,
    continuation: tuple[str, ...] | None,
    log: Any,
    log_context: dict[str, str],
) -> None:
    """Persist one scoring batch and its durable continuation atomically."""
    async with session_maker() as session:
        try:
            for scored in scores:
                await session.execute(match_upsert_statement(scored))
            if continuation is not None:
                task_name, *args = continuation
                enqueue_task(session, task_name, *args)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            log.exception("score.upsert-failed", **log_context)
            raise TransientScoringError(f"upsert failed: {type(exc).__name__}") from exc
