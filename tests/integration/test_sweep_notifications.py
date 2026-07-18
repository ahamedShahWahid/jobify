"""Integration tests for the sweep_notifications task.

Exercises the outbox sweeper against a real Postgres 16 database using the
savepoint-based rollback isolation strategy shared with the rest of the
integration suite.

All tests call ``_sweep_notifications_async`` directly (the async body) rather
than going through the Celery task wrapper. This avoids the eager-mode
thread-hop and lets us inject the savepoint-bound sessionmaker and a fake
email channel.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
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

from jobify.db.models import (
    ConsentScope,
    Notification,
    NotificationChannel,
    NotificationStatus,
    User,
    UserConsent,
    UserRole,
)
from jobify.integrations.notifications.base import ChannelResult
from jobify_worker.tasks.sweep_notifications import (
    _sweep_notifications_async,
    _worker_settings,
)

pytestmark = pytest.mark.integration


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """Wrap the test's savepoint-bound session into a sessionmaker so the
    worker's _sweep_notifications_async sees the test's data.

    Mirrors the helper in test_score_applicant_worker.py.
    """
    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


async def _seed_user(session: AsyncSession, *, email: str = "u@example.com") -> User:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    return user


async def _seed_notification(
    session: AsyncSession,
    user: User,
    *,
    channel: NotificationChannel = NotificationChannel.EMAIL,
    status: NotificationStatus = NotificationStatus.PENDING,
    send_after: datetime | None = None,
    attempts: int = 0,
) -> Notification:
    n = Notification(
        user_id=user.id,
        kind="application_received",
        channel=channel,
        status=status,
        payload={"kind": "application_received"},
        attempts=attempts,
    )
    if send_after is not None:
        n.send_after = send_after
    session.add(n)
    await session.flush()
    return n


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_sweep_dispatches_pending_email(session: AsyncSession) -> None:
    """A pending EMAIL notification is claimed, dispatched, and marked SENT."""
    user = await _seed_user(session)
    n = await _seed_notification(session, user, channel=NotificationChannel.EMAIL)
    await session.commit()

    sm = _make_sm(session)
    # LoggingEmailChannel is the default; it always returns success.
    await _sweep_notifications_async(sm=sm, batch_size=10)

    # Reload from DB to see committed state.
    await session.refresh(n)
    assert n.status == NotificationStatus.SENT
    assert n.sent_at is not None
    assert n.last_error is None


@pytest.mark.integration
async def test_sweep_dispatches_pending_in_app(session: AsyncSession) -> None:
    """A pending IN_APP notification is marked SENT without calling the email channel."""
    user = await _seed_user(session, email="inapp@example.com")
    n = await _seed_notification(session, user, channel=NotificationChannel.IN_APP)
    await session.commit()

    sm = _make_sm(session)
    # Pass a mock channel that should never be called.
    never_called: AsyncMock = AsyncMock(spec=["send"])
    await _sweep_notifications_async(sm=sm, email_channel=never_called, batch_size=10)  # type: ignore[arg-type]

    never_called.send.assert_not_called()

    await session.refresh(n)
    assert n.status == NotificationStatus.SENT
    assert n.sent_at is not None


@pytest.mark.integration
async def test_sweep_skips_future_send_after(session: AsyncSession) -> None:
    """A notification whose send_after is in the future is not picked up."""
    user = await _seed_user(session, email="future@example.com")
    future = datetime.now(UTC) + timedelta(hours=1)
    n = await _seed_notification(session, user, send_after=future)
    await session.commit()

    sm = _make_sm(session)
    await _sweep_notifications_async(sm=sm, batch_size=10)

    await session.refresh(n)
    # Row must remain PENDING and untouched.
    assert n.status == NotificationStatus.PENDING


@pytest.mark.integration
async def test_sweep_skips_already_sent(session: AsyncSession) -> None:
    """A notification already in SENT status is not re-processed."""
    user = await _seed_user(session, email="sent@example.com")
    n = await _seed_notification(session, user, status=NotificationStatus.SENT)
    await session.commit()

    call_log: list[str] = []

    class _CountingChannel:
        async def send(self, notification: Notification, *, recipient: str) -> ChannelResult:
            call_log.append(str(notification.id))
            return ChannelResult.success()

    sm = _make_sm(session)
    await _sweep_notifications_async(sm=sm, email_channel=_CountingChannel(), batch_size=10)

    assert call_log == [], "SENT row should not be dispatched again"

    await session.refresh(n)
    assert n.status == NotificationStatus.SENT


@pytest.mark.integration
async def test_sweep_reclaims_expired_dispatch_lease(session: AsyncSession) -> None:
    """A worker crash after claim must not strand a notification forever."""
    user = await _seed_user(session, email="reclaim@example.com")
    n = await _seed_notification(
        session,
        user,
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.DISPATCHING,
        attempts=1,
    )
    n.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)

    await session.refresh(n)
    assert n.status == NotificationStatus.SENT
    assert n.attempts == 2
    assert n.dispatch_token is None
    assert n.locked_until is None


@pytest.mark.integration
async def test_sweep_does_not_steal_active_dispatch_lease(session: AsyncSession) -> None:
    user = await _seed_user(session, email="active-lease@example.com")
    n = await _seed_notification(
        session,
        user,
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.DISPATCHING,
        attempts=1,
    )
    n.locked_until = datetime.now(UTC) + timedelta(minutes=1)
    await session.commit()

    await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)

    await session.refresh(n)
    assert n.status == NotificationStatus.DISPATCHING
    assert n.attempts == 1


@pytest.mark.integration
async def test_sweep_retries_on_failed_channel(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed channel delivery increments attempts and reschedules with backoff.
    After 5 failures the row transitions to FAILED.
    """
    import jobify_worker.runtime as cel
    import jobify_worker.tasks.sweep_notifications as sweep_mod

    user = await _seed_user(session, email="retry@example.com")
    n = await _seed_notification(session, user, channel=NotificationChannel.EMAIL, attempts=0)
    await session.commit()

    class _FailingChannel:
        async def send(self, notification: Notification, *, recipient: str) -> ChannelResult:
            return ChannelResult.failed("simulated")

    failing = _FailingChannel()
    monkeypatch.setattr(cel, "get_email_channel", lambda: failing)
    monkeypatch.setattr(sweep_mod, "get_email_channel", lambda: failing)

    sm = _make_sm(session)

    # Run 4 times — each time reset send_after to now() so the sweeper picks it up,
    # then verify state after each pass.
    for expected_attempts in range(1, 5):
        # Reset send_after to the past so the sweeper can claim it again.
        n.send_after = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

        await _sweep_notifications_async(sm=sm, email_channel=failing, batch_size=10)
        await session.refresh(n)
        assert (
            n.status == NotificationStatus.PENDING
        ), f"Expected PENDING after attempt {expected_attempts}, got {n.status}"
        assert n.attempts == expected_attempts
        assert n.last_error == "simulated"
        assert n.send_after > datetime.now(UTC)

    # 5th failure: reset send_after then run again → FAILED.
    n.send_after = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    await _sweep_notifications_async(sm=sm, email_channel=failing, batch_size=10)
    await session.refresh(n)
    assert n.status == NotificationStatus.FAILED
    assert n.attempts == 5
    assert n.last_error == "simulated"


