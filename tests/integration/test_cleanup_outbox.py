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


async def test_cleanup_loops_across_batches_until_backlog_is_empty(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PERF-06: a single 1000-row batch/day couldn't keep up with a backlog
    that grows faster than that (every resume upload stages 3+ outbox
    events). Batch size is now just a per-transaction chunk size, not a
    per-run cap — the task loops until a batch comes back short.
    """
    now = datetime(2026, 7, 18, tzinfo=UTC)
    rows = [
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=now - timedelta(days=31),
        )
        for _ in range(5)
    ]
    session.add_all(rows)
    await session.commit()
    row_ids = [row.id for row in rows]
    monkeypatch.setattr(settings, "outbox_cleanup_batch_size", 2)

    assert await _cleanup_outbox_async(sm=_make_sm(session), now=now) == 5

    remaining = (
        (await session.execute(select(OutboxEvent.id).where(OutboxEvent.id.in_(row_ids))))
        .scalars()
        .all()
    )
    assert remaining == []


async def test_cleanup_stops_and_warns_at_the_max_batches_safety_cap(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backlog too large to clear in max_batches stops rather than holding
    the outbox queue's worker for an unbounded number of batches — and warns,
    since stopping short of a full cleanup should never be silent.
    """
    now = datetime(2026, 7, 18, tzinfo=UTC)
    rows = [
        OutboxEvent(
            kind=OutboxEventKind.TASK_DISPATCH,
            status=OutboxEventStatus.COMPLETED,
            payload={},
            updated_at=now - timedelta(days=31),
        )
        for _ in range(5)
    ]
    session.add_all(rows)
    await session.commit()
    row_ids = [row.id for row in rows]
    monkeypatch.setattr(settings, "outbox_cleanup_batch_size", 1)
    monkeypatch.setattr(settings, "outbox_cleanup_max_batches", 2)

    with capture_logs() as captured:
        assert await _cleanup_outbox_async(sm=_make_sm(session), now=now) == 2

    remaining = (
        (await session.execute(select(OutboxEvent.id).where(OutboxEvent.id.in_(row_ids))))
        .scalars()
        .all()
    )
    assert len(remaining) == 3
    warnings = [c for c in captured if c["event"] == "outbox.cleanup-max-batches-reached"]
    assert len(warnings) == 1
    assert warnings[0]["deleted_count"] == 2
    assert warnings[0]["max_batches"] == 2
