"""Integration tests for GET/PATCH /v1/applicants/me/preferences."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import ApplicantPreferences, User, UserRole
from jobify_api.auth.google_verifier import GoogleClaims
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32


def _claims() -> GoogleClaims:
    return GoogleClaims(
        sub="google-sub-prefs",
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email="prefs@example.com",
        email_verified=True,
        name="Prefs Test",
    )


async def _signin(client: httpx.AsyncClient, google_verifier) -> dict:
    google_verifier.canned["tok"] = _claims()
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert resp.status_code == 200
    return resp.json()


async def test_get_preferences_defaults_empty(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.get("/v1/applicants/me/preferences", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"desired_role": None, "locations": [], "expected_ctc": None}


async def test_patch_partial_update(
    async_client: httpx.AsyncClient, google_verifier, session: AsyncSession
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={
            "desired_role": "software_engineering",
            "locations": ["Pune", "Bengaluru"],
            "expected_ctc": 1800000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["desired_role"] == "software_engineering"
    assert body["locations"] == ["Pune", "Bengaluru"]
    assert body["expected_ctc"] == "1800000.00"

    row = (
        await session.execute(
            select(ApplicantPreferences).where(
                ApplicantPreferences.applicant_id == signin["user"]["applicant_id"]
            )
        )
    ).scalar_one()
    assert row.locations == ["Pune", "Bengaluru"]


async def test_patch_omitted_key_unchanged(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"expected_ctc": 1000000}
    )
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={"locations": ["Remote"]},
    )
    assert resp.status_code == 200
    assert resp.json()["expected_ctc"] == "1000000.00"


@pytest.mark.parametrize(
    "body",
    [
        {"desired_role": "not_a_real_role"},
        {"locations": None},
        {"locations": [""]},
        {"locations": ["a"] * 11},
        {"expected_ctc": -5},
        {"unknown_field": "x"},
    ],
)
async def test_patch_validation_422(async_client: httpx.AsyncClient, google_verifier, body) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch("/v1/applicants/me/preferences", headers=headers, json=body)
    assert resp.status_code == 422


async def test_patch_recruiter_returns_403(
    async_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    import uuid

    recruiter = User(email=f"recruiter-{uuid.uuid4()}@example.com", role=UserRole.RECRUITER)
    session.add(recruiter)
    await session.flush()
    access = mint_access_token(
        user_id=recruiter.id, role=recruiter.role.value, secret=_JWT_SECRET, ttl_seconds=600
    )
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers={"Authorization": f"Bearer {access}"},
        json={"expected_ctc": 1000000},
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
        "/v1/applicants/me/preferences", headers=headers, json={"locations": ["Pune"]}
    )
    assert resp.status_code == 200
    assert calls == [signin["user"]["applicant_id"]]


async def test_patch_desired_role_only_no_rescore(
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
        "/v1/applicants/me/preferences",
        headers=headers,
        json={"desired_role": "design"},
    )
    assert resp.status_code == 200
    assert calls == []  # desired_role is capture-only, not a matching field
