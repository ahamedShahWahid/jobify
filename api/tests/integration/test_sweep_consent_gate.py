"""Integration: revoke consent → next sweep marks pending row CANCELLED.

The sweep uses a savepoint-bound sessionmaker (via _make_sm) so all state
is visible across the test's session and the sweep's internal sessions.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.consent import seed_default_consents, set_consent
from jobify.db.models import (
    ConsentScope,
    Notification,
    NotificationChannel,
    NotificationStatus,
    User,
    UserRole,
)
from jobify.integrations.notifications.base import ChannelResult
from jobify.workers.tasks.sweep_notifications import _sweep_notifications_async
from tests.integration.test_sweep_notifications import (
    _make_sm,
    _seed_notification,
)


@pytest.mark.integration
async def test_revoked_email_consent_cancels_next_sweep(
    session: AsyncSession,
) -> None:
    user = User(email=f"sw-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    # Revoke email_transactional.
    await set_consent(
        session,
        user=user,
        scope=ConsentScope.EMAIL_TRANSACTIONAL,
        granted=False,
    )

    notif = await _seed_notification(
        session,
        user,
        channel=NotificationChannel.EMAIL,
    )
    await session.commit()  # commit savepoint so sweep's separate session sees it

    sm = _make_sm(session)

    # Inline a channel that fails the test if called — gate should preempt.
    class _NeverCalled:
        async def send(self, n: Notification, *, recipient: str) -> ChannelResult:
            raise AssertionError("channel must not be called when consent revoked")

    await _sweep_notifications_async(
        sm=sm,
        email_channel=_NeverCalled(),
        batch_size=10,  # type: ignore[arg-type]
    )

    await session.refresh(notif)
    assert notif.status == NotificationStatus.CANCELLED
    assert notif.cancelled_at is not None
    assert notif.last_error == "consent_revoked:email_transactional"


@pytest.mark.integration
async def test_revoked_in_app_consent_cancels_next_sweep(
    session: AsyncSession,
) -> None:
    user = User(email=f"sw-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    await set_consent(
        session,
        user=user,
        scope=ConsentScope.IN_APP_NOTIFICATIONS,
        granted=False,
    )

    notif = await _seed_notification(
        session,
        user,
        channel=NotificationChannel.IN_APP,
    )
    await session.commit()

    sm = _make_sm(session)

    class _NeverCalled:
        async def send(self, n: Notification, *, recipient: str) -> ChannelResult:
            raise AssertionError("channel must not be called when consent revoked")

    await _sweep_notifications_async(
        sm=sm,
        email_channel=_NeverCalled(),
        batch_size=10,  # type: ignore[arg-type]
    )

    await session.refresh(notif)
    assert notif.status == NotificationStatus.CANCELLED
    assert notif.cancelled_at is not None
    assert notif.last_error == "consent_revoked:in_app_notifications"


@pytest.mark.integration
async def test_no_consent_row_falls_back_to_default_grant(
    session: AsyncSession,
) -> None:
    """Pre-P4-B users have no consent rows. LookupError → fallback to DEFAULT_CONSENTS.

    EMAIL_TRANSACTIONAL defaults to True, so the sweep should still dispatch.
    This is the load-bearing pre-launch-safety invariant.
    """
    user = User(email=f"sw-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    # NO seed_default_consents call — simulates a pre-P4-B user.

    notif = await _seed_notification(
        session,
        user,
        channel=NotificationChannel.EMAIL,
    )
    await session.commit()

    sm = _make_sm(session)

    class _CountingChannel:
        sent: ClassVar[list[tuple[str, str]]] = []

        async def send(self, n: Notification, *, recipient: str) -> ChannelResult:
            type(self).sent.append((str(n.id), recipient))
            return ChannelResult.success()

    await _sweep_notifications_async(
        sm=sm,
        email_channel=_CountingChannel(),
        batch_size=10,  # type: ignore[arg-type]
    )

    await session.refresh(notif)
    # Default-fallback: email_transactional default is True → dispatch happened.
    assert notif.status == NotificationStatus.SENT
    assert len(_CountingChannel.sent) == 1
