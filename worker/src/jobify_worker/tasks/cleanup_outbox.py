"""Prune expired terminal rows from the durable outbox in bounded batches."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from jobify.db.models import OutboxEvent, OutboxEventStatus
from jobify_worker.async_bridge import run_async
from jobify_worker.celery_app import celery_app, settings
from jobify_worker.runtime import get_session_maker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


@celery_app.task(name="jobify.cleanup_outbox", acks_late=True)  # type: ignore[untyped-decorator]
def cleanup_outbox() -> int:
    return run_async(_cleanup_outbox_async)


async def _cleanup_outbox_async(
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    now: datetime | None = None,
) -> int:
    sm = sm or get_session_maker()
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=settings.outbox_retention_days)

    total_deleted = 0
    exhausted = True
    for _ in range(settings.outbox_cleanup_max_batches):
        batch_deleted = await _delete_one_batch(sm, cutoff)
        total_deleted += batch_deleted
        if batch_deleted < settings.outbox_cleanup_batch_size:
            exhausted = False
            break

    if exhausted:
        _log.warning(
            "outbox.cleanup-max-batches-reached",
            deleted_count=total_deleted,
            max_batches=settings.outbox_cleanup_max_batches,
            retention_days=settings.outbox_retention_days,
            cutoff=cutoff,
        )

    _log.info(
        "outbox.cleanup-completed",
        deleted_count=total_deleted,
        retention_days=settings.outbox_retention_days,
        cutoff=cutoff,
    )
    return total_deleted


async def _delete_one_batch(sm: async_sessionmaker[AsyncSession], cutoff: datetime) -> int:
    async with sm() as session:
        rows = (
            (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.deleted_at.is_(None),
                        OutboxEvent.status.in_(
                            (OutboxEventStatus.COMPLETED, OutboxEventStatus.FAILED)
                        ),
                        OutboxEvent.updated_at < cutoff,
                    )
                    .order_by(OutboxEvent.updated_at, OutboxEvent.id)
                    .limit(settings.outbox_cleanup_batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for event in rows:
            await session.delete(event)
        await session.commit()
    return len(rows)