@pytest.mark.integration
async def test_sweep_batch_size_respected(session: AsyncSession) -> None:
    """With 100 pending notifications, only batch_size=10 are processed per call."""
    user = await _seed_user(session, email="batch@example.com")
    for _ in range(100):
        await _seed_notification(session, user, channel=NotificationChannel.IN_APP)
    await session.commit()

    sm = _make_sm(session)
    await _sweep_notifications_async(sm=sm, batch_size=10)

    # Reload all rows.
    rows = (
        (await session.execute(select(Notification).where(Notification.user_id == user.id)))
        .scalars()
        .all()
    )
    sent = [r for r in rows if r.status == NotificationStatus.SENT]
    pending = [r for r in rows if r.status == NotificationStatus.PENDING]
    assert len(sent) == 10
    assert len(pending) == 90


@pytest.mark.integration
async def test_slow_notification_claim_does_not_preclaim_later_rows(
    migrated_db: str,
) -> None:
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    notification_ids: list[UUID] = []
    user_id: UUID | None = None
    first_send_started = asyncio.Event()
    release_first_send = asyncio.Event()

    class _SlowFirstChannel:
        async def send(self, row: Notification, *, recipient: str) -> ChannelResult:
            if row.id == notification_ids[0]:
                first_send_started.set()
                await release_first_send.wait()
            return ChannelResult.success()

    try:
        async with sm() as seed:
            user = User(email=f"slow-{uuid4()}@example.com", role=UserRole.APPLICANT)
            seed.add(user)
            await seed.flush()
            user_id = user.id
            first = Notification(
                user_id=user.id,
                kind="application_received",
                channel=NotificationChannel.EMAIL,
                status=NotificationStatus.PENDING,
                send_after=datetime(2000, 1, 1, tzinfo=UTC),
                payload={},
            )
            second = Notification(
                user_id=user.id,
                kind="application_received",
                channel=NotificationChannel.EMAIL,
                status=NotificationStatus.PENDING,
                send_after=datetime(2000, 1, 2, tzinfo=UTC),
                payload={},
            )
            seed.add_all([first, second])
            await seed.commit()
            notification_ids = [first.id, second.id]

        async with sm() as isolation_session:
            async with isolation_session.begin():
                await isolation_session.execute(
                    select(Notification.id)
                    .where(Notification.id.not_in(notification_ids))
                    .with_for_update()
                )
                first_sweep = asyncio.create_task(
                    _sweep_notifications_async(
                        sm=sm,
                        email_channel=_SlowFirstChannel(),
                        batch_size=2,
                    )
                )
                await asyncio.wait_for(first_send_started.wait(), timeout=5)

                async with sm() as inspect_session:
                    later = await inspect_session.get(Notification, notification_ids[1])
                    assert later is not None
                    assert later.status == NotificationStatus.PENDING
                    assert later.dispatch_token is None
                    assert later.locked_until is None

                await _sweep_notifications_async(
                    sm=sm,
                    email_channel=_SlowFirstChannel(),
                    batch_size=1,
                )
                release_first_send.set()
                await asyncio.wait_for(first_sweep, timeout=5)

        async with sm() as verify:
            rows = list(
                (
                    await verify.execute(
                        select(Notification).where(Notification.id.in_(notification_ids))
                    )
                ).scalars()
            )
            assert {row.status for row in rows} == {NotificationStatus.SENT}
            assert {row.attempts for row in rows} == {1}
            assert all(row.dispatch_token is None and row.locked_until is None for row in rows)
    finally:
        release_first_send.set()
        if notification_ids or user_id is not None:
            async with sm() as cleanup:
                if notification_ids:
                    await cleanup.execute(
                        delete(Notification).where(Notification.id.in_(notification_ids))
                    )
                if user_id is not None:
                    await cleanup.execute(delete(User).where(User.id == user_id))
                await cleanup.commit()
        await engine.dispose()


