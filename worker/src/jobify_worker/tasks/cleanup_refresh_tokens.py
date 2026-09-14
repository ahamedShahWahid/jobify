"""Prune stale refresh tokens (PERF-08) in bounded, looping batches.

``refresh_tokens`` has no ``deleted_at`` (append-only by convention — see
``jobify.db.models.RefreshToken``) and no prior cleanup: every refresh
rotation inserts a row and only marks the old one revoked, so the table
grows ~12 rows/active-user/day with nothing removing them.

Deletes a row once it is either naturally expired (``expires_at`` in the
past — never presented again, safe immediately) or revoked long enough ago
that its reuse-detection value has passed (``revoked_at`` older than
``refresh_token_retention_days``, default 7 — a revoked row found on replay
is what triggers family revocation in ``AuthService.refresh``; 7 days is far
past any plausible attacker replay window given the access-token TTL is
minutes). A live (unrevoked, unexpired) row is never a cleanup candidate.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import or_, select

from jobify.db.models import RefreshToken
from jobify_worker.async_bridge import run_async
from jobify_worker.celery_app import celery_app, settings
from jobify_worker.runtime import get_session_maker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


@celery_app.task(name="jobify.cleanup_refresh_tokens", acks_late=True)  # type: ignore[untyped-decorator]
def cleanup_refresh_tokens() -> int:
    return run_async(_cleanup_refresh_tokens_async)


async def _cleanup_refresh_tokens_async(
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    now: datetime | None = None,
) -> int:
    sm = sm or get_session_maker()
    now = now or datetime.now(UTC)
    revoked_cutoff = now - timedelta(days=settings.refresh_token_retention_days)

    total_deleted = 0
    exhausted = True
    for _ in range(settings.refresh_token_cleanup_max_batches):
        batch_deleted = await _delete_one_batch(sm, now=now, revoked_cutoff=revoked_cutoff)
        total_deleted += batch_deleted
        if batch_deleted < settings.refresh_token_cleanup_batch_size:
            exhausted = False
            break

    if exhausted:
        _log.warning(
            "refresh_tokens.cleanup-max-batches-reached",
            deleted_count=total_deleted,
            max_batches=settings.refresh_token_cleanup_max_batches,
            retention_days=settings.refresh_token_retention_days,
        )

    _log.info(
        "refresh_tokens.cleanup-completed",
        deleted_count=total_deleted,
        retention_days=settings.refresh_token_retention_days,
    )
    return total_deleted


async def _delete_one_batch(
    sm: async_sessionmaker[AsyncSession], *, now: datetime, revoked_cutoff: datetime
) -> int:
    async with sm() as session:
        rows = (
            (
                await session.execute(
                    select(RefreshToken)
                    .where(
                        or_(
                            RefreshToken.expires_at < now,
                            RefreshToken.revoked_at < revoked_cutoff,
                        )
                    )
                    .order_by(RefreshToken.expires_at, RefreshToken.id)
                    .limit(settings.refresh_token_cleanup_batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for token in rows:
            await session.delete(token)
        await session.commit()
    return len(rows)
