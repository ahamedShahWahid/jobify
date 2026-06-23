"""Integration tests for POST /v1/auth/logout."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from jobify.db.models import RefreshToken
from jobify_api.auth.google_verifier import GoogleClaims
from jobify_api.auth.tokens import sha256_token_hash

pytestmark = pytest.mark.integration


def _claims(sub: str = "google-sub-1", email: str = "a@example.com") -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=True,
        name="A",
    )


async def test_logout_revokes_refresh_token(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    google_verifier.canned["tok"] = _claims()
    signin = await async_client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert signin.status_code == 200
    refresh = signin.json()["refresh_token"]

    resp = await async_client.post("/v1/auth/logout", json={"refresh_token": refresh})
    assert resp.status_code == 204
    assert resp.content == b""

    row = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == sha256_token_hash(refresh))
        )
    ).scalar_one()
    assert row.revoked_at is not None
    assert row.revocation_reason == "logout"


async def test_logout_then_refresh_returns_401(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    google_verifier.canned["tok"] = _claims()
    signin = await async_client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    refresh = signin.json()["refresh_token"]

    await async_client.post("/v1/auth/logout", json={"refresh_token": refresh})

    resp = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401
    # Logout sets revoked_at; replaying that token through refresh hits the
    # revoked-row branch and triggers reuse detection → token_reused.
    # (token_revoked is reserved for a future admin-revoke endpoint.)
    assert resp.json()["detail"] == "token_reused"


async def test_logout_unknown_token_returns_204(
    async_client: httpx.AsyncClient,
) -> None:
    resp = await async_client.post("/v1/auth/logout", json={"refresh_token": "no-such-token"})
    assert resp.status_code == 204
    assert resp.content == b""


async def test_logout_does_not_affect_other_users(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    google_verifier.canned["alice"] = _claims(sub="alice-sub", email="alice@example.com")
    google_verifier.canned["bob"] = _claims(sub="bob-sub", email="bob@example.com")

    alice = await async_client.post("/v1/auth/oauth/google", json={"id_token": "alice"})
    bob = await async_client.post("/v1/auth/oauth/google", json={"id_token": "bob"})
    assert alice.status_code == bob.status_code == 200
    alice_refresh = alice.json()["refresh_token"]
    bob_refresh = bob.json()["refresh_token"]

    # Alice logs out.
    await async_client.post("/v1/auth/logout", json={"refresh_token": alice_refresh})

    # Bob's refresh still works.
    resp = await async_client.post("/v1/auth/refresh", json={"refresh_token": bob_refresh})
    assert resp.status_code == 200
