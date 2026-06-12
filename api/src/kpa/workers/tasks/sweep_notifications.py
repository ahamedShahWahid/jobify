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

import asyncio
import concurrent.futures
import random
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.sql import func

from kpa.consent import get_consent
from kpa.db.models import (
    DEFAULT_CONSENTS,
    ConsentScope,
    Notification,
    NotificationChannel,
    NotificationStatus,
    User,
)
from kpa.integrations.notifications.base import ChannelResult
from kpa.workers.celery_app import (
    celery_app,
    get_email_channel,
    get_session_maker,
)
from kpa.workers.celery_app import settings as _worker_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from kpa.integrations.notifications.base import EmailChannel

_log = structlog.get_logger(__name__)


def _scope_for_notification(n: Notification) -> ConsentScope:
    if n.channel == NotificationChannel.EMAIL:
        return ConsentScope.EMAIL_TRANSACTIONAL
    if n.channel == NotificationChannel.IN_APP:
        return ConsentScope.IN_APP_NOTIFICATIONS
    raise ValueError(f"unmapped channel: {n.channel}")


# --- Sync Celery entry point ---


@celery_app.task(  # type: ignore[untyped-decorator]
    name="kpa.sweep_notifications",
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

    def _run(coro_factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """Run a coroutine, dispatching to a thread if a loop is running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(asyncio.run, coro_factory())
                fut.result()
        else:
            asyncio.run(coro_factory())

    _run(lambda: _sweep_notifications_async())


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

    # --- Txn 1: claim a batch (SELECT FOR UPDATE SKIP LOCKED → set DISPATCHING) ---
    async with sm() as session:
        stmt = (
            select(Notification)
            .where(
                Notification.deleted_at.is_(None),
                Notification.status == NotificationStatus.PENDING,
                Notification.send_after <= func.now(),
            )
            .order_by(Notification.send_after.asc())
            .limit(effective_batch_size)
            .with_for_update(skip_locked=True)
        )
        rows = (await session.execute(stmt)).scalars().all()
        for n in rows:
            n.status = NotificationStatus.DISPATCHING
        await session.commit()

    _log.info("sweep.batch-claimed", count=len(rows))

    # --- Per-notification dispatch (each in its own session) ---
    for notification in rows:
        try:
            await _dispatch_one(
                session_maker=sm,
                email_channel=email_channel,
                notification_id=notification.id,
            )
        except Exception:
            _log.exception("sweep.dispatch-unexpected", notification_id=str(notification.id))


async def _dispatch_one(
    *,
    session_maker: async_sessionmaker[AsyncSession],
    email_channel: EmailChannel,
    notification_id: UUID,
) -> None:
    """Load the notification row, call the channel adapter, and commit the new state.

    Opens a fresh session so failures are isolated to a single row. The caller
    wraps this in a broad except so one bad notification never aborts the batch.
    """
    async with session_maker() as session:
        n = await session.get(Notification, notification_id)
        if n is None or n.deleted_at is not None:
            _log.warning("sweep.notification-missing", notification_id=str(notification_id))
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
            _log.info(
                "sweep.cancelled-no-consent",
                notification_id=str(notification_id),
                user_id=str(user.id),
                scope=scope.value,
            )
            await session.commit()
            return

        # --- Channel dispatch ---
        if n.channel == NotificationChannel.EMAIL:
            result: ChannelResult = await email_channel.send(n, recipient=user.email)
        elif n.channel == NotificationChannel.IN_APP:
            # In-app delivery is "the row exists" — mark sent immediately.
            result = ChannelResult.success()
        else:
            result = ChannelResult.failed(f"unknown_channel:{n.channel}")

        # --- State transition ---
        if result.ok:
            n.status = NotificationStatus.SENT
            n.sent_at = func.now()
            n.last_error = None
            _log.info(
                "sweep.sent",
                notification_id=str(notification_id),
                channel=n.channel,
                kind=n.kind,
            )
        else:
            n.attempts += 1
            n.last_error = result.message
            if n.attempts >= 5:
                n.status = NotificationStatus.FAILED
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
                _log.info(
                    "sweep.retry-scheduled",
                    notification_id=str(notification_id),
                    attempts=n.attempts,
                    delay_seconds=delay,
                )

        await session.commit()
