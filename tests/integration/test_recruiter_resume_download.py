from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from jobify.db.models import Applicant, Application, Resume, User, UserRole

pytestmark = pytest.mark.integration


async def _setup_employer_and_job(async_client, token):
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


async def _seed_applicant_with_resume(session, storage, job_id, content: bytes):
    u = User(email="seeker@example.com", role=UserRole.APPLICANT)
    session.add(u)
    await session.flush()
    a = Applicant(user_id=u.id, full_name="Job Seeker")
    session.add(a)
    await session.flush()
    r = Resume(
        applicant_id=a.id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        storage_key="",
        size_bytes=len(content),
    )
    session.add(r)
    await session.flush()
    r.storage_key = f"resumes/{r.id}.pdf"
    await storage.save(key=r.storage_key, content=content, content_type="application/pdf")
    app = Application(applicant_id=a.id, job_id=job_id, status="applied")
    session.add(app)
    await session.flush()
    return r, app


async def test_recruiter_downloads_resume(async_client, session, applicant_user_and_token):
    recruiter, token = applicant_user_and_token
    job_id = await _setup_employer_and_job(async_client, token)
    storage = async_client._transport.app.state.storage  # type: ignore[union-attr]
    resume, application = await _seed_applicant_with_resume(
        session, storage, job_id, b"%PDF-1.4 fake resume bytes"
    )
    await session.commit()

    with capture_logs() as logs:
        r = await async_client.get(
            f"/v1/applications/{application.id}/resume",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content == b"%PDF-1.4 fake resume bytes"

    audit = [e for e in logs if e.get("event") == "recruiter.resume-accessed"]
    assert len(audit) == 1, logs
    assert audit[0]["application_id"] == str(application.id)
    assert audit[0]["resume_id"] == str(resume.id)

    from sqlalchemy import select as sa_select

    from jobify.db.models import AuditLog, EmployerUser

    # Resolve employer_id for the recruiter (created by _setup_employer_and_job)
    eu_row = (
        await session.execute(sa_select(EmployerUser).where(EmployerUser.user_id == recruiter.id))
    ).scalar_one()

    result = await session.execute(
        sa_select(AuditLog).where(
            AuditLog.action == "resume.accessed",
            AuditLog.resource_id == resume.id,
        )
    )
    audit_row = result.scalar_one()
    assert audit_row.actor_user_id == recruiter.id
    assert audit_row.actor_role == "recruiter"
    assert audit_row.context["request_id"] is not None
    assert audit_row.context["application_id"] == str(application.id)
    assert audit_row.context["applicant_id"] == str(application.applicant_id)
    assert audit_row.context["employer_id"] == str(eu_row.employer_id)


async def test_recruiter_at_other_employer_gets_404(
    async_client, session, applicant_user_and_token
):
    _, token = applicant_user_and_token
    job_id = await _setup_employer_and_job(async_client, token)
    storage = async_client._transport.app.state.storage  # type: ignore[union-attr]
    _, application = await _seed_applicant_with_resume(session, storage, job_id, b"X")
    await session.commit()

    # Other recruiter
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

    r = await async_client.get(
        f"/v1/applications/{application.id}/resume",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 404


async def test_applicant_role_returns_403(async_client, applicant_user_and_token):
    _, token = applicant_user_and_token
    r = await async_client.get(
        "/v1/applications/00000000-0000-0000-0000-000000000000/resume",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"


async def test_download_sanitizes_content_disposition_filename(
    async_client, session, applicant_user_and_token
):
    """An applicant-controlled filename must not break the header (RFC 6266).

    Quotes/backslashes/control chars are replaced in the ASCII fallback and
    the exact original name travels percent-encoded in filename*.
    """
    recruiter, token = applicant_user_and_token
    job_id = await _setup_employer_and_job(async_client, token)
    storage = async_client._transport.app.state.storage  # type: ignore[union-attr]
    resume, application = await _seed_applicant_with_resume(session, storage, job_id, b"X")
    resume.original_filename = 'we"ird\\name\r\n.pdf'
    await session.commit()

    r = await async_client.get(
        f"/v1/applications/{application.id}/resume",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    cd = r.headers["content-disposition"]
    assert "\r" not in cd and "\n" not in cd
    assert 'filename="we_ird_name__.pdf"' in cd
    assert "filename*=UTF-8''we%22ird%5Cname%0D%0A.pdf" in cd
