from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jobify.db.models import OutboxEvent, OutboxEventKind, OutboxEventStatus
from jobify_worker.scripts.requeue_outbox import _requeue_rows


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.mark.integration
async def test_requeue_dry_run_does_not_mutate_failed_event(
    session: AsyncSession,
) -> None:
    token = uuid4()
    failed = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.FAILED,
        attempts=10,
        last_error="broker down",
        locked_until=datetime.now(UTC) - timedelta(minutes=1),
        dispatch_token=token,
        payload={"task_name": "jobify.parse_resume", "args": ["failed"]},
    )
    session.add(failed)
    await session.commit()

    assert await _requeue_rows(_make_sm(session), limit=100, dry_run=True) == 1

    await session.refresh(failed)
    assert failed.status == OutboxEventStatus.FAILED
    assert failed.dispatch_token == token
    assert failed.attempts == 10


@pytest.mark.integration
async def test_requeue_resets_failed_event_only(session: AsyncSession) -> None:
    failed = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.FAILED,
        attempts=10,
        last_error="broker down",
        locked_until=datetime.now(UTC) - timedelta(minutes=1),
        dispatch_token=uuid4(),
        payload={"task_name": "jobify.parse_resume", "args": ["failed"]},
    )
    completed = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.COMPLETED,
        payload={},
    )
    session.add_all([failed, completed])
    await session.commit()
    before = datetime.now(UTC)

    assert await _requeue_rows(_make_sm(session), limit=100, dry_run=False) == 1

    await session.refresh(failed)
    await session.refresh(completed)
    assert failed.status == OutboxEventStatus.PENDING
    assert failed.attempts == 0
    assert failed.last_error is None
    assert failed.locked_until is None
    assert failed.dispatch_token is None
    assert failed.available_at >= before
    assert completed.status == OutboxEventStatus.COMPLETED
