"""Integration tests for POST/DELETE /v1/jobs/{id}/save and GET /v1/saved."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
    session: AsyncSession, email: str = "save@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Save Test", locations=["Bangalore"])
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
async def test_save_creates_saved_job_201(session: AsyncSession, async_client: AsyncClient) -> None:
    user, _ = await _make_applicant(session, email="save-201@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="Save201Co")
    await session.commit()

    resp = await async_client.post(
        f"/v1/jobs/{job.id}/save",
        headers=_token_headers(user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["job_id"] == str(job.id)
    assert "id" in body
    assert "created_at" in body


@pytest.mark.integration
async def test_save_idempotent_returns_existing_200(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="save-idem@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="SaveIdemCo")
    await session.commit()

    headers = _token_headers(user)

    r1 = await async_client.post(f"/v1/jobs/{job.id}/save", headers=headers)
    assert r1.status_code == 201
    first_id = r1.json()["id"]

    r2 = await async_client.post(f"/v1/jobs/{job.id}/save", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == first_id


@pytest.mark.integration
async def test_unsave_soft_deletes_row_204(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="unsave-204@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="Unsave204Co")
    await session.commit()

    headers = _token_headers(user)

    # Save first.
    r1 = await async_client.post(f"/v1/jobs/{job.id}/save", headers=headers)
    assert r1.status_code == 201

    # Unsave.
    r2 = await async_client.delete(f"/v1/jobs/{job.id}/save", headers=headers)
    assert r2.status_code == 204
    assert r2.content == b""

    # Confirm no longer visible in the saved list.
    resp = await async_client.get("/v1/saved", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.integration
async def test_unsave_when_not_saved_returns_204(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Unsave of a non-existent save is a no-op — still 204."""
    user, _ = await _make_applicant(session, email="unsave-noop@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="UnsaveNoopCo")
    await session.commit()

    resp = await async_client.delete(
        f"/v1/jobs/{job.id}/save",
        headers=_token_headers(user),
    )
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.integration
async def test_re_save_after_unsave_creates_new_row_201(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Re-saving after unsave creates a fresh row with a different id."""
    user, _ = await _make_applicant(session, email="save-resave@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="SaveResaveCo")
    await session.commit()

    headers = _token_headers(user)

    # Save → unsave → save again.
    r1 = await async_client.post(f"/v1/jobs/{job.id}/save", headers=headers)
    assert r1.status_code == 201
    first_id = r1.json()["id"]

    r2 = await async_client.delete(f"/v1/jobs/{job.id}/save", headers=headers)
    assert r2.status_code == 204

    r3 = await async_client.post(f"/v1/jobs/{job.id}/save", headers=headers)
    assert r3.status_code == 201
    # Spec Decision #3: re-save after unsave creates a fresh row.
    assert r3.json()["id"] != first_id


@pytest.mark.integration
async def test_save_404_for_closed_or_missing_job(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="save-404@example.com")
    closed_job, _ = await _make_job_and_employer(
        session,
        employer_name="Save404ClosedCo",
        status_value=JobStatus.CLOSED,
    )
    soft_deleted_job, _ = await _make_job_and_employer(session, employer_name="Save404SoftDelCo")
    soft_deleted_job.deleted_at = datetime.now(UTC)
    await session.commit()

    headers = _token_headers(user)
    unknown_id = uuid.uuid4()

    # Unknown job.
    r1 = await async_client.post(f"/v1/jobs/{unknown_id}/save", headers=headers)
    assert r1.status_code == 404
    assert r1.json()["detail"] == "job_not_found"

    # Closed job.
    r2 = await async_client.post(f"/v1/jobs/{closed_job.id}/save", headers=headers)
    assert r2.status_code == 404
    assert r2.json()["detail"] == "job_not_found"

    # Soft-deleted job.
    r3 = await async_client.post(f"/v1/jobs/{soft_deleted_job.id}/save", headers=headers)
    assert r3.status_code == 404
    assert r3.json()["detail"] == "job_not_found"


@pytest.mark.integration
async def test_list_saved_jobs_returns_items(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="saved-list@example.com")
    job1, _ = await _make_job_and_employer(session, title="Alpha", employer_name="SavedListCo1")
    job2, _ = await _make_job_and_employer(session, title="Beta", employer_name="SavedListCo2")
    await session.commit()

    headers = _token_headers(user)
    await async_client.post(f"/v1/jobs/{job1.id}/save", headers=headers)
    await async_client.post(f"/v1/jobs/{job2.id}/save", headers=headers)

    resp = await async_client.get("/v1/saved", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    job_ids = {it["saved_job"]["job_id"] for it in items}
    assert str(job1.id) in job_ids
    assert str(job2.id) in job_ids

    # Each item must carry saved_job + job + employer keys.
    for item in items:
        assert "saved_job" in item
        assert "job" in item
        assert "employer" in item


@pytest.mark.integration
async def test_list_saved_jobs_excludes_unsaved(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="saved-excl@example.com")
    job1, _ = await _make_job_and_employer(session, title="Keep", employer_name="SavedExclCo1")
    job2, _ = await _make_job_and_employer(session, title="Drop", employer_name="SavedExclCo2")
    await session.commit()

    headers = _token_headers(user)
    await async_client.post(f"/v1/jobs/{job1.id}/save", headers=headers)
    await async_client.post(f"/v1/jobs/{job2.id}/save", headers=headers)

    # Unsave job2 — its soft-deleted row must not appear in the list.
    await async_client.delete(f"/v1/jobs/{job2.id}/save", headers=headers)

    resp = await async_client.get("/v1/saved", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["saved_job"]["job_id"] == str(job1.id)


@pytest.mark.integration
async def test_list_saved_jobs_pagination(session: AsyncSession, async_client: AsyncClient) -> None:
    user, _ = await _make_applicant(session, email="saved-page@example.com")
    jobs = []
    for i in range(5):
        job, _ = await _make_job_and_employer(
            session, title=f"SJob{i}", employer_name=f"SavedPageCo{i}"
        )
        jobs.append(job)
    await session.commit()

    headers = _token_headers(user)
    for job in jobs:
        r = await async_client.post(f"/v1/jobs/{job.id}/save", headers=headers)
        assert r.status_code == 201

    # Page 1 — limit=2.
    resp1 = await async_client.get("/v1/saved?limit=2", headers=headers)
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    # Page 2.
    resp2 = await async_client.get(
        f"/v1/saved?limit=2&cursor={body1['next_cursor']}", headers=headers
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2["items"]) == 2
    assert body2["next_cursor"] is not None

    # Page 3 — last page.
    resp3 = await async_client.get(
        f"/v1/saved?limit=2&cursor={body2['next_cursor']}", headers=headers
    )
    assert resp3.status_code == 200
    body3 = resp3.json()
    assert len(body3["items"]) == 1
    assert body3["next_cursor"] is None

    # All 5 saved jobs appear exactly once.
    all_ids = (
        [it["saved_job"]["id"] for it in body1["items"]]
        + [it["saved_job"]["id"] for it in body2["items"]]
        + [it["saved_job"]["id"] for it in body3["items"]]
    )
    assert len(all_ids) == len(set(all_ids)) == 5


@pytest.mark.integration
async def test_list_saved_jobs_etag_round_trip(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="saved-etag@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="SavedEtagCo")
    await session.commit()

    headers = _token_headers(user)
    await async_client.post(f"/v1/jobs/{job.id}/save", headers=headers)

    r1 = await async_client.get("/v1/saved", headers=headers)
    assert r1.status_code == 200
    etag = r1.headers["ETag"]

    r2 = await async_client.get(
        "/v1/saved",
        headers={**headers, "If-None-Match": etag},
    )
    assert r2.status_code == 304
    assert r2.content == b""
