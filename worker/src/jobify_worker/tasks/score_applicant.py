"""score_applicant task — score an applicant against every open job with an embedding.

Dispatched from embed_applicant Txn 3 post-commit. The body processes a bounded
batch of jobs, then dispatches a follow-up task after commit if more scoreable
jobs remain. Each batch has a two-transaction split: load + collect → no-DB
compute → UPSERT. No external API call so there's no need for the embed
worker's three-transaction shape.

surfaced_at semantics: set on first run that crosses threshold; preserved on
subsequent rescores even if total later drops below threshold. The UPSERT's
``set_`` clause uses ``coalesce(surfaced_at, CASE WHEN crosses THEN now() ELSE NULL END)``
so once non-null, the value is never overwritten.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import UUID

import sqlalchemy as sa
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from jobify.celery_app import celery_app
from jobify.celery_app import settings as _settings
from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    ApplicantPreferences,
    Employer,
    Job,
    JobEmbedding,
    JobStatus,
    Match,
)
from jobify.scoring.match import TransientScoringError, score_match
from jobify_worker.runtime import get_session_maker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)

# Upper bound on concurrent explain() calls per batch (LLM impl hits Gemini).
_EXPLAIN_CONCURRENCY = 10


@celery_app.task(  # type: ignore[untyped-decorator]
    name="jobify.score_applicant",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientScoringError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def score_applicant(  # type: ignore[no-untyped-def]
    self, applicant_id_str: str, after_job_id_str: str | None = None
) -> None:
    """Sync entry. Wraps the async body in a fresh event loop, with eager-mode thread hop."""

    def _run(coro_factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(asyncio.run, coro_factory())
                fut.result()
        else:
            asyncio.run(coro_factory())

    after_job_id = UUID(after_job_id_str) if after_job_id_str is not None else None
    _run(lambda: _score_applicant_async(UUID(applicant_id_str), after_job_id=after_job_id))


async def _score_applicant_async(
    applicant_id: UUID,
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    after_job_id: UUID | None = None,
    batch_size: int | None = None,
) -> None:
    sm = sm or get_session_maker()
    limit = batch_size or _settings.score_batch_size

    # --- Txn 1: load applicant + emb, list a bounded batch of scoreable jobs ---
    async with sm() as session:
        applicant_row = (
            await session.execute(
                select(Applicant, ApplicantEmbedding, ApplicantPreferences)
                .join(ApplicantEmbedding, ApplicantEmbedding.applicant_id == Applicant.id)
                .outerjoin(
                    ApplicantPreferences,
                    ApplicantPreferences.applicant_id == Applicant.id,
                )
                .where(
                    Applicant.id == applicant_id,
                    Applicant.deleted_at.is_(None),
                    ApplicantEmbedding.deleted_at.is_(None),
                    # NULL IS NULL is true, so a MISSING preferences row still
                    # passes (degrades to empty defaults below) — but nothing
                    # today ever soft-deletes an ApplicantPreferences row
                    # (only hard-deleted via DSR); if that ever changes, a
                    # soft-deleted row would fail this filter and silently
                    # drop the applicant from scoring instead of degrading.
                    ApplicantPreferences.deleted_at.is_(None),
                )
            )
        ).first()
        if applicant_row is None:
            _log.info("score.applicant-skipped", applicant_id=str(applicant_id))
            return
        applicant, applicant_emb, applicant_prefs = applicant_row

        jobs_stmt = (
            select(Job, JobEmbedding, Employer.name)
            .join(JobEmbedding, JobEmbedding.job_id == Job.id)
            .join(Employer, Employer.id == Job.employer_id)
            .where(
                Job.status == JobStatus.OPEN,
                Job.deleted_at.is_(None),
                JobEmbedding.deleted_at.is_(None),
                Employer.deleted_at.is_(None),
            )
            .order_by(Job.id.asc())
            .limit(limit + 1)
        )
        if after_job_id is not None:
            jobs_stmt = jobs_stmt.where(Job.id > after_job_id)
        job_rows = (await session.execute(jobs_stmt)).all()
        has_more = len(job_rows) > limit
        job_rows = job_rows[:limit]
        next_after_job_id = job_rows[-1][0].id if has_more and job_rows else None
        # Detach all entities from this session before closing — we read scalars in compute step.
        scored_inputs = []
        for job, job_emb, employer_name in job_rows:
            scored_inputs.append(
                (
                    job.id,
                    job.title,
                    list(job.locations or []),
                    job.min_exp_years,
                    job.max_exp_years,
                    job.ctc_min,
                    job.ctc_max,
                    list(job_emb.embedding),
                    job_emb.model_name,
                    employer_name,
                )
            )
        applicant_emb_vec = list(applicant_emb.embedding)
        applicant_emb_model = applicant_emb.model_name
        applicant_locs = list(applicant_prefs.locations or []) if applicant_prefs else []
        applicant_years = applicant.years_experience
        applicant_ctc = applicant_prefs.expected_ctc if applicant_prefs else None

    if not scored_inputs:
        _log.info(
            "score.no-scoreable-jobs",
            applicant_id=str(applicant_id),
            after_job_id=str(after_job_id) if after_job_id else None,
        )
        return

    # --- (no DB) compute ---
    from jobify.scoring.explainer import ExplainContext
    from jobify_worker.runtime import get_match_explainer

    _explainer = get_match_explainer()

    pending: list[tuple[UUID, Any, str, ExplainContext]] = []
    for (
        job_id,
        job_title,
        job_locs,
        job_min_exp,
        job_max_exp,
        job_ctc_min,
        job_ctc_max,
        job_emb_vec,
        job_emb_model,
        employer_name,
    ) in scored_inputs:
        ms = score_match(
            applicant_embedding=applicant_emb_vec,
            job_embedding=job_emb_vec,
            applicant_locations=applicant_locs,
            applicant_years=applicant_years,
            applicant_expected_ctc=applicant_ctc,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_min=job_ctc_min,
            job_ctc_max=job_ctc_max,
            vector_weight=_settings.match_vector_weight,
            threshold=_settings.match_surface_threshold,
        )
        ctx = ExplainContext(
            components=ms.components,
            vector=ms.vector,
            structured=ms.structured,
            total=ms.total,
            threshold=_settings.match_surface_threshold,
            job_title=job_title,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_max=job_ctc_max,
            employer_name=employer_name,
            applicant_expected_ctc=applicant_ctc,
            applicant_locations=applicant_locs,
        )
        pending.append((job_id, ms, job_emb_model, ctx))

    # explain() never raises (explainer contract) and the LLM impl is
    # I/O-bound — run the batch concurrently instead of one Gemini round-trip
    # per job, bounded so a large batch doesn't stampede the API.
    sem = asyncio.Semaphore(_EXPLAIN_CONCURRENCY)

    async def _explain_bounded(ctx: ExplainContext) -> dict[str, str]:
        async with sem:
            return await _explainer.explain(ctx)

    explanations = await asyncio.gather(*(_explain_bounded(ctx) for *_, ctx in pending))
    scores: list[tuple[UUID, Any, str, dict[str, str]]] = [
        (job_id, ms, model, explanation)
        for (job_id, ms, model, _ctx), explanation in zip(pending, explanations, strict=True)
    ]

    # --- Txn 2: UPSERT each row ---
    async with sm() as session:
        try:
            for job_id, ms, job_emb_model, explanation in scores:
                model_versions = {
                    "applicant_model": applicant_emb_model,
                    "job_model": job_emb_model,
                    "vector_weight": _settings.match_vector_weight,
                    "threshold": _settings.match_surface_threshold,
                }
                stmt = (
                    pg_insert(Match)
                    .values(
                        applicant_id=applicant_id,
                        job_id=job_id,
                        vector_score=ms.vector,
                        structured_score=ms.structured,
                        total_score=ms.total,
                        score_components=ms.components,
                        model_versions=model_versions,
                        surfaced_at=func.now() if ms.crosses_threshold else None,
                        explanation=explanation,
                    )
                    .on_conflict_do_update(
                        index_elements=["applicant_id", "job_id"],
                        index_where=sa.text("deleted_at IS NULL"),
                        set_={
                            "vector_score": ms.vector,
                            "structured_score": ms.structured,
                            "total_score": ms.total,
                            "score_components": ms.components,
                            "model_versions": model_versions,
                            "surfaced_at": func.coalesce(
                                Match.surfaced_at,
                                sa.case(
                                    (sa.literal(ms.crosses_threshold), func.now()),
                                    else_=None,
                                ),
                            ),
                            "explanation": explanation,
                            "updated_at": func.now(),
                        },
                    )
                )
                await session.execute(stmt)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            _log.exception("score.upsert-failed", applicant_id=str(applicant_id))
            raise TransientScoringError(f"upsert failed: {type(exc).__name__}") from exc

    _log.info(
        "score.applicant-complete",
        applicant_id=str(applicant_id),
        scored=len(scores),
        has_more=has_more,
    )
    if next_after_job_id is not None:
        _dispatch_next_batch(applicant_id, next_after_job_id)


def _dispatch_next_batch(applicant_id: UUID, after_job_id: UUID) -> None:
    """Continue applicant scoring after a successful committed batch."""
    try:
        score_applicant.delay(str(applicant_id), str(after_job_id))
    except Exception as exc:
        _log.exception(
            "score.next-batch-dispatch-failed",
            applicant_id=str(applicant_id),
            after_job_id=str(after_job_id),
        )
        raise TransientScoringError("next batch dispatch failed") from exc
