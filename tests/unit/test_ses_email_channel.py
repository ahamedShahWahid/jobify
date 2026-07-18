from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from jobify.integrations.notifications.ses import SesEmailChannel


@pytest.mark.asyncio
async def test_ses_channel_sends_application_email() -> None:
    client = MagicMock()
    channel = SesEmailChannel(from_address="notify@jobify.test", client=client)
    notification = SimpleNamespace(
        kind="application_received",
        payload={"job_title": "Engineer", "employer_name": "Acme"},
    )

    result = await channel.send(notification, recipient="user@example.com")

    assert result.ok
    request = client.send_email.call_args.kwargs
    assert request["FromEmailAddress"] == "notify@jobify.test"
    assert request["Destination"] == {"ToAddresses": ["user@example.com"]}
    assert "Engineer" in request["Content"]["Simple"]["Subject"]["Data"]


@pytest.mark.asyncio
async def test_ses_channel_returns_failure_for_provider_error() -> None:
    client = MagicMock()
    client.send_email.side_effect = RuntimeError("down")
    channel = SesEmailChannel(from_address="notify@jobify.test", client=client)
    notification = SimpleNamespace(kind="unknown", payload={})
    result = await channel.send(notification, recipient="user@example.com")
    assert not result.ok
    assert "RuntimeError" in result.message
