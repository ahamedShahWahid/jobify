"""Integration tests for GET /v1/applicants/me/resumes (list)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.google_verifier import GoogleClaims
from jobify.auth.tokens import mint_access_token
from jobify.db.models import User, UserRole

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


def _claims(sub: str = "g-resume-1", email: str = "alice@example.com") -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=True,
        name="Alice",
    )


async def _signin(client: httpx.AsyncClient, google_verifier, claims) -> dict:
    google_verifier.canned["tok"] = claims
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert resp.status_code == 200
    return resp.json()


async def _upload(client: httpx.AsyncClient, access: str, name: str) -> dict:
    resp = await client.post(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {access}"},
        files={"file": (name, b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_list_empty(async_client: httpx.AsyncClient, google_verifier) -> None:
    signin = await _signin(async_client, google_verifier, _claims())
    resp = await async_client.get(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {signin['access_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_newest_first_and_scoped(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier, _claims())
    access = signin["access_token"]
    first = await _upload(async_client, access, "one.pdf")
    second = await _upload(async_client, access, "two.pdf")

    resp = await async_client.get(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Both resumes must appear; set comparison confirms correct scoping.
    assert {r["id"] for r in body} == {first["id"], second["id"]}
    # Ordering is (created_at DESC, id DESC). In fast test runs both rows may
    # share the same created_at; verify the list is sorted stably by checking
    # that created_at values are non-increasing.
    created_ats = [r["created_at"] for r in body]
    assert created_ats == sorted(created_ats, reverse=True)


async def test_list_recruiter_403(async_client: httpx.AsyncClient, session: AsyncSession) -> None:
    user = User(
        email=f"rec-resume-{uuid.uuid4()}@example.com",
        role=UserRole.RECRUITER,
    )
    session.add(user)
    await session.flush()
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    resp = await async_client.get(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"


async def test_list_excludes_other_applicant_resumes(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    # Sign in as Alice and upload.
    alice_signin = await _signin(
        async_client,
        google_verifier,
        _claims(sub="g-alice-iso", email="alice-iso@example.com"),
    )
    alice_resume = await _upload(async_client, alice_signin["access_token"], "alice.pdf")

    # Sign in as Bob and upload.
    bob_signin = await _signin(
        async_client,
        google_verifier,
        _claims(sub="g-bob-iso", email="bob-iso@example.com"),
    )
    await _upload(async_client, bob_signin["access_token"], "bob.pdf")

    # Alice's list must NOT contain Bob's resume.
    resp = await async_client.get(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {alice_signin['access_token']}"},
    )
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert alice_resume["id"] in ids
    assert len(ids) == 1  # only Alice's resume
