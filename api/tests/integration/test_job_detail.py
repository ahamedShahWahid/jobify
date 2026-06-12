"""Integration tests for GET /v1/jobs/{id}."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.tokens import mint_access_token
from jobify.db.models import (
    Applicant,
    Application,
    Employer,
    Job,
    JobStatus,
    Match,
    SavedJob,
    User,
    UserRole,
)

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


async def _make_applicant(
    session: AsyncSession, email: str = "jd@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="JD Test", locations=["Bangalore"])
    session.add(applicant)
    await session.flush()
    return user, applicant


async def _make_job_and_employer(
    session: AsyncSession,
    *,
    title: str = "Engineer",
    employer_name: str = "Acme",
    status_value: JobStatus = JobStatus.OPEN,
    verified: bool = True,
) -> tuple[Job, Employer]:
    employer = Employer(
        name=employer_name,
        name_norm=employer_name.lower(),
        verified_at=datetime.now(UTC) if verified else None,
    )
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
async def test_job_detail_happy_path(session: AsyncSession, async_client: AsyncClient) -> None:
    user, applicant = await _make_applicant(session, email="jd-happy@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="HappyCo")
    session.add(
        Match(
            applicant_id=applicant.id,
            job_id=j.id,
            vector_score=0.8,
            structured_score=0.8,
            total_score=0.8,
            score_components={"location": 1.0, "exp": 1.0, "ctc": 0.4},
            model_versions={},
            surfaced_at=datetime.now(UTC),
            explanation={
                "fit": "test",
                "caveat": "",
                "generator": "templated",
                "generator_version": "1",
            },
        )
    )
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["job"]["id"] == str(j.id)
    assert body["job"]["title"] == "Engineer"
    assert body["job"]["status"] == "open"
    assert body["employer"]["verified"] is True
    assert body["match"] is not None
    assert body["match"]["total_score"] == pytest.approx(0.8)
    assert body["match"]["explanation"] is not None
    assert "fit" in body["match"]["explanation"]


@pytest.mark.integration
async def test_job_detail_match_null_when_no_match_exists(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="jd-nomatch@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="NoMatchCo")
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 200
    assert resp.json()["match"] is None


@pytest.mark.integration
async def test_job_detail_404_for_unknown_id(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="jd-404@example.com")
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{uuid.uuid4()}", headers=_token_headers(user))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "job_not_found"


@pytest.mark.integration
async def test_job_detail_404_for_closed_job(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="jd-closed@example.com")
    j, _ = await _make_job_and_employer(
        session, employer_name="ClosedCo", status_value=JobStatus.CLOSED
    )
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "job_not_found"


@pytest.mark.integration
async def test_job_detail_404_for_soft_deleted_job(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="jd-softdel@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="SoftDelCo")
    j.deleted_at = datetime.now(UTC)
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 404


@pytest.mark.integration
async def test_job_detail_returns_match_even_when_below_threshold(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, applicant = await _make_applicant(session, email="jd-thresh@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="ThreshCo")
    session.add(
        Match(
            applicant_id=applicant.id,
            job_id=j.id,
            vector_score=0.3,
            structured_score=0.3,
            total_score=0.3,
            score_components={},
            model_versions={},
            surfaced_at=None,  # below threshold — not surfaced
        )
    )
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 200
    assert resp.json()["match"] is not None
    assert resp.json()["match"]["surfaced_at"] is None


@pytest.mark.integration
async def test_job_detail_invalid_uuid(session: AsyncSession, async_client: AsyncClient) -> None:
    user, _ = await _make_applicant(session, email="jd-baduuid@example.com")
    await session.commit()
    resp = await async_client.get("/v1/jobs/not-a-uuid", headers=_token_headers(user))
    # FastAPI's default for a malformed UUID path param is 422; the error-handler
    # middleware may convert that to 400. Accept either.
    assert resp.status_code in (400, 422)


@pytest.mark.integration
async def test_job_detail_missing_token_returns_401(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    j, _ = await _make_job_and_employer(session, employer_name="NoBearerCo")
    await session.commit()
    resp = await async_client.get(f"/v1/jobs/{j.id}")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_job_detail_recruiter_role_returns_403(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user = User(email="jd-recruiter@example.com", role=UserRole.RECRUITER)
    session.add(user)
    j, _ = await _make_job_and_employer(session, employer_name="RecruiterCo")
    await session.commit()
    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"


@pytest.mark.integration
async def test_job_detail_etag_returns_304(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="jd-etag@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="EtagJobCo")
    await session.commit()

    r1 = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert r1.status_code == 200
    etag = r1.headers["ETag"]

    r2 = await async_client.get(
        f"/v1/jobs/{j.id}",
        headers={**_token_headers(user), "If-None-Match": etag},
    )
    assert r2.status_code == 304
    assert r2.content == b""


@pytest.mark.integration
async def test_job_detail_application_null_when_user_never_applied(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """application/saved_job default to null when the applicant has neither."""
    user, _ = await _make_applicant(session, email="jd-noapp@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="NoAppCo")
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["application"] is None
    assert body["saved_job"] is None


@pytest.mark.integration
async def test_job_detail_includes_applied_application(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """When the applicant has applied, the response carries status='applied'.

    Reproduces the bug where the Flutter ActionBar shows the Apply button
    even after applying — the backend silently omitted the application.
    """
    user, applicant = await _make_applicant(session, email="jd-applied@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="AppliedCo")
    app = Application(
        applicant_id=applicant.id,
        job_id=j.id,
        status="applied",
        source="feed",
    )
    session.add(app)
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["application"] is not None
    assert body["application"]["id"] == str(app.id)
    assert body["application"]["job_id"] == str(j.id)
    assert body["application"]["status"] == "applied"
    assert body["application"]["source"] == "feed"
    assert "created_at" in body["application"]
    assert "updated_at" in body["application"]


@pytest.mark.integration
async def test_job_detail_includes_withdrawn_application(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Withdrawn applications are still returned (status flip, not soft-delete).

    The ActionBar uses status to decide Apply vs Withdraw — for a withdrawn
    row it shows Apply (re-apply path) but it still needs to see the row.
    """
    user, applicant = await _make_applicant(session, email="jd-withdrawn@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="WithdrawnCo")
    app = Application(
        applicant_id=applicant.id,
        job_id=j.id,
        status="withdrawn",
        source="feed",
    )
    session.add(app)
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 200
    assert resp.json()["application"]["status"] == "withdrawn"


@pytest.mark.integration
async def test_job_detail_includes_saved_job(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, applicant = await _make_applicant(session, email="jd-saved@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="SavedCo")
    sj = SavedJob(applicant_id=applicant.id, job_id=j.id)
    session.add(sj)
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["saved_job"] is not None
    assert body["saved_job"]["id"] == str(sj.id)
    assert body["saved_job"]["job_id"] == str(j.id)


@pytest.mark.integration
async def test_job_detail_application_scoped_to_caller(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Another applicant's application MUST NOT leak into this caller's response."""
    caller, _caller_a = await _make_applicant(session, email="jd-caller@example.com")
    other_user, other_applicant = await _make_applicant(session, email="jd-other@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="ScopedCo")
    session.add(
        Application(
            applicant_id=other_applicant.id,
            job_id=j.id,
            status="applied",
            source="feed",
        )
    )
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(caller))
    assert resp.status_code == 200
    assert resp.json()["application"] is None


@pytest.mark.integration
async def test_job_detail_etag_changes_when_application_changes(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """ETag must depend on application.updated_at so the client refetches
    after apply / withdraw instead of seeing a stale 304."""
    user, applicant = await _make_applicant(session, email="jd-etag2@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="EtagAppCo")
    await session.commit()

    r1 = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    etag1 = r1.headers["ETag"]

    session.add(
        Application(
            applicant_id=applicant.id,
            job_id=j.id,
            status="applied",
            source="feed",
        )
    )
    await session.commit()

    r2 = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    etag2 = r2.headers["ETag"]
    assert etag2 != etag1, "ETag must change once an application exists"


async def test_job_detail_soft_deleted_applicant_gets_500(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Same tombstoned-applicant guard as the feed — see test_feed.py."""
    user, applicant = await _make_applicant(session, email="jd-tombstone@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="TombstoneCo")
    applicant.deleted_at = datetime.now(UTC)
    await session.commit()

    r = await async_client.get(f"/v1/jobs/{j.id}", headers=_token_headers(user))
    assert r.status_code == 500
    assert r.json()["detail"] == "applicant_missing"
