from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog.testing import capture_logs

from jobify.db.models import OutboxEvent, OutboxEventKind, OutboxEventStatus
from jobify_worker.celery_app import settings
from jobify_worker.tasks.cleanup_outbox import _cleanup_outbox_async

pytestmark = pytest.mark.integration


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


async def test_cleanup_deletes_only_expired_live_terminal_rows(
    session: AsyncSession,
) -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    old = now - timedelta(days=31)
    rows = [
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={"storage_key": "must-not-be-logged"},
            updated_at=old,
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.FAILED,
            payload={},
            updated_at=old,
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=now - timedelta(days=1),
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.PENDING,
            payload={"task_name": "jobify.parse_resume", "args": ["pending"]},
            updated_at=old,
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=old,
            deleted_at=now - timedelta(days=2),
        ),
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.FAILED,
            payload={},
            updated_at=now - timedelta(days=30),
        ),
    ]
    session.add_all(rows)
    await session.commit()
    deleted_ids = {rows[0].id, rows[1].id}

    with capture_logs() as captured:
        assert await _cleanup_outbox_async(sm=_make_sm(session), now=now) == 2

    remaining = set(
        (
            await session.execute(
                select(OutboxEvent.id).where(OutboxEvent.id.in_([row.id for row in rows]))
            )
        ).scalars()
    )
    assert deleted_ids.isdisjoint(remaining)
    assert len(remaining) == 4
    assert captured == [
        {
            "event": "outbox.cleanup-completed",
            "log_level": "info",
            "deleted_count": 2,
            "retention_days": 30,
            "cutoff": now - timedelta(days=30),
        }
    ]
    assert "must-not-be-logged" not in repr(captured)


async def test_cleanup_respects_batch_limit(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    session.add_all(
        [
            OutboxEvent(
                kind=OutboxEventKind.TASK_DISPATCH,
                status=OutboxEventStatus.COMPLETED,
                payload={},
                updated_at=now - timedelta(days=31),
            )
            for _ in range(2)
        ]
    )
    await session.commit()
    monkeypatch.setattr(settings, "outbox_cleanup_batch_size", 1)

    assert await _cleanup_outbox_async(sm=_make_sm(session), now=now) == 1