@pytest.mark.integration
async def test_sweep_does_not_complete_stale_claim_after_dispatch(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, email="stale@example.com")
    notification = await _seed_notification(session, user)
    await session.commit()
    sm = _make_sm(session)

    class _TokenStealingChannel:
        async def send(self, row: Notification, *, recipient: str) -> ChannelResult:
            async with sm() as claim_session:
                current = await claim_session.get(Notification, row.id, with_for_update=True)
                assert current is not None
                current.dispatch_token = uuid4()
                current.locked_until = datetime.now(UTC) + timedelta(minutes=1)
                await claim_session.commit()
            return ChannelResult.success()

    await _sweep_notifications_async(
        sm=sm,
        email_channel=_TokenStealingChannel(),
        batch_size=10,
    )
    await session.refresh(notification)
    assert notification.status == NotificationStatus.DISPATCHING
    assert notification.sent_at is None


@pytest.mark.integration
async def test_sweep_cancels_when_transactional_email_consent_is_revoked(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, email="revoked@example.com")
    notification = await _seed_notification(session, user)
    session.add(
        UserConsent(
            user_id=user.id,
            scope=ConsentScope.EMAIL_TRANSACTIONAL.value,
            granted=False,
        )
    )
    await session.commit()
    await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)
    await session.refresh(notification)
    assert notification.status == NotificationStatus.CANCELLED
    assert notification.last_error == "consent_revoked:email_transactional"


@pytest.mark.integration
async def test_sweep_fails_when_recipient_email_is_missing(session: AsyncSession) -> None:
    user = User(email=None, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    notification = await _seed_notification(session, user)
    await session.commit()
    await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)
    await session.refresh(notification)
    assert notification.status == NotificationStatus.FAILED
    assert notification.last_error == "user_missing_or_no_email"


@pytest.mark.integration
async def test_sweep_logs_claim_exhaustion(session: AsyncSession) -> None:
    user = await _seed_user(session, email="exhausted@example.com")
    notification = await _seed_notification(
        session,
        user,
        status=NotificationStatus.DISPATCHING,
        attempts=_worker_settings.notify_max_attempts,
    )
    notification.dispatch_token = uuid4()
    notification.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    with capture_logs() as logs:
        await _sweep_notifications_async(sm=_make_sm(session), batch_size=10)
    assert any(row["event"] == "sweep.claim-exhausted" for row in logs)
