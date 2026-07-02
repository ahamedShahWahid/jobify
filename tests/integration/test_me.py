"""Integration tests for GET /v1/me + current_user end-to-end."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx
import jwt as pyjwt
import pytest
from sqlalchemy import select

from jobify.db.models import User
from jobify_api.auth.google_verifier import GoogleClaims

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


async def _signin(client: httpx.AsyncClient, google_verifier) -> dict:
    google_verifier.canned["tok"] = _claims()
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert resp.status_code == 200
    return resp.json()


async def test_me_returns_user_and_applicant(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]

    resp = await async_client.get("/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == signin["user"]["id"]
    assert body["email"] == "alice@example.com"
    assert body["role"] == "applicant"
    assert body["applicant"]["id"] == signin["user"]["applicant_id"]
    assert body["applicant"]["full_name"] == "Alice"
    assert body["applicant"]["notice_period_days"] is None


async def test_me_missing_bearer_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    resp = await async_client.get("/v1/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_bearer_token"


async def test_me_invalid_signature_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    # Token signed with the wrong secret.
    forged = pyjwt.encode(
        {
            "iss": "jobify-api",
            "sub": "11111111-1111-1111-1111-111111111111",
            "role": "applicant",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "jti": "00000000-0000-0000-0000-000000000000",
        },
        "wrong-secret-but-still-32-bytes-y",
        algorithm="HS256",
    )
    resp = await async_client.get("/v1/me", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_access_token"


async def test_me_expired_token_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    expired = pyjwt.encode(
        {
            "iss": "jobify-api",
            "sub": "11111111-1111-1111-1111-111111111111",
            "role": "applicant",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
            "jti": "00000000-0000-0000-0000-000000000000",
        },
        "x" * 32,
        algorithm="HS256",
    )
    resp = await async_client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_access_token"


async def test_me_deleted_user_returns_401(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]
    user_id = signin["user"]["id"]

    db_user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    db_user.deleted_at = datetime.now(UTC)
    await session.flush()

    resp = await async_client.get("/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "user_not_found"


async def test_me_tolerates_nullable_email_and_scrubbed_applicant_fields(
    async_client: httpx.AsyncClient, session
) -> None:
    """users.email and applicants.full_name are nullable (DSR scrubbing) —
    /v1/me must not 500 on a scrubbed row."""
    from jobify.db.models import Applicant, UserRole
    from jobify_api.auth.tokens import mint_access_token

    user = User(email=None, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name=None)
    session.add(applicant)
    await session.flush()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )

    resp = await async_client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] is None
    assert body["applicant"]["full_name"] is None
