"""Pure-signature + redaction contract tests for the DSR builder. No DB."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from jobify_api.dsr import UserExport, _row_to_dict, build_user_export


def test_builder_signature() -> None:
    sig = inspect.signature(build_user_export)
    params = list(sig.parameters)
    assert params[0] == "session"
    assert sig.parameters["user"].kind == inspect.Parameter.KEYWORD_ONLY


def test_user_export_top_level_fields() -> None:
    fields = set(UserExport.model_fields.keys())
    expected = {
        "version",
        "exported_at",
        "exported_for_user_id",
        "user",
        "applicant",
        "applicant_preferences",
        "oauth_identities",
        "resumes",
        "applicant_embedding",
        "applications",
        "application_stage_events",
        "saved_jobs",
        "matches",
        "match_feedback",
        "notifications",
        "user_consents",
        "audit_history",
        "employer_memberships",
        "owned_jobs",
        "received_invites",
        "sent_invites",
        "redactions",
        "notes",
    }
    assert fields == expected, f"missing={expected - fields}, extra={fields - expected}"


def test_row_to_dict_drops_redacted_columns() -> None:
    """Defensive contract — any column on the explicit deny set OR matching
    one of the suffix patterns (`_secret`, `_password`) is dropped from the
    serialized row. Today the schema has zero such columns; this test pins
    the contract so a future MFA / password-auth column doesn't silently
    land in a DSR export."""
    row = SimpleNamespace(
        # Allowed columns
        id="some-id",
        email="user@example.com",
        # Explicit denylist hits
        totp_secret="DO_NOT_LEAK",
        recovery_codes=["DO_NOT_LEAK_1", "DO_NOT_LEAK_2"],
        access_token="DO_NOT_LEAK_OAUTH",
        refresh_token="DO_NOT_LEAK_REFRESH",
        password_hash="DO_NOT_LEAK_HASH",
        token_hash="DO_NOT_LEAK_REFRESH_HASH",
        # Suffix-pattern denylist hits — future-proofing
        webhook_signing_secret="DO_NOT_LEAK_WEBHOOK",
        api_key_password="DO_NOT_LEAK_PW",
    )
    result = _row_to_dict(row)

    # Allowed survives.
    assert result["id"] == "some-id"
    assert result["email"] == "user@example.com"

    # Denied columns absent.
    for forbidden in (
        "totp_secret",
        "recovery_codes",
        "access_token",
        "refresh_token",
        "password_hash",
        "token_hash",
        "webhook_signing_secret",
        "api_key_password",
    ):
        assert forbidden not in result, f"{forbidden} leaked into export"

    # And their values never appear anywhere in the serialized output.
    serialized = repr(result)
    assert "DO_NOT_LEAK" not in serialized
