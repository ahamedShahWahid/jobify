"""sweep_notifications task — claim pending notification rows and dispatch them.

The sweeper implements the outbox-pattern fan-out for the notifications table.
It is designed to be called on demand (or via Celery Beat when worker infra
hardens). Multiple concurrent sweeper instances are safe: ``SKIP LOCKED``
ensures disjoint batches.

State machine per row:
    pending -> dispatching -> sent      (success path)
    pending -> dispatching -> pending   (transient failure, attempts < 5)
    pending -> dispatching -> failed    (max attempts reached)

The task does NOT use Celery autoretry for the per-notification failures —
retries are handled inside _dispatch_one via the send_after backoff formula.
The broad except around _dispatch_one ensures one bad notification never
aborts the rest of the batch.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog
from sqlalchemy import or_, select
from sqlalchemy.sql import func

from jobify.consent import get_consent
from jobify.db.models import (
    DEFAULT_CONSENTS,
    ConsentScope,
    Notification,
    NotificationChannel,
    NotificationStatus,
    User,
)
from jobify.integrations.notifications.base import ChannelResult
from jobify_worker.async_bridge import run_async
from jobify_worker.celery_app import celery_app
from jobify_worker.celery_app import settings as _worker_settings
from jobify_worker.runtime import get_email_channel, get_session_maker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from jobify.integrations.notifications.base import EmailChannel

_log = structlog.get_logger(__name__)


def _scope_for_notification(n: Notification) -> ConsentScope:
    if n.channel == NotificationChannel.EMAIL:
        return ConsentScope.EMAIL_TRANSACTIONAL
    if n.channel == NotificationChannel.IN_APP:
        return ConsentScope.IN_APP_NOTIFICATIONS
    raise ValueError(f"unmapped channel: {n.channel}")


# --- Sync Celery entry point ---


@celery_app.task(  # type: ignore[untyped-decorator]
    name="jobify.sweep_notifications",
    bind=True,
    acks_late=True,
)
def sweep_notifications(self) -> None:  # type: ignore[no-untyped-def]
    """Sync entry. Wraps the async body in a fresh event loop.

    When invoked in eager mode from within a running event loop (e.g. during
    integration tests via httpx.AsyncClient), ``asyncio.run()`` would raise
    RuntimeError because a loop is already running. In that case we delegate
    to a fresh thread so the inner ``asyncio.run()`` gets a clean loop.
    """

    run_async(_sweep_notifications_async)


# --- Async body ---


async def _sweep_notifications_async(
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    email_channel: EmailChannel | None = None,
    batch_size: int | None = None,
) -> None:
    """Async body — claim a batch of pending notifications and dispatch each one.

    Production callers (the Celery task) pass nothing; this resolves the real
    sessionmaker, email channel, and batch size from settings.

    Tests inject ``sm`` (savepoint-bound sessionmaker), a fake ``email_channel``,
    and an explicit ``batch_size`` to avoid env-var monkeypatching.
    """
    sm = sm or get_session_maker()
    email_channel = email_channel or get_email_channel()
    effective_batch_size = (
        batch_size if batch_size is not None else _worker_settings.notify_batch_size
    )

    claims = await _claim_notifications(sm, batch_size=effective_batch_size)
    _log.info("sweep.batch-claimed", count=len(claims))

    # --- Per-notification dispatch (each in its own session) ---
    for notification_id, dispatch_token in claims:
        try:
            await _dispatch_one(
                session_maker=sm,
                email_channel=email_channel,
                notification_id=notification_id,
                dispatch_token=dispatch_token,
            )
        except Exception:
            # The lease makes this recoverable: a later sweep reclaims the row.
            _log.exception("sweep.dispatch-unexpected", notification_id=str(notification_id))


async def _claim_notifications(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    batch_size: int,
) -> list[tuple[UUID, UUID]]:
    """Lease due pending rows and reclaim expired dispatches.

    A per-claim token prevents a slow, stale worker from completing a row after
    another worker has reclaimed it. Attempts increment at claim time so repeated
    worker crashes eventually become terminal instead of looping forever.
    """
    now = datetime.now(UTC)
    lease_until = now + timedelta(seconds=_worker_settings.notify_lease_seconds)
    claims: list[tuple[UUID, UUID]] = []
    async with session_maker() as session:
        stmt = (
            select(Notification)
            .where(
                Notification.deleted_at.is_(None),
                or_(
                    (
                        (Notification.status == NotificationStatus.PENDING)
                        & (Notification.send_after <= now)
                    ),
                    (
                        (Notification.status == NotificationStatus.DISPATCHING)
                        & or_(
                            Notification.locked_until.is_(None),
                            Notification.locked_until < now,
                        )
                    ),
                ),
            )
            .order_by(Notification.send_after.asc(), Notification.id.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        rows = (await session.execute(stmt)).scalars().all()
        for notification in rows:
            if notification.attempts >= _worker_settings.notify_max_attempts:
                notification.status = NotificationStatus.FAILED
                notification.last_error = notification.last_error or "dispatch_lease_expired"
                notification.dispatch_token = None
                notification.locked_until = None
                continue
            token = uuid4()
            notification.status = NotificationStatus.DISPATCHING
            notification.attempts += 1
            notification.dispatch_token = token
            notification.locked_until = lease_until
            claims.append((notification.id, token))
        await session.commit()
    return claims


async def _dispatch_one(
    *,
    session_maker: async_sessionmaker[AsyncSession],
    email_channel: EmailChannel,
    notification_id: UUID,
    dispatch_token: UUID,
) -> None:
    """Load the notification row, call the channel adapter, and commit the new state.

    Opens a fresh session so failures are isolated to a single row. The caller
    wraps this in a broad except so one bad notification never aborts the batch.
    """
    # Resolve recipient and consent in a short DB transaction. The external
    # channel call happens only after this session closes, so a slow provider
    # cannot consume a database connection for the duration of network I/O.
    async with session_maker() as session:
        n = await session.get(Notification, notification_id, with_for_update=True)
        if n is None or n.deleted_at is not None:
            _log.warning("sweep.notification-missing", notification_id=str(notification_id))
            return
        if not _owns_claim(n, dispatch_token):
            _log.info("sweep.claim-lost", notification_id=str(notification_id))
            return

        # Resolve the recipient from users.email rather than trusting the payload.
        user = await session.get(User, n.user_id)
        if user is None or user.email is None:
            _log.error(
                "sweep.user-missing-or-no-email",
                notification_id=str(notification_id),
                user_id=str(n.user_id),
            )
            n.status = NotificationStatus.FAILED
            n.last_error = "user_missing_or_no_email"
            _clear_claim(n)
            await session.commit()
            return

        # --- Consent gate ---
        scope = _scope_for_notification(n)
        try:
            granted = await get_consent(session, user=user, scope=scope)
        except LookupError:
            # Backfill miss (pre-P4-B user, or DSR-delete cascade). The default
            # value is the safe behavior per spec §8.3.
            granted = DEFAULT_CONSENTS[scope]

        if not granted:
            n.status = NotificationStatus.CANCELLED
            n.cancelled_at = func.now()
            n.last_error = f"consent_revoked:{scope.value}"
            _clear_claim(n)
            _log.info(
                "sweep.cancelled-no-consent",
                notification_id=str(notification_id),
                user_id=str(user.id),
                scope=scope.value,
            )
            await session.commit()
            return

        channel = n.channel
        recipient = user.email

    # --- Channel dispatch (no open DB session) ---
    try:
        if channel == NotificationChannel.EMAIL:
            result: ChannelResult = await email_channel.send(n, recipient=recipient)
        elif channel == NotificationChannel.IN_APP:
            result = ChannelResult.success()
        else:
            result = ChannelResult.failed(f"unknown_channel:{channel}")
    except Exception as exc:
        result = ChannelResult.failed(f"{type(exc).__name__}:{exc}"[:1000])

    # --- State transition, guarded by the exact claim token ---
    async with session_maker() as session:
        n = await session.get(Notification, notification_id, with_for_update=True)
        if n is None or not _owns_claim(n, dispatch_token):
            _log.info("sweep.claim-lost-after-dispatch", notification_id=str(notification_id))
            return

        if result.ok:
            n.status = NotificationStatus.SENT
            n.sent_at = func.now()
            n.last_error = None
            _clear_claim(n)
            _log.info(
                "sweep.sent",
                notification_id=str(notification_id),
                channel=n.channel,
                kind=n.kind,
            )
        else:
            n.last_error = result.message
            if n.attempts >= _worker_settings.notify_max_attempts:
                n.status = NotificationStatus.FAILED
                _clear_claim(n)
                _log.warning(
                    "sweep.max-attempts-reached",
                    notification_id=str(notification_id),
                    attempts=n.attempts,
                    last_error=result.message,
                )
            else:
                n.status = NotificationStatus.PENDING
                delay = min(60 * (2 ** (n.attempts - 1)), 3600) + random.randint(0, 30)  # noqa: S311
                n.send_after = datetime.now(UTC) + timedelta(seconds=delay)
                _clear_claim(n)
                _log.info(
                    "sweep.retry-scheduled",
                    notification_id=str(notification_id),
                    attempts=n.attempts,
                    delay_seconds=delay,
                )

        await session.commit()


def _owns_claim(notification: Notification, dispatch_token: UUID) -> bool:
    return (
        notification.status == NotificationStatus.DISPATCHING
        and notification.dispatch_token == dispatch_token
    )


def _clear_claim(notification: Notification) -> None:
    notification.dispatch_token = None
    notification.locked_until = None
