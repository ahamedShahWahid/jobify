"""parse_resume task — extract text, parse to structured JSON, persist.

Sync Celery entry point wraps an asyncio body via :func:`asyncio.run`. The
async body splits work into three transactions:

1. Load + idempotency gate + mark `parse_status=parsing` (commit). Holds a
   short row lock only.
2. (no DB) Read bytes from storage, call extract_text(), call parser.parse().
   Can take seconds; no row lock held.
3. Re-load row inside a fresh session, verify it's still `parsing`, write
   `parsed_json` + `parse_status=parsed`, commit.

ParserError → permanent failure → `parse_status=failed` immediately, no retry.
TransientParserError → propagated → Celery autoretry (up to 3 with backoff).
Any other unexpected exception → wrapped → retried up to max_retries.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from jobify.db.models import Resume, ResumeParseStatus
from jobify.integrations.parser.base import (
    ParsedResume,
    ParserError,
    ResumeParser,
    TransientParserError,
)
from jobify.integrations.parser.library import LibraryResumeParser
from jobify.integrations.storage.local import LocalFileStorage
from jobify.workers.celery_app import celery_app, get_session_maker, settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


# --- Sync Celery entry point ---


@celery_app.task(  # type: ignore[untyped-decorator]
    name="jobify.parse_resume",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientParserError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def parse_resume(self, resume_id_str: str) -> None:  # type: ignore[no-untyped-def]
    """Sync entry. Wraps the async body in a fresh event loop.

    On TransientParserError: if we've exhausted retries, mark the row failed
    *before* re-raising so Celery's MaxRetriesExceededError doesn't leave the
    row stuck at PARSING. On any other completion path, do nothing (the async
    body owns failed/parsed transitions via _mark_failed and Txn3).

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

    try:
        _run(lambda: _parse_resume_async(UUID(resume_id_str)))
    except TransientParserError as exc:
        if self.request.retries >= self.max_retries:
            # Capture the reason string before the except-clause variable goes
            # out of scope in Python 3, so the helper lambda captures a str
            # (not the exception object itself).
            reason = f"max_retries_exceeded: {exc}"
            _run(
                lambda: _mark_failed(
                    get_session_maker(),
                    UUID(resume_id_str),
                    reason=reason,
                )
            )
        raise


# --- Async body ---


async def _parse_resume_async(
    resume_id: UUID,
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    storage: object | None = None,
    parser: ResumeParser | None = None,
) -> None:
    """Async body — split out for unit testing with injected fakes.

    Production callers (the Celery task) pass nothing; this resolves the real
    sessionmaker, LocalFileStorage, and LibraryResumeParser.
    """
    sm = sm or get_session_maker()
    storage = storage or LocalFileStorage(root=settings.storage_root)
    parser = parser or LibraryResumeParser()

    # --- Transaction 1: load + gate + mark parsing ---
    async with sm() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            _log.warning("parse.row-missing", resume_id=str(resume_id))
            return
        if resume.deleted_at is not None or resume.storage_key is None:
            _log.info("parse.skip-deleted", resume_id=str(resume_id))
            return

        if resume.parse_status in {
            ResumeParseStatus.PARSED,
            ResumeParseStatus.FAILED,
        }:
            # Terminal: never re-process a parsed/failed row.
            _log.info(
                "parse.skip-terminal",
                resume_id=str(resume_id),
                status=resume.parse_status.value,
            )
            return
        # PENDING or PARSING both proceed. PARSING happens when this is a
        # retry after a TransientParserError — we want the retry to do work,
        # not no-op. Re-marking parsing is idempotent.

        resume.parse_status = ResumeParseStatus.PARSING
        storage_key = resume.storage_key
        content_type = resume.content_type
        await session.commit()

    # --- Outside any DB txn: read + extract + parse ---
    try:
        content = await storage.read(storage_key)  # type: ignore[attr-defined]
        parsed: ParsedResume = await parser.parse(content=content, content_type=content_type)
    except ParserError as exc:
        await _mark_failed(sm, resume_id, reason=str(exc))
        return
    except TransientParserError:
        # Reraise unchanged so Celery autoretry fires. Row stays at 'parsing'.
        raise
    except Exception as exc:
        _log.exception("parse.unexpected", resume_id=str(resume_id))
        # Wrap so it hits the autoretry list, but cap by Celery's max_retries.
        raise TransientParserError(f"unexpected: {type(exc).__name__}") from exc

    # --- Transaction 3: re-load + verify + persist final ---
    async with sm() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None or resume.parse_status != ResumeParseStatus.PARSING:
            _log.warning(
                "parse.row-mutated-mid-parse",
                resume_id=str(resume_id),
                current_status=resume.parse_status.value if resume else "missing",
            )
            return
        resume.parsed_json = parsed.model_dump(mode="json")
        resume.parse_status = ResumeParseStatus.PARSED
        resume.parse_error = None
        await session.commit()

    # Dispatch async embedding — broker outages MUST NOT fail the parse
    # because parsed_json is already durable. Admin tooling can replay
    # missing applicant_embeddings rows after the broker recovers.
    #
    # Lazy import: jobify.workers.tasks.embed is autodiscovered by Celery but
    # we keep the import deferred to dispatch time so that import-time
    # failures in test collection (where env vars aren't yet set) don't
    # cascade through this module.
    try:
        from jobify.workers.tasks.embed import embed_applicant

        embed_applicant.delay(str(resume.applicant_id))
    except Exception as exc:
        _log.warning(
            "embed.dispatch-failed",
            applicant_id=str(resume.applicant_id),
            resume_id=str(resume_id),
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=True,
        )

    _log.info(
        "parse.complete",
        resume_id=str(resume_id),
        parser=parsed.parser_name,
        skills_count=len(parsed.skills),
    )


async def _mark_failed(
    sm: async_sessionmaker[AsyncSession],
    resume_id: UUID,
    *,
    reason: str,
) -> None:
    async with sm() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            return
        if resume.parse_status != ResumeParseStatus.PARSING:
            # Row was mutated externally (admin reset, another worker took over,
            # or another retry attempt). Don't clobber a non-PARSING status.
            _log.warning(
                "parse.mark-failed-skipped",
                resume_id=str(resume_id),
                current_status=resume.parse_status.value,
            )
            return
        resume.parse_status = ResumeParseStatus.FAILED
        resume.parse_error = reason[:1000]
        await session.commit()
    _log.warning("parse.failed", resume_id=str(resume_id), reason=reason)
