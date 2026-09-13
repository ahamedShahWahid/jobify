"""Integration tests for GET/PATCH /v1/applicants/me/preferences."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Applicant, ApplicantPreferences, User, UserRole
from jobify_api.auth.google_verifier import GoogleClaims
from jobify_api.auth.tokens import mint_access_token
from jobify_api.routes.applicants import _require_preferences_row
from tests.integration.outbox_helpers import task_event_args

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
    assert body == {
        "desired_role": None,
        "locations": [],
        "expected_ctc": None,
        "language": "en",
    }


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

    # And the reverse: a patch omitting locations leaves them untouched too.
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={"expected_ctc": 2000000},
    )
    assert resp.status_code == 200
    assert resp.json()["locations"] == ["Remote"]


@pytest.mark.parametrize(
    "body",
    [
        {"desired_role": "not_a_real_role"},
        {"locations": None},
        {"locations": [""]},
        {"locations": ["a"] * 11},
        {"locations": ["x" * 101]},
        {"expected_ctc": -5},
        {"expected_ctc": 10000000000},
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
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"locations": ["Pune"]}
    )
    assert resp.status_code == 200
    assert [signin["user"]["applicant_id"]] in await task_event_args(
        session, "jobify.score_applicant"
    )


async def test_patch_desired_role_only_no_rescore(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    before = len(await task_event_args(session, "jobify.score_applicant"))
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={"desired_role": "design"},
    )
    assert resp.status_code == 200
    assert len(await task_event_args(session, "jobify.score_applicant")) == before


async def test_patch_expected_ctc_explicit_null_clears_and_rescores(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"expected_ctc": 1200000}
    )
    assert resp.status_code == 200
    assert resp.json()["expected_ctc"] == "1200000.00"
    before = len(await task_event_args(session, "jobify.score_applicant"))

    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"expected_ctc": None}
    )
    assert resp.status_code == 200
    assert resp.json()["expected_ctc"] is None
    # Clearing a matching field is still a matching change → rescore.
    events = await task_event_args(session, "jobify.score_applicant")
    assert len(events) == before + 1
    assert events[-1] == [signin["user"]["applicant_id"]]


async def test_patch_desired_role_explicit_null_clears_no_rescore(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    before = len(await task_event_args(session, "jobify.score_applicant"))
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"desired_role": "design"}
    )
    assert resp.status_code == 200
    assert resp.json()["desired_role"] == "design"

    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"desired_role": None}
    )
    assert resp.status_code == 200
    assert resp.json()["desired_role"] is None
    assert len(await task_event_args(session, "jobify.score_applicant")) == before


async def test_patch_empty_body_is_noop(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={"desired_role": "design", "locations": ["Pune"], "expected_ctc": 500000},
    )
    assert resp.status_code == 200
    before = len(await task_event_args(session, "jobify.score_applicant"))

    resp = await async_client.patch("/v1/applicants/me/preferences", headers=headers, json={})
    assert resp.status_code == 200
    assert resp.json() == {
        "desired_role": "design",
        "locations": ["Pune"],
        "expected_ctc": "500000.00",
        "language": "en",
    }
    assert len(await task_event_args(session, "jobify.score_applicant")) == before


async def test_get_soft_deleted_preferences_row_returns_500(
    async_client: httpx.AsyncClient, google_verifier, session: AsyncSession
) -> None:
    """Mirrors test_upload_applicant_role_without_applicant_row_returns_500 —
    the eagerly-created row soft-deleted out-of-band is an invariant
    violation, surfaced as the pinned 500 slug (never auto-created)."""
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    row = (
        await session.execute(
            select(ApplicantPreferences).where(
                ApplicantPreferences.applicant_id == signin["user"]["applicant_id"]
            )
        )
    ).scalar_one()
    row.deleted_at = datetime.now(UTC)
    await session.commit()

    resp = await async_client.get("/v1/applicants/me/preferences", headers=headers)
    assert resp.status_code == 500
    assert resp.json()["detail"] == "applicant_preferences_missing"


async def _hard_delete_preferences_row(session: AsyncSession, applicant_id: str) -> None:
    """Simulate an applicant that predates migration 0021 (no row ever created)."""
    await session.execute(
        delete(ApplicantPreferences).where(ApplicantPreferences.applicant_id == applicant_id)
    )
    await session.commit()


async def _live_preferences_rows(session: AsyncSession, applicant_id: str) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(ApplicantPreferences)
            .where(
                ApplicantPreferences.applicant_id == applicant_id,
                ApplicantPreferences.deleted_at.is_(None),
            )
        )
    ).scalar_one()


async def test_get_preferences_creates_defaults_when_row_never_existed(
    async_client: httpx.AsyncClient, google_verifier, session: AsyncSession
) -> None:
    """Pre-0021 accounts have no preferences row at all (0021 did not backfill;
    0028 does). The route provisions the default row instead of 500ing."""
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    applicant_id = signin["user"]["applicant_id"]
    await _hard_delete_preferences_row(session, applicant_id)

    resp = await async_client.get("/v1/applicants/me/preferences", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "desired_role": None,
        "locations": [],
        "expected_ctc": None,
        "language": "en",
    }
    assert await _live_preferences_rows(session, applicant_id) == 1

    # A second read reuses the provisioned row rather than inserting another.
    resp = await async_client.get("/v1/applicants/me/preferences", headers=headers)
    assert resp.status_code == 200
    assert await _live_preferences_rows(session, applicant_id) == 1


async def test_patch_preferences_creates_row_when_row_never_existed(
    async_client: httpx.AsyncClient, google_verifier, session: AsyncSession
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    applicant_id = signin["user"]["applicant_id"]
    await _hard_delete_preferences_row(session, applicant_id)

    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"language": "hi"}
    )
    assert resp.status_code == 200
    assert resp.json()["language"] == "hi"
    assert await _live_preferences_rows(session, applicant_id) == 1


async def test_provisioning_skips_applicant_erased_after_auth_check(
    async_client: httpx.AsyncClient, google_verifier, session: AsyncSession
) -> None:
    """DSR erasure racing a preferences request: the request passed
    require_applicant, then the deleter committed (hard-deletes the prefs row,
    soft-deletes the applicant). Provisioning must not recreate a live row —
    PATCH would otherwise write location/CTC back for an erased applicant."""
    signin = await _signin(async_client, google_verifier)
    applicant_id = signin["user"]["applicant_id"]
    await _hard_delete_preferences_row(session, applicant_id)
    await session.execute(
        update(Applicant).where(Applicant.id == applicant_id).values(deleted_at=datetime.now(UTC))
    )
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await _require_preferences_row(UUID(applicant_id), session)
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "applicant_preferences_missing"
    assert await _live_preferences_rows(session, applicant_id) == 0


async def test_preferences_language_defaults_en_and_round_trips(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    resp = await async_client.get("/v1/applicants/me/preferences", headers=headers)
    assert resp.json()["language"] == "en"

    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"language": "hi"}
    )
    assert resp.status_code == 200
    assert resp.json()["language"] == "hi"

    resp = await async_client.get("/v1/applicants/me/preferences", headers=headers)
    assert resp.json()["language"] == "hi"


@pytest.mark.parametrize("body", [{"language": "fr"}, {"language": None}])
async def test_preferences_language_rejects_junk_and_null(
    async_client: httpx.AsyncClient, google_verifier, body
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch("/v1/applicants/me/preferences", headers=headers, json=body)
    assert resp.status_code == 422


async def test_language_change_stages_rescore_but_desired_role_does_not(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    """Language joins the rescore trigger set; desired_role stays capture-only."""
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    before = len(await task_event_args(session, "jobify.score_applicant"))

    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"language": "hi"}
    )
    assert resp.status_code == 200
    assert [signin["user"]["applicant_id"]] in await task_event_args(
        session, "jobify.score_applicant"
    )
    after_language = len(await task_event_args(session, "jobify.score_applicant"))
    assert after_language == before + 1

    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"desired_role": "design"}
    )
    assert resp.status_code == 200
    assert resp.json()["desired_role"] == "design"
    assert len(await task_event_args(session, "jobify.score_applicant")) == after_language


async def test_get_recruiter_returns_403(
    async_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    import uuid

    recruiter = User(email=f"recruiter-get-{uuid.uuid4()}@example.com", role=UserRole.RECRUITER)
    session.add(recruiter)
    await session.flush()
    access = mint_access_token(
        user_id=recruiter.id, role=recruiter.role.value, secret=_JWT_SECRET, ttl_seconds=600
    )
    resp = await async_client.get(
        "/v1/applicants/me/preferences",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"
