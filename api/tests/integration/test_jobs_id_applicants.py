from __future__ import annotations

import pytest

from kpa.db.models import Applicant, Application, User, UserRole

pytestmark = pytest.mark.integration


async def _setup_employer(async_client, token):
    emp = await async_client.post(
        "/v1/employers", json={"name": "Acme"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert emp.status_code == 201
    return emp.json()["id"]


async def _create_job(async_client, token, emp_id):
    body = {
        "employer_id": emp_id,
        "title": "Engineer",
        "description": "Build distributed systems." * 2,
        "locations": ["Bangalore"],
        "min_exp_years": 1,
        "max_exp_years": 5,
    }
    r = await async_client.post("/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_applications(session, job_id, n: int):
    """Insert n live applications, each with its own applicant+user."""
    for i in range(n):
        u = User(email=f"applicant{i}@example.com", role=UserRole.APPLICANT)
        session.add(u)
        await session.flush()
        a = Applicant(user_id=u.id, full_name=f"Applicant {i}")
        session.add(a)
        await session.flush()
        app = Application(applicant_id=a.id, job_id=job_id, status="applied")
        session.add(app)
    await session.flush()


async def test_applicants_happy_path(async_client, session, applicant_user_and_token):
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    job_id = await _create_job(async_client, token, emp_id)
    await _seed_applications(session, job_id, 3)
    await session.commit()

    r = await async_client.get(
        f"/v1/jobs/{job_id}/applicants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 3
    for row in body["items"]:
        assert row["status"] == "applied"
        assert row["match_score"] is None
        assert row["match_explanation"] is None
        assert "@example.com" in row["email"]


async def test_applicants_other_employer_returns_404(
    async_client, session, applicant_user_and_token
):
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    job_id = await _create_job(async_client, token, emp_id)

    # Other recruiter
    from kpa.auth.tokens import mint_access_token

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

    r = await async_client.get(
        f"/v1/jobs/{job_id}/applicants",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 404


async def test_applicants_applicant_role_returns_403(async_client, applicant_user_and_token):
    _, token = applicant_user_and_token
    r = await async_client.get(
        "/v1/jobs/00000000-0000-0000-0000-000000000000/applicants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"


async def test_applicants_listing_writes_audit_row(async_client, session, applicant_user_and_token):
    """Listing applicants exposes PII (names + emails) — must be audited,
    mirroring the resume-download endpoint."""
    recruiter, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    job_id = await _create_job(async_client, token, emp_id)
    await _seed_applications(session, job_id, 2)
    await session.commit()

    r = await async_client.get(
        f"/v1/jobs/{job_id}/applicants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    import uuid as _uuid

    from sqlalchemy import select as sa_select

    from kpa.db.models import AuditLog

    row = (
        await session.execute(
            sa_select(AuditLog).where(
                AuditLog.action == "job.applicants_listed",
                AuditLog.resource_id == _uuid.UUID(job_id),
            )
        )
    ).scalar_one()
    assert row.actor_user_id == recruiter.id
    assert row.actor_role == "recruiter"
    assert row.context["employer_id"] == emp_id
    assert row.context["count"] == 2
