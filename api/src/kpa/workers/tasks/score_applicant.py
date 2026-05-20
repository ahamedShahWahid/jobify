"""score_applicant task — score an applicant against every open job with an embedding.

Dispatched from embed_applicant Txn 3 post-commit. The body has a
two-transaction split: load + collect → no-DB compute → UPSERT. No external
API call so there's no need for the embed worker's three-transaction shape.

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

from kpa.db.models import (
    Applicant,
    ApplicantEmbedding,
    Job,
    JobEmbedding,
    JobStatus,
    Match,
)
from kpa.scoring.match import TransientScoringError, score_match
from kpa.settings import Settings
from kpa.workers.celery_app import celery_app, get_session_maker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)
_settings = Settings()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="kpa.score_applicant",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientScoringError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def score_applicant(self, applicant_id_str: str) -> None:  # type: ignore[no-untyped-def]
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

    _run(lambda: _score_applicant_async(UUID(applicant_id_str)))


async def _score_applicant_async(
    applicant_id: UUID,
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    sm = sm or get_session_maker()

    # --- Txn 1: load applicant + emb, list scoreable jobs ---
    async with sm() as session:
        applicant_row = (
            await session.execute(
                select(Applicant, ApplicantEmbedding)
                .join(ApplicantEmbedding, ApplicantEmbedding.applicant_id == Applicant.id)
                .where(
                    Applicant.id == applicant_id,
                    Applicant.deleted_at.is_(None),
                    ApplicantEmbedding.deleted_at.is_(None),
                )
            )
        ).first()
        if applicant_row is None:
            _log.info("score.applicant-skipped", applicant_id=str(applicant_id))
            return
        applicant, applicant_emb = applicant_row

        job_rows = (
            await session.execute(
                select(Job, JobEmbedding)
                .join(JobEmbedding, JobEmbedding.job_id == Job.id)
                .where(
                    Job.status == JobStatus.OPEN,
                    Job.deleted_at.is_(None),
                    JobEmbedding.deleted_at.is_(None),
                )
            )
        ).all()
        # Detach all entities from this session before closing — we read scalars in compute step.
        scored_inputs = []
        for job, job_emb in job_rows:
            scored_inputs.append(
                (
                    job.id,
                    list(job.locations or []),
                    job.min_exp_years,
                    job.max_exp_years,
                    job.ctc_min,
                    job.ctc_max,
                    list(job_emb.embedding),
                    job_emb.model_name,
                )
            )
        applicant_emb_vec = list(applicant_emb.embedding)
        applicant_emb_model = applicant_emb.model_name
        applicant_locs = list(applicant.locations or [])
        applicant_years = applicant.years_experience
        applicant_ctc = applicant.expected_ctc

    if not scored_inputs:
        _log.info("score.no-scoreable-jobs", applicant_id=str(applicant_id))
        return

    # --- (no DB) compute ---
    scores: list[tuple[UUID, Any, Any]] = []
    for (
        job_id,
        job_locs,
        job_min_exp,
        job_max_exp,
        job_ctc_min,
        job_ctc_max,
        job_emb_vec,
        job_emb_model,
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
        scores.append((job_id, ms, job_emb_model))

    # --- Txn 2: UPSERT each row ---
    async with sm() as session:
        try:
            for job_id, ms, job_emb_model in scores:
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
    )
