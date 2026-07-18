"""embed_job task — read a Job + Employer, embed, upsert job_embeddings.

Dispatched from the seed CLI's `_dispatch_embeds` post-commit. The body splits
work into three transactions identical in shape to embed_applicant's split: a
short-lock gate, a no-DB external call, and a verify-then-upsert close.
Holding a row lock across the Gemini API call would starve other writers.

EmbeddingProviderError → permanent failure → log + return (no row state to
clean up, no retry). TransientEmbeddingError → propagated → Celery autoretry
(up to 3 with backoff). Any other unexpected exception → wrapped into
TransientEmbeddingError → autoretry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from jobify.db.models import Employer, Job, JobEmbedding
from jobify.integrations.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingTask,
    TransientEmbeddingError,
)
from jobify.integrations.embeddings.canonicalize_job import canonicalize_job
from jobify.outbox import enqueue_task
from jobify_worker.async_bridge import run_async
from jobify_worker.celery_app import celery_app
from jobify_worker.runtime import get_embedding_provider, get_session_maker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


# --- Sync Celery entry point ---


@celery_app.task(  # type: ignore[untyped-decorator]
    name="jobify.embed_job",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientEmbeddingError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def embed_job(self, job_id_str: str) -> None:  # type: ignore[no-untyped-def]
    """Sync entry. Wraps the async body in a fresh event loop.

    When invoked in eager mode from within a running event loop (e.g. during
    integration tests via httpx.AsyncClient), ``asyncio.run()`` would raise
    RuntimeError because a loop is already running. In that case we delegate
    to a fresh thread so the inner ``asyncio.run()`` gets a clean loop.
    """

    run_async(lambda: _embed_job_async(UUID(job_id_str)))


# --- Async body ---


async def _embed_job_async(
    job_id: UUID,
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    provider: EmbeddingProvider | None = None,
) -> None:
    """Async body — split out for unit testing with injected fakes.

    Production callers (the Celery task) pass nothing; this resolves the real
    sessionmaker and GeminiEmbeddingProvider.
    """
    sm = sm or get_session_maker()
    provider = provider or get_embedding_provider()

    # --- Transaction 1: gate (load job + employer name, content hash) ---
    async with sm() as session:
        loaded = await _load_job_with_employer(session, job_id)
        if loaded is None:
            _log.info("embed.job-missing", job_id=str(job_id))
            return
        job, employer_name = loaded
        text, content_hash = canonicalize_job(job, employer_name=employer_name)
        existing = (
            await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job_id))
        ).scalar_one_or_none()
        if existing is not None and existing.canonicalized_text_hash == content_hash:
            _log.info("embed.job-idempotent-skip", job_id=str(job_id))
            return
        title = f"{job.title} at {employer_name}"

    # --- Transaction 2: no DB (Gemini call) ---
    try:
        result = await provider.encode(
            text=text,
            task=EmbeddingTask.DOCUMENT,
            title=title,
        )
    except EmbeddingProviderError as exc:
        _log.error(
            "embed.job-permanent-failure",
            job_id=str(job_id),
            error=str(exc),
        )
        return
    except TransientEmbeddingError:
        # Re-raise unchanged so Celery's autoretry_for tuple triggers.
        raise
    except Exception as exc:
        _log.exception("embed.job-unexpected", job_id=str(job_id))
        raise TransientEmbeddingError(f"unexpected: {type(exc).__name__}") from exc

    # --- Transaction 3: verify content hash still current, then upsert ---
    async with sm() as session:
        loaded_now = await _load_job_with_employer(session, job_id)
        if loaded_now is None:
            _log.info("embed.job-stale-gone", job_id=str(job_id))
            return
        job_now, employer_name_now = loaded_now
        _, content_hash_now = canonicalize_job(job_now, employer_name=employer_name_now)
        if content_hash_now != content_hash:
            _log.info(
                "embed.job-stale-content-aborted",
                job_id=str(job_id),
                computed_hash=content_hash,
                current_hash=content_hash_now,
            )
            return

        stmt = (
            pg_insert(JobEmbedding)
            .values(
                job_id=job_id,
                embedding=result.values,
                model_name=result.model_name,
                canonicalized_text_hash=content_hash,
                input_tokens=result.input_tokens,
            )
            .on_conflict_do_update(
                index_elements=["job_id"],
                set_={
                    "embedding": result.values,
                    "model_name": result.model_name,
                    "canonicalized_text_hash": content_hash,
                    "input_tokens": result.input_tokens,
                    "updated_at": func.now(),
                },
            )
        )
        await session.execute(stmt)
        enqueue_task(session, "jobify.score_job", str(job_id))
        await session.commit()

    _log.info(
        "embed.job-complete",
        job_id=str(job_id),
        model_name=result.model_name,
        input_tokens=result.input_tokens,
    )


async def _load_job_with_employer(session: AsyncSession, job_id: UUID) -> tuple[Job, str] | None:
    """Return ``(job, employer_name)`` or None.

    Returns None when either the job or its employer is soft-deleted, or when
    the job doesn't exist. Used by both Txn1 (gate) and Txn3 (verify) — the
    hash compare in Txn3 detects the race where the job content changed between
    Txn1 and Txn3.
    """
    row = (
        await session.execute(
            select(Job, Employer.name)
            .join(Employer, Job.employer_id == Employer.id)
            .where(
                Job.id == job_id,
                Job.deleted_at.is_(None),
                Employer.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        return None
    job, employer_name = row
    return job, employer_name
