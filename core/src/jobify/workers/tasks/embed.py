"""embed_applicant task — read latest parsed resume, embed, upsert.

Dispatched from parse_resume's Txn3. The body splits work into three
transactions identical in shape to parse_resume's split: a short-lock gate,
a no-DB external call, and a verify-then-upsert close. Holding a row lock
across the Gemini API call would starve other writers.

EmbeddingProviderError → permanent failure → log + return (no row state to
clean up, no retry). TransientEmbeddingError → propagated → Celery autoretry
(up to 3 with backoff). Any other unexpected exception → wrapped into
TransientEmbeddingError → autoretry.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from jobify.db.models import Applicant, ApplicantEmbedding, Resume, ResumeParseStatus
from jobify.integrations.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingTask,
    TransientEmbeddingError,
)
from jobify.integrations.embeddings.canonicalize import canonicalize_profile
from jobify.integrations.parser.base import ParsedResume
from jobify.workers.celery_app import (
    celery_app,
    get_embedding_provider,
    get_session_maker,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


# --- Sync Celery entry point ---


@celery_app.task(  # type: ignore[untyped-decorator]
    name="jobify.embed_applicant",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientEmbeddingError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def embed_applicant(self, applicant_id_str: str) -> None:  # type: ignore[no-untyped-def]
    """Sync entry. Wraps the async body in a fresh event loop.

    When invoked in eager mode from within a running event loop (e.g. during
    integration tests via httpx.AsyncClient), ``asyncio.run()`` would raise
    RuntimeError because a loop is already running. In that case we delegate
    to a fresh thread so the inner ``asyncio.run()`` gets a clean loop.
    """

    def _run(coro_factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """Run a coroutine, dispatching to a thread if a loop is running."""
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

    _run(lambda: _embed_applicant_async(UUID(applicant_id_str)))


# --- Async body ---


async def _embed_applicant_async(
    applicant_id: UUID,
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

    # --- Transaction 1: gate (load applicant + latest parsed resume, content hash) ---
    async with sm() as session:
        applicant = await session.get(Applicant, applicant_id)
        if applicant is None or applicant.deleted_at is not None:
            _log.warning("embed.applicant-missing", applicant_id=str(applicant_id))
            return
        latest = await _load_latest_parsed_resume(session, applicant_id)
        if latest is None or latest.parsed_json is None:
            _log.info("embed.no-parsed-resume", applicant_id=str(applicant_id))
            return
        parsed = ParsedResume.model_validate(latest.parsed_json)
        text, content_hash = canonicalize_profile(parsed, full_name=applicant.full_name or "")
        existing = (
            await session.execute(
                select(ApplicantEmbedding).where(ApplicantEmbedding.applicant_id == applicant_id)
            )
        ).scalar_one_or_none()
        if existing is not None and existing.canonicalized_text_hash == content_hash:
            _log.info("embed.idempotent-skip", applicant_id=str(applicant_id))
            return
        title = applicant.full_name

    # --- Transaction 2: no DB (Gemini call) ---
    try:
        result = await provider.encode(
            text=text,
            task=EmbeddingTask.DOCUMENT,
            title=title,
        )
    except EmbeddingProviderError as exc:
        _log.error(
            "embed.permanent-failure",
            applicant_id=str(applicant_id),
            error=str(exc),
        )
        return  # No row state to clean up; no retry.
    except TransientEmbeddingError:
        # Explicit catch-and-reraise is load-bearing: without it, the bare
        # ``except Exception`` below would wrap this into a NEW
        # TransientEmbeddingError and the original message would be lost.
        # Celery's autoretry_for tuple includes TransientEmbeddingError, so
        # re-raising unchanged triggers the autoretry path with full context.
        raise
    except Exception as exc:
        _log.exception("embed.unexpected", applicant_id=str(applicant_id))
        # Wrap so it hits the autoretry list, but cap by Celery's max_retries.
        raise TransientEmbeddingError(f"unexpected: {type(exc).__name__}") from exc

    # --- Transaction 3: verify content hash still current, then upsert ---
    async with sm() as session:
        applicant_now = await session.get(Applicant, applicant_id)
        if applicant_now is None or applicant_now.deleted_at is not None:
            _log.info("embed.stale-applicant-gone", applicant_id=str(applicant_id))
            return
        latest_now = await _load_latest_parsed_resume(session, applicant_id)
        if latest_now is None or latest_now.parsed_json is None:
            _log.info("embed.stale-no-parsed-resume", applicant_id=str(applicant_id))
            return
        parsed_now = ParsedResume.model_validate(latest_now.parsed_json)
        _, content_hash_now = canonicalize_profile(
            parsed_now, full_name=applicant_now.full_name or ""
        )
        if content_hash_now != content_hash:
            _log.info(
                "embed.stale-content-aborted",
                applicant_id=str(applicant_id),
                computed_hash=content_hash,
                current_hash=content_hash_now,
            )
            return

        stmt = (
            pg_insert(ApplicantEmbedding)
            .values(
                applicant_id=applicant_id,
                embedding=result.values,
                model_name=result.model_name,
                canonicalized_text_hash=content_hash,
                input_tokens=result.input_tokens,
            )
            .on_conflict_do_update(
                index_elements=["applicant_id"],
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
        await session.commit()

    _log.info(
        "embed.complete",
        applicant_id=str(applicant_id),
        model_name=result.model_name,
        input_tokens=result.input_tokens,
    )
    _dispatch_score(applicant_id)


def _dispatch_score(applicant_id: UUID) -> None:
    """Fire score_applicant.delay(...) post-embed, fire-and-forget.

    Broker outage MUST NOT propagate — the embedding is durable. Same broad-except
    + warning-log pattern as the upload route → parse worker dispatch.
    """
    from jobify.workers.tasks.score_applicant import score_applicant

    try:
        score_applicant.delay(str(applicant_id))
    except Exception:
        _log.warning("score.dispatch-failed", applicant_id=str(applicant_id), exc_info=True)


async def _load_latest_parsed_resume(session: AsyncSession, applicant_id: UUID) -> Resume | None:
    """Return the most recently created parsed resume for an applicant.

    Used by both Txn1 (gate) and Txn3 (verify) to read the same row twice; the
    hash compare in Txn3 detects the race where a newer resume parsed between
    Txn1 and Txn3.
    """
    return (
        await session.execute(
            select(Resume)
            .where(
                Resume.applicant_id == applicant_id,
                Resume.parse_status == ResumeParseStatus.PARSED,
                Resume.deleted_at.is_(None),
            )
            .order_by(Resume.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
