from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import boto3
import pytest

from jobify.integrations.notifications.ses import SesEmailChannel


def test_ses_client_disables_sdk_retries_for_non_idempotent_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _client(service_name: str, **kwargs: object) -> MagicMock:
        captured["service_name"] = service_name
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(boto3, "client", _client)

    SesEmailChannel(
        from_address="notify@jobify.test",
        region="ap-south-1",
        connect_timeout_seconds=7.0,
        read_timeout_seconds=41.0,
    )

    config = captured["config"]
    assert captured["service_name"] == "sesv2"
    assert config.connect_timeout == 7.0
    assert config.read_timeout == 41.0
    assert config.retries == {"total_max_attempts": 1, "mode": "standard"}


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
