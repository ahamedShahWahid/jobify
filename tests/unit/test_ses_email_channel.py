from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import boto3
import pytest
from prometheus_client import REGISTRY

from jobify.integrations.notifications.ses import SesEmailChannel, _render


def _external_calls(service: str, operation: str, outcome: str) -> float:
    labels = {"service": service, "operation": operation, "outcome": outcome}
    return REGISTRY.get_sample_value("jobify_external_calls_total", labels) or 0.0


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
    before = _external_calls("ses", "send_email", "success")

    result = await channel.send(notification, recipient="user@example.com")

    assert result.ok
    request = client.send_email.call_args.kwargs
    assert request["FromEmailAddress"] == "notify@jobify.test"
    assert request["Destination"] == {"ToAddresses": ["user@example.com"]}
    assert "Engineer" in request["Content"]["Simple"]["Subject"]["Data"]
    assert _external_calls("ses", "send_email", "success") == before + 1


@pytest.mark.asyncio
async def test_ses_channel_returns_failure_for_provider_error() -> None:
    client = MagicMock()
    client.send_email.side_effect = RuntimeError("down")
    channel = SesEmailChannel(from_address="notify@jobify.test", client=client)
    notification = SimpleNamespace(kind="unknown", payload={})
    before = _external_calls("ses", "send_email", "error")

    result = await channel.send(notification, recipient="user@example.com")

    assert not result.ok
    assert result.message == "ses:RuntimeError"
    assert "down" not in result.message
    assert _external_calls("ses", "send_email", "error") == before + 1


_ALL_LOCALIZED_KINDS = ["application_received", "application_stage_changed"]


def test_render_hindi_all_kinds_and_stages() -> None:
    payload = {"job_title": "Flutter Developer", "employer_name": "Acme", "stage": "shortlisted"}
    for kind in _ALL_LOCALIZED_KINDS:
        subject, body = _render(kind, payload, "hi")
        assert any("ऀ" <= ch <= "ॿ" for ch in subject), kind
        assert any("ऀ" <= ch <= "ॿ" for ch in body), kind
        assert "Flutter Developer" in subject or "Flutter Developer" in body  # slots filled
        assert "{" not in subject and "{" not in body

    for stage in ["shortlisted", "interview", "offer", "hired", "rejected", "applied"]:
        subject, body = _render(
            "application_stage_changed",
            {"job_title": "T", "employer_name": "E", "stage": stage},
            "hi",
        )
        assert any("ऀ" <= ch <= "ॿ" for ch in body), stage


def test_render_unknown_kind_hindi_generic_fallback() -> None:
    subject, body = _render("some_future_kind", {}, "hi")
    assert any("ऀ" <= ch <= "ॿ" for ch in body)


def test_render_employer_invite_always_english() -> None:
    subject, body = _render("employer_invite", {"employer_name": "Acme", "role": "member"}, "hi")
    assert not any("ऀ" <= ch <= "ॿ" for ch in subject + body)


def test_render_default_language_is_english_unchanged() -> None:
    subject, _ = _render("application_received", {"job_title": "T", "employer_name": "E"})
    assert subject == "Application received — T"
