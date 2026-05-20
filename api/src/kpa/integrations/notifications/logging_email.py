"""Stub email channel that logs the would-be email payload via structlog.

Used for MVP / dev environments. Swap to ``SESEmailChannel`` when a deploy
target is picked and ``KPA_EMAIL_CHANNEL=ses`` is set.

No email is actually sent. Every call emits a structlog ``email.sent`` event
at INFO level with the notification id, kind, recipient, and payload so that
local development and integration tests can assert on the log record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from kpa.integrations.notifications.base import ChannelResult

if TYPE_CHECKING:
    from kpa.db.models import Notification

_log = structlog.get_logger(__name__)


class LoggingEmailChannel:
    """Stub email channel implementing the ``EmailChannel`` Protocol.

    Satisfies ``EmailChannel`` structurally — no explicit inheritance needed.
    """

    async def send(
        self,
        notification: Notification,
        *,
        recipient: str,
    ) -> ChannelResult:
        """Log the would-be email and return success.

        Args:
            notification: The ``Notification`` ORM row.
            recipient: The resolved recipient email address.

        Returns:
            Always ``ChannelResult.success()``.
        """
        _log.info(
            "email.sent",
            notification_id=str(notification.id),
            kind=notification.kind,
            recipient=recipient,
            payload=notification.payload,
        )
        return ChannelResult.success()
