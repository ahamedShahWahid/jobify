"""score_job task — score every applicant-with-embedding against this job.

Mirror of score_applicant. Dispatched from embed_job Txn 3 post-commit.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlalchemy import and_, select

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
)
from jobify.scoring.match import TransientScoringError
from jobify_worker.runtime import get_session_maker
from jobify_worker.tasks._scoring_common import ScoringInput, explain_scores, match_upsert_statement

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="jobify.score_job",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientScoringError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def score_job(  # type: ignore[no-untyped-def]
    self, job_id_str: str, after_applicant_id_str: str | None = None
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

    after_applicant_id = (
        UUID(after_applicant_id_str) if after_applicant_id_str is not None else None
    )
    _run(lambda: _score_job_async(UUID(job_id_str), after_applicant_id=after_applicant_id))


async def _score_job_async(
    job_id: UUID,
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    after_applicant_id: UUID | None = None,
    batch_size: int | None = None,
) -> None:
    sm = sm or get_session_maker()
    limit = batch_size or _settings.score_batch_size

    # --- Txn 1: load job + emb, list a bounded batch of applicants with embeddings ---
    async with sm() as session:
        job_row = (
            await session.execute(
                select(Job, JobEmbedding, Employer.name)
                .join(JobEmbedding, JobEmbedding.job_id == Job.id)
                .join(Employer, Employer.id == Job.employer_id)
                .where(
                    Job.id == job_id,
                    Job.status == JobStatus.OPEN,
                    Job.deleted_at.is_(None),
                    JobEmbedding.deleted_at.is_(None),
                    Employer.deleted_at.is_(None),
                )
            )
        ).first()
        if job_row is None:
            _log.info("score.job-skipped", job_id=str(job_id))
            return
        job, job_emb, employer_name = job_row

        apps_stmt = (
            select(Applicant, ApplicantEmbedding, ApplicantPreferences)
            .join(ApplicantEmbedding, ApplicantEmbedding.applicant_id == Applicant.id)
            .outerjoin(
                ApplicantPreferences,
                and_(
                    ApplicantPreferences.applicant_id == Applicant.id,
                    ApplicantPreferences.deleted_at.is_(None),
                ),
            )
            .where(
                Applicant.deleted_at.is_(None),
                ApplicantEmbedding.deleted_at.is_(None),
            )
            .order_by(Applicant.id.asc())
            .limit(limit + 1)
        )
        if after_applicant_id is not None:
            apps_stmt = apps_stmt.where(Applicant.id > after_applicant_id)
        app_rows = (await session.execute(apps_stmt)).all()
        has_more = len(app_rows) > limit
        app_rows = app_rows[:limit]
        next_after_applicant_id = app_rows[-1][0].id if has_more and app_rows else None
        # Detach all entities from this session before closing — we read scalars in compute step.
        scored_inputs = []
        for applicant, applicant_emb, applicant_prefs in app_rows:
            if applicant_prefs is None:
                # Eager creation at signup means this should never fire for a
                # real applicant — degrading to empty preferences here.
                _log.warning(
                    "score.preferences-missing",
                    applicant_id=str(applicant.id),
                    job_id=str(job_id),
                )
            scored_inputs.append(
                (
                    applicant.id,
                    list(applicant_prefs.locations or []) if applicant_prefs else [],
                    applicant.years_experience,
                    applicant_prefs.expected_ctc if applicant_prefs else None,
                    list(applicant_emb.embedding),
                    applicant_emb.model_name,
                )
            )
        job_emb_vec = list(job_emb.embedding)
        job_emb_model = job_emb.model_name
        job_title = job.title
        job_locs = list(job.locations or [])
        job_min_exp = job.min_exp_years
        job_max_exp = job.max_exp_years
        job_ctc_min = job.ctc_min
        job_ctc_max = job.ctc_max
        job_employer_name = employer_name

    if not scored_inputs:
        _log.info(
            "score.no-scoreable-applicants",
            job_id=str(job_id),
            after_applicant_id=str(after_applicant_id) if after_applicant_id else None,
        )
        return

    # --- (no DB) compute + explain ---
    from jobify_worker.runtime import get_match_explainer

    scoring_inputs = [
        ScoringInput(
            applicant_id=applicant_id,
            job_id=job_id,
            applicant_embedding=applicant_emb_vec,
            applicant_embedding_model=applicant_emb_model,
            applicant_locations=applicant_locs,
            applicant_years=applicant_years,
            applicant_expected_ctc=applicant_ctc,
            job_embedding=job_emb_vec,
            job_embedding_model=job_emb_model,
            job_title=job_title,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_min=job_ctc_min,
            job_ctc_max=job_ctc_max,
            employer_name=job_employer_name,
        )
        for (
            applicant_id,
            applicant_locs,
            applicant_years,
            applicant_ctc,
            applicant_emb_vec,
            applicant_emb_model,
        ) in scored_inputs
    ]
    scores = await explain_scores(
        get_match_explainer(),
        scoring_inputs,
        vector_weight=_settings.match_vector_weight,
        threshold=_settings.match_surface_threshold,
    )

    # --- Txn 2: UPSERT each row ---
    async with sm() as session:
        try:
            for scored in scores:
                await session.execute(match_upsert_statement(scored))
            await session.commit()
        except Exception as exc:
            await session.rollback()
            _log.exception("score.upsert-failed", job_id=str(job_id))
            raise TransientScoringError(f"upsert failed: {type(exc).__name__}") from exc

    _log.info("score.job-complete", job_id=str(job_id), scored=len(scores), has_more=has_more)
    if next_after_applicant_id is not None:
        _dispatch_next_batch(job_id, next_after_applicant_id)


def _dispatch_next_batch(job_id: UUID, after_applicant_id: UUID) -> None:
    """Continue job scoring after a successful committed batch."""
    try:
        score_job.delay(str(job_id), str(after_applicant_id))
    except Exception as exc:
        _log.exception(
            "score.next-batch-dispatch-failed",
            job_id=str(job_id),
            after_applicant_id=str(after_applicant_id),
        )
        raise TransientScoringError("next batch dispatch failed") from exc
