from __future__ import annotations

import pytest
from sqlalchemy import select

from jobify.db.models import Job

pytestmark = pytest.mark.integration


async def _setup_job(async_client, token):
    emp = await async_client.post(
        "/v1/employers", json={"name": "Acme"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert emp.status_code == 201
    body = {
        "employer_id": emp.json()["id"],
        "title": "Engineer",
        "description": "Build distributed systems." * 2,
        "locations": ["Bangalore"],
        "min_exp_years": 1,
        "max_exp_years": 5,
    }
    r = await async_client.post("/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_delete_soft_deletes_job(async_client, session, applicant_user_and_token):
    _, token = applicant_user_and_token
    job_id = await _setup_job(async_client, token)

    r = await async_client.delete(
        f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 204

    job = await session.scalar(select(Job).where(Job.id == job_id))
    assert job is not None
    assert job.deleted_at is not None


async def test_delete_second_call_returns_404(async_client, applicant_user_and_token):
    """Soft-deleted rows are excluded from _load_recruiter_job → uniform 404 on re-delete."""
    _, token = applicant_user_and_token
    job_id = await _setup_job(async_client, token)
    r1 = await async_client.delete(
        f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r1.status_code == 204
    r2 = await async_client.delete(
        f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 404


async def test_delete_other_employer_returns_404(async_client, session, applicant_user_and_token):
    _, token = applicant_user_and_token
    job_id = await _setup_job(async_client, token)

    from jobify.db.models import User, UserRole
    from jobify_api.auth.tokens import mint_access_token

    other = User(email="other@example.com", role=UserRole.APPLICANT)
    session.add(other)
    await session.flush()
    other_token = mint_access_token(
        user_id=other.id, role=other.role.value, secret="x" * 32, ttl_seconds=600
    )
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Beta"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r1.status_code == 201

    r = await async_client.delete(
        f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert r.status_code == 404


async def test_delete_applicant_returns_403(async_client, applicant_user_and_token):
    """An APPLICANT (no employer-create call) gets 403 not_a_recruiter from _load_recruiter_job."""
    _, token = applicant_user_and_token
    r = await async_client.delete(
        "/v1/jobs/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"
