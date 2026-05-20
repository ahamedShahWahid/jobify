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

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kpa.db.models import Notification, NotificationChannel, NotificationStatus, User, UserRole
from kpa.integrations.notifications.base import ChannelResult
from kpa.workers.tasks.sweep_notifications import _sweep_notifications_async


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
async def test_sweep_retries_on_failed_channel(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed channel delivery increments attempts and reschedules with backoff.
    After 5 failures the row transitions to FAILED.
    """
    import kpa.workers.celery_app as cel
    import kpa.workers.tasks.sweep_notifications as sweep_mod

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
