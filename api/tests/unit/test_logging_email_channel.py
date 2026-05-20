"""Unit tests for LoggingEmailChannel.

Verifies that:
- ``send()`` returns ``ChannelResult`` with ``ok=True``.
- ``send()`` emits a structlog ``email.sent`` event with the expected fields.

These tests run without a DB or Redis connection (unit scope, no integration
marker).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
import structlog
import structlog.testing

from kpa.integrations.notifications.base import ChannelResult
from kpa.integrations.notifications.logging_email import LoggingEmailChannel


def _make_notification(
    *,
    kind: str = "application_received",
    payload: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """Build a minimal notification stand-in (no ORM required)."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        kind=kind,
        payload=payload or {"kind": kind, "job_id": str(uuid.uuid4())},
    )


@pytest.mark.asyncio
async def test_logging_email_channel_returns_success() -> None:
    """``send()`` always returns ``ChannelResult`` with ``ok=True``."""
    channel = LoggingEmailChannel()
    notif = _make_notification()

    result = await channel.send(notif, recipient="user@example.com")

    assert isinstance(result, ChannelResult)
    assert result.ok is True
    assert result.message == ""


@pytest.mark.asyncio
async def test_logging_email_channel_logs_payload() -> None:
    """``send()`` emits an ``email.sent`` structlog event with the right fields."""
    channel = LoggingEmailChannel()
    notif = _make_notification(
        kind="application_received",
        payload={"kind": "application_received", "job_id": "job-xyz"},
    )
    recipient = "applicant@example.com"

    with structlog.testing.capture_logs() as captured:
        await channel.send(notif, recipient=recipient)

    assert len(captured) == 1
    log_entry = captured[0]
    assert log_entry["event"] == "email.sent"
    assert log_entry["notification_id"] == str(notif.id)
    assert log_entry["kind"] == "application_received"
    assert log_entry["recipient"] == recipient
    assert log_entry["payload"] == notif.payload
