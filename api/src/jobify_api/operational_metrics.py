"""Database-backed health metrics for durable asynchronous work queues.

The route fetches an :class:`AsyncWorkSnapshot` with the async session, then
hands it to a per-scrape :class:`AsyncWorkCollector` — ``Collector.collect()``
is synchronous, so the query cannot run inside it. Labels use only the fixed
queue/status sets below.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.metrics_core import Metric
from prometheus_client.registry import Collector
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Notification, OutboxEvent

_NOTIFICATION_STATUSES: Final = ("pending", "dispatching", "sent", "failed", "cancelled")
_OUTBOX_STATUSES: Final = ("pending", "processing", "completed", "failed")


@dataclass(frozen=True)
class AsyncWorkSnapshot:
    notification_counts: dict[str, int]
    outbox_counts: dict[str, int]
    notification_oldest_age_seconds: float
    outbox_oldest_age_seconds: float


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


async def fetch_async_work_snapshot(session: AsyncSession) -> AsyncWorkSnapshot:
    """Query queue depth and oldest actionable age for both durable queues."""
    return AsyncWorkSnapshot(
        notification_counts=await _status_counts(session, Notification),
        outbox_counts=await _status_counts(session, OutboxEvent),
        notification_oldest_age_seconds=await _oldest_age_seconds(
            session, Notification, ("pending", "dispatching")
        ),
        outbox_oldest_age_seconds=await _oldest_age_seconds(
            session, OutboxEvent, ("pending", "processing")
        ),
    )


class AsyncWorkCollector(Collector):
    """Per-scrape collector; ``None`` means the query failed (``up`` = 0 only)."""

    def __init__(self, snapshot: AsyncWorkSnapshot | None) -> None:
        self._snapshot = snapshot

    def collect(self) -> Iterable[Metric]:
        snapshot = self._snapshot
        yield GaugeMetricFamily(
            "jobify_async_metrics_up",
            "Whether durable async-work metrics were queried successfully.",
            value=0 if snapshot is None else 1,
        )
        if snapshot is None:
            return
        items = GaugeMetricFamily(
            "jobify_async_items",
            "Durable async-work rows by queue and status.",
            labels=["queue", "status"],
        )
        for queue, statuses, counts in (
            ("notifications", _NOTIFICATION_STATUSES, snapshot.notification_counts),
            ("outbox", _OUTBOX_STATUSES, snapshot.outbox_counts),
        ):
            for status in statuses:
                items.add_metric([queue, status], counts.get(status, 0))
        yield items
        ages = GaugeMetricFamily(
            "jobify_async_oldest_actionable_age_seconds",
            "Age of the oldest live actionable row.",
            labels=["queue"],
        )
        ages.add_metric(["notifications"], snapshot.notification_oldest_age_seconds)
        ages.add_metric(["outbox"], snapshot.outbox_oldest_age_seconds)
        yield ages
