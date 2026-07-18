from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from structlog.testing import capture_logs

from jobify.db.models import OutboxEvent, OutboxEventKind, OutboxEventStatus
from jobify_worker.celery_app import settings
from jobify_worker.tasks.sweep_outbox import (
    _claim,
    _complete,
    _record_failure,
    _sweep_outbox_async,
)

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


@pytest.mark.parametrize(
    "locked_until",
    [None, datetime(2000, 1, 1, tzinfo=UTC)],
    ids=["null-lock", "expired-lock"],
)
@pytest.mark.asyncio
async def test_claim_reclaims_processing_event_with_future_available_at(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    locked_until: datetime | None,
) -> None:
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        available_at=datetime.now(UTC) + timedelta(days=1),
        locked_until=locked_until,
        created_at=datetime(1990, 1, 1, tzinfo=UTC),
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()
    monkeypatch.setattr(settings, "outbox_batch_size", 1)

    claims = await _claim(_make_sm(session))

    await session.refresh(event)
    assert event.dispatch_token is not None
    assert claims == [(event.id, event.dispatch_token)]


@pytest.mark.asyncio
async def test_stale_token_cannot_complete_or_reschedule_reclaimed_event(
    session: AsyncSession,
) -> None:
    stale = uuid4()
    current = uuid4()
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        dispatch_token=current,
        locked_until=datetime.now(UTC) + timedelta(minutes=1),
        attempts=2,
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()

    await _complete(_make_sm(session), event.id, stale)
    await _record_failure(_make_sm(session), event.id, stale, RuntimeError("late"))

    await session.refresh(event)
    assert event.status == OutboxEventStatus.PROCESSING
    assert event.dispatch_token == current
    assert event.last_error is None


@pytest.mark.asyncio
async def test_record_failure_marks_event_failed_at_attempt_limit(
    session: AsyncSession,
) -> None:
    token = uuid4()
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        dispatch_token=token,
        locked_until=datetime.now(UTC) + timedelta(minutes=1),
        attempts=settings.outbox_max_attempts,
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()

    await _record_failure(_make_sm(session), event.id, token, RuntimeError("poison"))

    await session.refresh(event)
    assert event.status == OutboxEventStatus.FAILED
    assert event.dispatch_token is None
    assert event.locked_until is None


@pytest.mark.asyncio
async def test_record_failure_schedules_retry_with_backoff(
    session: AsyncSession,
) -> None:
    token = uuid4()
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        dispatch_token=token,
        locked_until=datetime.now(UTC) + timedelta(minutes=1),
        attempts=1,
        payload={"task_name": "jobify.parse_resume", "args": ["id"]},
    )
    session.add(event)
    await session.commit()
    before = datetime.now(UTC)

    await _record_failure(_make_sm(session), event.id, token, RuntimeError("broker"))

    await session.refresh(event)
    assert event.status == OutboxEventStatus.PENDING
    assert event.available_at > before
    assert event.dispatch_token is None
    assert event.locked_until is None


@pytest.mark.asyncio
async def test_sweep_isolates_failed_event_from_rest_of_batch(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poison = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
        payload={"task_name": "jobify.parse_resume", "args": ["poison"]},
    )
    healthy = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        created_at=datetime(2000, 1, 2, tzinfo=UTC),
        payload={"task_name": "jobify.parse_resume", "args": ["healthy"]},
    )
    session.add_all([poison, healthy])
    await session.commit()
    monkeypatch.setattr(settings, "outbox_batch_size", 2)

    def dispatch(_name: str, args: list[object]) -> None:
        if args == ["poison"]:
            raise RuntimeError("poison")

    await _sweep_outbox_async(
        sm=_make_sm(session),
        storage=FakeStorage(),
        dispatch=dispatch,
    )

    await session.refresh(poison)
    await session.refresh(healthy)
    assert poison.status == OutboxEventStatus.PENDING
    assert poison.dispatch_token is None
    assert healthy.status == OutboxEventStatus.COMPLETED
    assert healthy.dispatch_token is None


@pytest.mark.asyncio
async def test_claim_exhaustion_is_logged_without_payload(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        status=OutboxEventStatus.PROCESSING,
        dispatch_token=uuid4(),
        attempts=settings.outbox_max_attempts,
        locked_until=datetime.now(UTC) - timedelta(seconds=1),
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
        payload={
            "task_name": "jobify.parse_resume",
            "args": ["sensitive-task-argument"],
        },
    )
    session.add(event)
    await session.commit()
    monkeypatch.setattr(settings, "outbox_batch_size", 1)

    with capture_logs() as logs:
        await _sweep_outbox_async(
            sm=_make_sm(session),
            storage=FakeStorage(),
            dispatch=lambda _name, _args: None,
        )

    await session.refresh(event)
    exhausted_logs = [row for row in logs if row["event"] == "outbox.claim-exhausted"]
    assert len(exhausted_logs) == 1
    assert "sensitive-task-argument" not in str(exhausted_logs[0])
    assert event.status == OutboxEventStatus.FAILED
    assert event.dispatch_token is None
    assert event.locked_until is None


@pytest.mark.integration
async def test_concurrent_claimers_claim_event_once(
    migrated_db: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    event_id: UUID | None = None
    first_selected = asyncio.Event()
    second_selected = asyncio.Event()
    sequence_lock = asyncio.Lock()
    execute_count = 0

    class CoordinatedClaimSession(AsyncSession):
        async def execute(self, *args: Any, **kwargs: Any) -> Any:
            nonlocal execute_count
            async with sequence_lock:
                execute_count += 1
                sequence = execute_count

            if sequence == 2:
                await first_selected.wait()

            result = await super().execute(*args, **kwargs)
            if sequence == 1:
                first_selected.set()
                await second_selected.wait()
            elif sequence == 2:
                second_selected.set()
            return result

    claim_sm = async_sessionmaker(
        engine,
        class_=CoordinatedClaimSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(settings, "outbox_batch_size", 1)
    try:
        async with sm() as seed_session:
            event = OutboxEvent(
                kind=OutboxEventKind.TASK_DISPATCH,
                created_at=datetime(2000, 1, 1, tzinfo=UTC),
                payload={
                    "task_name": "jobify.parse_resume",
                    "args": ["concurrent"],
                },
            )
            seed_session.add(event)
            await seed_session.commit()
            event_id = event.id

        # Keep unrelated rows locked on a third connection so SKIP LOCKED
        # exercises only this test's event even when the local test database
        # contains data left by an interrupted run.
        async with sm() as isolation_session:
            async with isolation_session.begin():
                await isolation_session.execute(
                    select(OutboxEvent.id).where(OutboxEvent.id != event_id).with_for_update()
                )
                async with asyncio.timeout(5):
                    first, second = await asyncio.gather(
                        _claim(claim_sm),
                        _claim(claim_sm),
                    )

        claims = first + second
        assert first_selected.is_set()
        assert second_selected.is_set()
        assert execute_count == 2
        assert len(claims) == 1
        assert claims[0][0] == event_id
    finally:
        if event_id is not None:
            async with sm() as cleanup_session:
                await cleanup_session.execute(delete(OutboxEvent).where(OutboxEvent.id == event_id))
                await cleanup_session.commit()
        await engine.dispose()


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
