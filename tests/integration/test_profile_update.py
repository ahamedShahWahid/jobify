"""Integration tests for PATCH /v1/applicants/me."""

from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Applicant, User, UserRole
from jobify_api.auth.google_verifier import GoogleClaims
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


def _claims() -> GoogleClaims:
    return GoogleClaims(
        sub="google-sub-profile",
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


async def test_patch_partial_update(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]

    resp = await async_client.patch(
        "/v1/applicants/me",
        headers={"Authorization": f"Bearer {access}"},
        json={"years_experience": 4.5, "current_ctc": 1200000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicant"]["years_experience"] == "4.5"
    assert body["applicant"]["current_ctc"] == "1200000.00"
    assert body["applicant"]["full_name"] == "Alice"

    row = (
        await session.execute(select(Applicant).where(Applicant.user_id == signin["user"]["id"]))
    ).scalar_one()
    assert row.years_experience == Decimal("4.5")


async def test_patch_explicit_null_clears_nullable(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    await async_client.patch("/v1/applicants/me", headers=headers, json={"notice_period_days": 30})
    resp = await async_client.patch(
        "/v1/applicants/me", headers=headers, json={"notice_period_days": None}
    )
    assert resp.status_code == 200
    assert resp.json()["applicant"]["notice_period_days"] is None


async def test_patch_omitted_key_unchanged(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    await async_client.patch("/v1/applicants/me", headers=headers, json={"notice_period_days": 45})
    resp = await async_client.patch(
        "/v1/applicants/me", headers=headers, json={"years_experience": 3}
    )
    assert resp.status_code == 200
    assert resp.json()["applicant"]["notice_period_days"] == 45


@pytest.mark.parametrize(
    "body",
    [
        {"full_name": ""},
        {"full_name": "x" * 201},
        {"full_name": None},
        {"notice_period_days": -1},
        {"notice_period_days": 400},
        {"current_ctc": -5},
        {"years_experience": 61},
        {"unknown_field": "x"},
    ],
)
async def test_patch_validation_422(async_client: httpx.AsyncClient, google_verifier, body) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch("/v1/applicants/me", headers=headers, json=body)
    assert resp.status_code == 422


async def test_patch_recruiter_returns_403(
    async_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    recruiter = User(
        email=f"recruiter-{uuid.uuid4()}@example.com",
        role=UserRole.RECRUITER,
    )
    session.add(recruiter)
    await session.flush()

    access = mint_access_token(
        user_id=recruiter.id,
        role=recruiter.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )

    resp = await async_client.patch(
        "/v1/applicants/me",
        headers={"Authorization": f"Bearer {access}"},
        json={"notice_period_days": 30},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"


async def test_patch_matching_field_dispatches_rescore(
    async_client: httpx.AsyncClient, google_verifier, monkeypatch
) -> None:
    import jobify.celery_app as _celery_mod

    calls: list[str] = []

    def _spy_enqueue(name: str, *args: object) -> None:
        if name == "jobify.score_applicant":
            calls.extend(args)

    monkeypatch.setattr(_celery_mod, "enqueue", _spy_enqueue)

    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    resp = await async_client.patch(
        "/v1/applicants/me", headers=headers, json={"years_experience": 3}
    )
    assert resp.status_code == 200
    assert calls == [signin["user"]["applicant_id"]]


async def test_patch_non_matching_field_no_rescore(
    async_client: httpx.AsyncClient, google_verifier, monkeypatch
) -> None:
    import jobify.celery_app as _celery_mod

    calls: list[str] = []

    def _spy_enqueue(name: str, *args: object) -> None:
        if name == "jobify.score_applicant":
            calls.extend(args)

    monkeypatch.setattr(_celery_mod, "enqueue", _spy_enqueue)

    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    # notice_period_days is informational — no matching impact.
    resp = await async_client.patch(
        "/v1/applicants/me", headers=headers, json={"notice_period_days": 30}
    )
    assert resp.status_code == 200
    assert calls == []
