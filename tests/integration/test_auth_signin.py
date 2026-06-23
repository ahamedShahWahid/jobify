"""Integration tests for POST /v1/auth/oauth/google."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from jobify.auth.google_verifier import GoogleClaims
from jobify.db.models import (
    DEFAULT_CONSENTS,
    Applicant,
    AuditLog,
    OAuthIdentity,
    OAuthProvider,
    RefreshToken,
    User,
    UserConsent,
)

pytestmark = pytest.mark.integration


def _claims(
    sub: str, email: str, name: str | None = "Test User", verified: bool = True
) -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=verified,
        name=name,
    )


async def test_signin_creates_user_applicant_and_identity(
    async_client: httpx.AsyncClient,
    google_verifier,
    session,
) -> None:
    google_verifier.canned["new_user_tok"] = _claims(
        sub="google-sub-new", email="new@example.com", name="New Person"
    )

    resp = await async_client.post("/v1/auth/oauth/google", json={"id_token": "new_user_tok"})

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"access_token", "refresh_token", "token_type", "expires_in", "user"}
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 600
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["role"] == "applicant"
    assert body["user"]["is_new_user"] is True
    assert isinstance(body["user"]["applicant_id"], str)
    user_id = uuid.UUID(body["user"]["id"])

    # DB side-effects
    db_user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    assert db_user.email == "new@example.com"

    db_applicant = (
        await session.execute(select(Applicant).where(Applicant.user_id == user_id))
    ).scalar_one()
    assert db_applicant.full_name == "New Person"

    db_identity = (
        await session.execute(select(OAuthIdentity).where(OAuthIdentity.user_id == user_id))
    ).scalar_one()
    assert db_identity.provider == OAuthProvider.GOOGLE
    assert db_identity.provider_subject == "google-sub-new"

    db_refresh = (
        await session.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    ).scalar_one()
    assert db_refresh.revoked_at is None

    # Default consents seeded in the same txn.
    consent_rows = (
        (await session.execute(select(UserConsent).where(UserConsent.user_id == user_id)))
        .scalars()
        .all()
    )
    assert len(consent_rows) == len(DEFAULT_CONSENTS)

    audit_rows = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user_id,
                    AuditLog.action == "consent.seeded",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == len(DEFAULT_CONSENTS)
    # Every seeded audit row carries the request_id from the sign-in HTTP call.
    assert all("request_id" in a.context for a in audit_rows)


async def test_signin_returning_user_updates_last_seen(
    async_client: httpx.AsyncClient,
    google_verifier,
    session,
) -> None:
    t0 = datetime.now(UTC)

    google_verifier.canned["alice_tok"] = _claims(
        sub="google-sub-alice", email="alice@example.com", name="Alice"
    )

    first = await async_client.post("/v1/auth/oauth/google", json={"id_token": "alice_tok"})
    assert first.status_code == 200
    user_id_1 = first.json()["user"]["id"]

    second = await async_client.post("/v1/auth/oauth/google", json={"id_token": "alice_tok"})
    assert second.status_code == 200
    body2 = second.json()
    assert body2["user"]["id"] == user_id_1
    assert body2["user"]["is_new_user"] is False

    # Only one user / applicant / identity scoped to this user.
    n_users = (await session.execute(select(User))).scalars().all()
    assert len(n_users) == 1
    n_idents = (
        (
            await session.execute(
                select(OAuthIdentity).where(OAuthIdentity.user_id == uuid.UUID(user_id_1))
            )
        )
        .scalars()
        .all()
    )
    assert len(n_idents) == 1
    # Two refresh tokens — one per sign-in — scoped to this user.
    n_refresh = (
        (
            await session.execute(
                select(RefreshToken).where(RefreshToken.user_id == uuid.UUID(user_id_1))
            )
        )
        .scalars()
        .all()
    )
    assert len(n_refresh) == 2

    # last_seen_at must have been updated by the second sign-in.
    db_ident = (
        await session.execute(
            select(OAuthIdentity).where(OAuthIdentity.user_id == uuid.UUID(user_id_1))
        )
    ).scalar_one()
    assert db_ident.last_seen_at is not None
    assert db_ident.last_seen_at >= t0


async def test_signin_rejects_invalid_google_token(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    # No canned tokens registered → fake raises InvalidGoogleTokenError.
    resp = await async_client.post("/v1/auth/oauth/google", json={"id_token": "garbage"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_google_token"


async def test_signin_email_collision_returns_409(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    # First Google account with email a@example.com lands successfully.
    google_verifier.canned["acct_a_tok"] = _claims(
        sub="google-sub-A", email="a@example.com", name="A"
    )
    first = await async_client.post("/v1/auth/oauth/google", json={"id_token": "acct_a_tok"})
    assert first.status_code == 200

    # A different Google sub but the same email → 409.
    google_verifier.canned["acct_b_tok"] = _claims(
        sub="google-sub-B", email="a@example.com", name="A doppelganger"
    )
    second = await async_client.post("/v1/auth/oauth/google", json={"id_token": "acct_b_tok"})
    assert second.status_code == 409
    assert second.json()["detail"] == "email_belongs_to_other_user"


async def test_signin_email_not_verified_blocked_when_required(
    async_client: httpx.AsyncClient,
    google_verifier,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When JOBIFY_AUTH_REQUIRE_EMAIL_VERIFIED=true, an unverified-email sign-in is rejected.

    Note: the env var is read at Settings() construction (app startup). Since the
    async_client fixture has already built the app with email_verified gate off,
    we have to override the live Settings object on app.state for this test.
    """
    settings = async_client._transport.app.state.settings  # type: ignore[attr-defined]
    monkeypatch.setattr(settings, "auth_require_email_verified", True)

    google_verifier.canned["unverified_tok"] = _claims(
        sub="g-unverified", email="unverified@example.com", verified=False
    )

    resp = await async_client.post("/v1/auth/oauth/google", json={"id_token": "unverified_tok"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "email_not_verified"
