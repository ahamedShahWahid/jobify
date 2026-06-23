"""Integration tests for POST /v1/auth/refresh — rotation + reuse detection."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from jobify.db.models import RefreshToken
from jobify_api.auth.google_verifier import GoogleClaims
from jobify_api.auth.tokens import sha256_token_hash

pytestmark = pytest.mark.integration


def _claims() -> GoogleClaims:
    return GoogleClaims(
        sub="google-sub-1",
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email="alice@example.com",
        email_verified=True,
        name="Alice",
    )


async def _sign_in(client: httpx.AsyncClient, google_verifier, token_tag: str = "tok") -> dict:
    google_verifier.canned[token_tag] = _claims()
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": token_tag})
    assert resp.status_code == 200
    return resp.json()


async def test_refresh_rotates_token(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    first = await _sign_in(async_client, google_verifier)
    refresh1 = first["refresh_token"]

    resp = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["refresh_token"] != refresh1

    # Old token row is revoked, replaced_by_id points at the new row.
    rows = (
        (await session.execute(select(RefreshToken).order_by(RefreshToken.issued_at)))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    old, new = rows
    assert old.revoked_at is not None
    assert old.revocation_reason == "rotated"
    assert old.replaced_by_id == new.id
    assert new.revoked_at is None
    assert old.family_id == new.family_id


async def test_refresh_reuse_revokes_whole_family(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    first = await _sign_in(async_client, google_verifier)
    refresh1 = first["refresh_token"]

    # First refresh: 200, token rotated.
    r1 = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1})
    assert r1.status_code == 200

    # Reuse the (now revoked) original token → 401 token_reused + family revoked.
    r2 = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1})
    assert r2.status_code == 401
    assert r2.json()["detail"] == "token_reused"

    # Both rows in the family are now revoked.
    rows = (await session.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)
    # The originally-rotated row keeps reason='rotated'; the legitimate successor
    # (T2) is revoked with 'reuse_detected' by _revoke_family.
    reasons = {r.revocation_reason for r in rows}
    assert reasons == {"rotated", "reuse_detected"}, reasons


async def test_refresh_unknown_token_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    resp = await async_client.post(
        "/v1/auth/refresh", json={"refresh_token": "definitely-not-real"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_refresh"


async def test_refresh_expired_token_returns_401(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    first = await _sign_in(async_client, google_verifier)
    refresh1 = first["refresh_token"]

    # Manually expire the row.
    row = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == sha256_token_hash(refresh1))
        )
    ).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.flush()

    resp = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "expired_refresh"


async def test_concurrent_refresh_race_has_exactly_one_winner(
    concurrent_async_client: httpx.AsyncClient, google_verifier
) -> None:
    first = await _sign_in(concurrent_async_client, google_verifier)
    refresh1 = first["refresh_token"]

    r1, r2 = await asyncio.gather(
        concurrent_async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1}),
        concurrent_async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1}),
    )

    statuses = sorted([r1.status_code, r2.status_code])
    # Exactly one winner: one 200 and one 401 token_reused.
    assert statuses == [200, 401]
    loser = r1 if r1.status_code == 401 else r2
    assert loser.json()["detail"] == "token_reused"
