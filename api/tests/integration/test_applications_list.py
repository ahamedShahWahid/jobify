"""Integration tests for GET /v1/applications and PATCH /v1/applications/{id}."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.tokens import mint_access_token
from jobify.db.models import (
    Applicant,
    Employer,
    Job,
    JobStatus,
    User,
    UserRole,
)

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


async def _make_applicant(
    session: AsyncSession, email: str = "applist@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="AppList Test", locations=["Bangalore"])
    session.add(applicant)
    await session.flush()
    return user, applicant


async def _make_job_and_employer(
    session: AsyncSession,
    *,
    title: str = "Engineer",
    employer_name: str = "Acme",
    status_value: JobStatus = JobStatus.OPEN,
) -> tuple[Job, Employer]:
    employer = Employer(name=employer_name, name_norm=employer_name.lower())
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title=title,
        description="x",
        locations=["Bangalore"],
        min_exp_years=1,
        max_exp_years=5,
        status=status_value,
    )
    session.add(job)
    await session.flush()
    return job, employer


def _token_headers(user: User) -> dict[str, str]:
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_list_empty_returns_empty_items(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="list-empty@example.com")
    await session.commit()

    resp = await async_client.get("/v1/applications", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


@pytest.mark.integration
async def test_list_returns_my_applications_only(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user_a, _ = await _make_applicant(session, email="list-mine-a@example.com")
    user_b, _ = await _make_applicant(session, email="list-mine-b@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="ListMineCo")
    job2, _ = await _make_job_and_employer(
        session, title="Other Job", employer_name="ListMineOtherCo"
    )
    await session.commit()

    # user_a applies to job; user_b applies to job2.
    ra = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=_token_headers(user_a))
    assert ra.status_code == 201
    rb = await async_client.post(f"/v1/jobs/{job2.id}/apply", headers=_token_headers(user_b))
    assert rb.status_code == 201

    # user_a sees only their own application.
    resp = await async_client.get("/v1/applications", headers=_token_headers(user_a))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["job"]["id"] == str(job.id)


@pytest.mark.integration
async def test_list_includes_withdrawn_in_history(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="list-hist@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="ListHistCo")
    await session.commit()

    headers = _token_headers(user)

    # Apply then withdraw.
    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201
    app_id = r1.json()["id"]

    r2 = await async_client.patch(
        f"/v1/applications/{app_id}",
        json={"status": "withdrawn"},
        headers=headers,
    )
    assert r2.status_code == 200

    # The withdrawn application must still appear in the list.
    resp = await async_client.get("/v1/applications", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["application"]["status"] == "withdrawn"


@pytest.mark.integration
async def test_list_pagination(session: AsyncSession, async_client: AsyncClient) -> None:
    user, _ = await _make_applicant(session, email="list-page@example.com")
    jobs = []
    for i in range(5):
        job, _ = await _make_job_and_employer(
            session, title=f"Job{i}", employer_name=f"ListPageCo{i}"
        )
        jobs.append(job)
    await session.commit()

    headers = _token_headers(user)
    for job in jobs:
        r = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
        assert r.status_code == 201

    # Page 1 — limit=2.
    resp1 = await async_client.get("/v1/applications?limit=2", headers=headers)
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    # Page 2.
    resp2 = await async_client.get(
        f"/v1/applications?limit=2&cursor={body1['next_cursor']}", headers=headers
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2["items"]) == 2
    assert body2["next_cursor"] is not None

    # Page 3 — last page.
    resp3 = await async_client.get(
        f"/v1/applications?limit=2&cursor={body2['next_cursor']}", headers=headers
    )
    assert resp3.status_code == 200
    body3 = resp3.json()
    assert len(body3["items"]) == 1
    assert body3["next_cursor"] is None

    # Ensure no duplicates across pages.
    all_ids = (
        [it["application"]["id"] for it in body1["items"]]
        + [it["application"]["id"] for it in body2["items"]]
        + [it["application"]["id"] for it in body3["items"]]
    )
    assert len(all_ids) == len(set(all_ids)) == 5


@pytest.mark.integration
async def test_list_etag_round_trip(session: AsyncSession, async_client: AsyncClient) -> None:
    user, _ = await _make_applicant(session, email="list-etag@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="ListEtagCo")
    await session.commit()

    headers = _token_headers(user)
    await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)

    r1 = await async_client.get("/v1/applications", headers=headers)
    assert r1.status_code == 200
    etag = r1.headers["ETag"]

    r2 = await async_client.get(
        "/v1/applications",
        headers={**headers, "If-None-Match": etag},
    )
    assert r2.status_code == 304
    assert r2.content == b""


@pytest.mark.integration
async def test_patch_withdraws_application_200(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="patch-withdraw@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="PatchWithdrawCo")
    await session.commit()

    headers = _token_headers(user)

    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201
    app_id = r1.json()["id"]

    r2 = await async_client.patch(
        f"/v1/applications/{app_id}",
        json={"status": "withdrawn"},
        headers=headers,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "withdrawn"
    assert body["id"] == app_id


@pytest.mark.integration
async def test_patch_re_withdraw_is_noop_200(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="patch-rewithdraw@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="PatchReWithdrawCo")
    await session.commit()

    headers = _token_headers(user)

    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    app_id = r1.json()["id"]

    # First withdrawal.
    r2 = await async_client.patch(
        f"/v1/applications/{app_id}",
        json={"status": "withdrawn"},
        headers=headers,
    )
    assert r2.status_code == 200

    # Second withdrawal — no-op, still 200.
    r3 = await async_client.patch(
        f"/v1/applications/{app_id}",
        json={"status": "withdrawn"},
        headers=headers,
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "withdrawn"


@pytest.mark.integration
async def test_patch_unknown_id_returns_404(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="patch-404@example.com")
    await session.commit()

    resp = await async_client.patch(
        f"/v1/applications/{uuid.uuid4()}",
        json={"status": "withdrawn"},
        headers=_token_headers(user),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "application_not_found"


@pytest.mark.integration
async def test_patch_other_users_application_returns_404(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user_a, _ = await _make_applicant(session, email="patch-other-a@example.com")
    user_b, _ = await _make_applicant(session, email="patch-other-b@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="PatchOtherCo")
    await session.commit()

    # user_a applies.
    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=_token_headers(user_a))
    assert r1.status_code == 201
    app_id = r1.json()["id"]

    # user_b tries to withdraw user_a's application → uniform 404.
    resp = await async_client.patch(
        f"/v1/applications/{app_id}",
        json={"status": "withdrawn"},
        headers=_token_headers(user_b),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "application_not_found"


@pytest.mark.integration
async def test_patch_invalid_transition_returns_400(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="patch-invalid@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="PatchInvalidCo")
    await session.commit()

    headers = _token_headers(user)

    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201
    app_id = r1.json()["id"]

    # Attempt to PATCH with status="applied" — invalid (not a recognised transition).
    resp = await async_client.patch(
        f"/v1/applications/{app_id}",
        json={"status": "applied"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_transition"
