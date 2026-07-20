"""Integration tests for POST /v1/jobs/{job_id}/apply."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Application,
    ApplicationStage,
    ApplicationStageEvent,
    ApplicationStatus,
    Employer,
    Job,
    JobStatus,
    User,
    UserRole,
)
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


async def _make_applicant(
    session: AsyncSession, email: str = "apply@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Apply Test")
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
async def test_apply_creates_application_201(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, applicant = await _make_applicant(session, email="apply-201@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="Apply201Co")
    await session.commit()

    resp = await async_client.post(
        f"/v1/jobs/{job.id}/apply",
        headers=_token_headers(user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["job_id"] == str(job.id)
    assert body["status"] == "applied"
    assert body["source"] == "feed"

    # Verify the row exists in the DB.
    row = (
        await session.execute(
            select(Application).where(
                Application.applicant_id == applicant.id,
                Application.job_id == job.id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.status == ApplicationStatus.APPLIED


@pytest.mark.integration
async def test_apply_idempotent_returns_existing_200(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="apply-idem@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="ApplyIdemCo")
    await session.commit()

    headers = _token_headers(user)

    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201
    first_id = r1.json()["id"]

    r2 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == first_id
    assert r2.json()["status"] == "applied"


@pytest.mark.integration
async def test_apply_reapply_after_withdraw_updates_same_row_to_applied(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Apply → withdraw → re-apply: the same row id is reused; status=applied."""
    user, applicant = await _make_applicant(session, email="apply-reapply@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="ApplyReapplyCo")
    await session.commit()

    headers = _token_headers(user)

    # First apply — 201.
    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201
    original_id = r1.json()["id"]

    # Withdraw — 200.
    r2 = await async_client.patch(
        f"/v1/applications/{original_id}",
        json={"status": "withdrawn"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "withdrawn"

    # Re-apply — 200 (updates same withdrawn row back to applied).
    r3 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r3.status_code == 200
    body3 = r3.json()
    # Same row id (approach b — row-id stable per spec Decision #2).
    assert body3["id"] == original_id
    assert body3["status"] == "applied"


@pytest.mark.integration
async def test_apply_reapply_resets_stage_and_records_event(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Apply -> recruiter bumps stage -> withdraw -> re-apply resets stage=applied
    and records a (<old> -> applied) stage event with the applicant as actor."""
    user, applicant = await _make_applicant(session, email="apply-reapply-stage@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="ApplyReapplyStageCo")
    await session.commit()

    headers = _token_headers(user)

    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201
    app_id = r1.json()["id"]

    # Recruiter-side stage bump, written directly (no recruiter route needed here).
    await session.execute(
        update(Application)
        .where(Application.id == uuid.UUID(app_id))
        .values(stage=ApplicationStage.INTERVIEW.value)
    )
    await session.commit()

    r2 = await async_client.patch(
        f"/v1/applications/{app_id}",
        json={"status": "withdrawn"},
        headers=headers,
    )
    assert r2.status_code == 200

    r3 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r3.status_code == 200  # same-row re-apply
    body3 = r3.json()
    assert body3["id"] == app_id
    assert body3["stage"] == "applied"

    events = (
        (
            await session.execute(
                select(ApplicationStageEvent).where(
                    ApplicationStageEvent.application_id == uuid.UUID(app_id)
                )
            )
        )
        .scalars()
        .all()
    )
    assert ("interview", "applied") in [(e.from_stage, e.to_stage) for e in events]
    reset_event = next(e for e in events if e.from_stage == "interview")
    assert reset_event.actor_user_id == user.id


@pytest.mark.integration
async def test_apply_404_for_unknown_job(session: AsyncSession, async_client: AsyncClient) -> None:
    user, _ = await _make_applicant(session, email="apply-404job@example.com")
    await session.commit()

    resp = await async_client.post(
        f"/v1/jobs/{uuid.uuid4()}/apply",
        headers=_token_headers(user),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "job_not_found"


@pytest.mark.integration
async def test_apply_404_for_closed_job(session: AsyncSession, async_client: AsyncClient) -> None:
    user, _ = await _make_applicant(session, email="apply-closed@example.com")
    job, _ = await _make_job_and_employer(
        session,
        employer_name="ApplyClosedCo",
        status_value=JobStatus.CLOSED,
    )
    await session.commit()

    resp = await async_client.post(
        f"/v1/jobs/{job.id}/apply",
        headers=_token_headers(user),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "job_not_found"


@pytest.mark.integration
async def test_apply_404_for_soft_deleted_job(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="apply-softdel@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="ApplySoftDelCo")
    job.deleted_at = datetime.now(UTC)
    await session.commit()

    resp = await async_client.post(
        f"/v1/jobs/{job.id}/apply",
        headers=_token_headers(user),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "job_not_found"


@pytest.mark.integration
async def test_apply_401_missing_token(session: AsyncSession, async_client: AsyncClient) -> None:
    job, _ = await _make_job_and_employer(session, employer_name="Apply401Co")
    await session.commit()

    resp = await async_client.post(f"/v1/jobs/{job.id}/apply")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_apply_403_recruiter_token(session: AsyncSession, async_client: AsyncClient) -> None:
    recruiter = User(email="apply-recruiter@example.com", role=UserRole.RECRUITER)
    session.add(recruiter)
    job, _ = await _make_job_and_employer(session, employer_name="Apply403Co")
    await session.commit()

    resp = await async_client.post(
        f"/v1/jobs/{job.id}/apply",
        headers=_token_headers(recruiter),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"
