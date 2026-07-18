"""Database-backed health metrics for durable asynchronous work queues."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Notification, OutboxEvent

_NOTIFICATION_STATUSES = ("pending", "dispatching", "sent", "failed", "cancelled")
_OUTBOX_STATUSES = ("pending", "processing", "completed", "failed")


async def _status_counts(
    session: AsyncSession, model: type[Notification] | type[OutboxEvent]
) -> dict[str, int]:
    rows = (
        await session.execute(
            select(model.status, func.count(model.id))
            .where(model.deleted_at.is_(None))
            .group_by(model.status)
        )
    ).all()
    return {str(getattr(status, "value", status)): int(count) for status, count in rows}


async def _oldest_age_seconds(
    session: AsyncSession,
    model: type[Notification] | type[OutboxEvent],
    actionable_statuses: Sequence[str],
) -> float:
    oldest = (
        await session.execute(
            select(func.extract("epoch", func.now() - func.min(model.created_at))).where(
                model.deleted_at.is_(None), model.status.in_(actionable_statuses)
            )
        )
    ).scalar_one_or_none()
    return max(float(oldest or 0.0), 0.0)


async def render_async_work_metrics(session: AsyncSession) -> str:
    """Render queue depth and age using only fixed queue/status labels."""
    notification_counts = await _status_counts(session, Notification)
    outbox_counts = await _status_counts(session, OutboxEvent)
    notification_age = await _oldest_age_seconds(session, Notification, ("pending", "dispatching"))
    outbox_age = await _oldest_age_seconds(session, OutboxEvent, ("pending", "processing"))

    lines = [
        "# HELP jobify_async_metrics_up Whether durable async-work metrics "
        "were queried successfully.",
        "# TYPE jobify_async_metrics_up gauge",
        "jobify_async_metrics_up 1",
        "# HELP jobify_async_items Durable async-work rows by queue and status.",
        "# TYPE jobify_async_items gauge",
    ]
    for queue, statuses, counts in (
        ("notifications", _NOTIFICATION_STATUSES, notification_counts),
        ("outbox", _OUTBOX_STATUSES, outbox_counts),
    ):
        for status in statuses:
            lines.append(
                f'jobify_async_items{{queue="{queue}",status="{status}"}} {counts.get(status, 0)}'
            )
    lines.extend(
        [
            "# HELP jobify_async_oldest_actionable_age_seconds Age of the oldest "
            "live actionable row.",
            "# TYPE jobify_async_oldest_actionable_age_seconds gauge",
            'jobify_async_oldest_actionable_age_seconds{queue="notifications"} '
            f"{notification_age:.9g}",
            'jobify_async_oldest_actionable_age_seconds{queue="outbox"} ' f"{outbox_age:.9g}",
        ]
    )
    return "\n".join(lines) + "\n"
