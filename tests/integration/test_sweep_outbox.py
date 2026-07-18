from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jobify.db.models import OutboxEvent, OutboxEventKind, OutboxEventStatus
from jobify_worker.celery_app import settings
from jobify_worker.tasks.sweep_outbox import _sweep_outbox_async

pytestmark = pytest.mark.integration


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        return None

    async def read(self, key: str) -> bytes:
        return b""

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


@pytest.mark.asyncio
async def test_sweep_dispatches_task_and_completes_event(session: AsyncSession) -> None:
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()
    calls: list[tuple[str, list[object]]] = []

    await _sweep_outbox_async(
        sm=_make_sm(session),
        storage=FakeStorage(),
        dispatch=lambda name, args: calls.append((name, args)),
    )

    await session.refresh(event)
    assert ("jobify.parse_resume", ["id"]) in calls
    assert event.status == OutboxEventStatus.COMPLETED
    assert event.completed_at is not None


@pytest.mark.asyncio
async def test_sweep_deletes_blob_and_reclaims_expired_lease(session: AsyncSession) -> None:
    event = OutboxEvent(
        kind=OutboxEventKind.BLOB_DELETE,
        status=OutboxEventStatus.PROCESSING,
        locked_until=datetime.now(UTC) - timedelta(seconds=1),
        payload={"storage_key": "resumes/id.pdf"},
    )
    session.add(event)
    await session.commit()
    storage = FakeStorage()

    await _sweep_outbox_async(
        sm=_make_sm(session),
        storage=storage,
        dispatch=lambda _name, _args: None,
    )

    await session.refresh(event)
    assert storage.deleted == ["resumes/id.pdf"]
    assert event.status == OutboxEventStatus.COMPLETED


@pytest.mark.asyncio
async def test_sweep_retries_failed_event(session: AsyncSession) -> None:
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()

    def fail(_name: str, _args: list[object]) -> None:
        raise RuntimeError("broker down")

    await _sweep_outbox_async(sm=_make_sm(session), storage=FakeStorage(), dispatch=fail)

    await session.refresh(event)
    assert event.status == OutboxEventStatus.PENDING
    assert event.attempts == 1
    assert "broker down" in (event.last_error or "")


@pytest.mark.asyncio
async def test_sweep_terminally_fails_expired_lease_at_attempt_limit(
    session: AsyncSession,
) -> None:
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        attempts=settings.outbox_max_attempts,
        locked_until=datetime.now(UTC) - timedelta(seconds=1),
        payload={"task_name": "jobify.parse_resume", "args": ["terminal-event-id"]},
    )
    session.add(event)
    await session.commit()
    calls: list[tuple[str, list[object]]] = []

    await _sweep_outbox_async(
        sm=_make_sm(session),
        storage=FakeStorage(),
        dispatch=lambda name, args: calls.append((name, args)),
    )

    await session.refresh(event)
    assert ("jobify.parse_resume", ["terminal-event-id"]) not in calls
    assert event.status == OutboxEventStatus.FAILED
    assert event.attempts == settings.outbox_max_attempts
    assert event.locked_until is None
    assert event.last_error == "processing_lease_expired"
