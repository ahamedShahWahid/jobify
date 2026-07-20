"""Integration tests for GET /v1/applications/{id}/timeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Application,
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
    session: AsyncSession, email: str = "timeline@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Timeline Test")
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


async def _setup(
    session: AsyncSession, *, email: str | None = None, employer_name: str | None = None
) -> tuple[User, Applicant, Job, Application]:
    suffix = uuid.uuid4().hex[:8]
    user, applicant = await _make_applicant(
        session, email=email or f"timeline-{suffix}@example.com"
    )
    job, _employer = await _make_job_and_employer(
        session, employer_name=employer_name or f"TimelineCo{suffix}"
    )
    await session.flush()
    application = Application(
        applicant_id=applicant.id,
        job_id=job.id,
        status=ApplicationStatus.APPLIED,
    )
    session.add(application)
    await session.flush()
    return user, applicant, job, application


async def test_timeline_orders_events_and_hides_actor(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, job, application = await _setup(session)
    # Explicit, strictly-increasing created_at: the whole test runs inside one
    # savepoint-nested Postgres transaction, so server_default func.now() (which
    # returns the transaction START time, not per-statement time) would tie
    # across both inserts and make ordering non-deterministic.
    base = datetime.now(UTC)
    for offset, pair in enumerate((("applied", "shortlisted"), ("shortlisted", "interview"))):
        session.add(
            ApplicationStageEvent(
                application_id=application.id,
                from_stage=pair[0],
                to_stage=pair[1],
                actor_user_id=user.id,
                created_at=base + timedelta(milliseconds=offset),
            )
        )
    await session.commit()
    r = await async_client.get(
        f"/v1/applications/{application.id}/timeline", headers=_token_headers(user)
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert [(i["from_stage"], i["to_stage"]) for i in items] == [
        ("applied", "shortlisted"),
        ("shortlisted", "interview"),
    ]
    assert all(set(i.keys()) == {"from_stage", "to_stage", "created_at"} for i in items)


async def test_timeline_uniform_404_for_other_applicants_application(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _, _, _ = await _setup(session)
    _, _, _, other_application = await _setup(session)
    await session.commit()
    r = await async_client.get(
        f"/v1/applications/{other_application.id}/timeline",
        headers=_token_headers(user),
    )
    assert r.status_code == 404


async def test_timeline_unknown_id_404(async_client: AsyncClient, session: AsyncSession) -> None:
    user, _, _, _ = await _setup(session)
    await session.commit()
    r = await async_client.get(
        f"/v1/applications/{uuid.uuid4()}/timeline", headers=_token_headers(user)
    )
    assert r.status_code == 404
