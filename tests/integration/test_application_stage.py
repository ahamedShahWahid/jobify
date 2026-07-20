"""Integration tests for PATCH /v1/jobs/{job_id}/applications/{id}/stage."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Application,
    ApplicationStageEvent,
    ApplicationStatus,
    AuditLog,
    Employer,
    EmployerUser,
    Job,
    JobStatus,
    Notification,
    User,
    UserRole,
)
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


def _token_headers(user: User) -> dict[str, str]:
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    return {"Authorization": f"Bearer {token}"}


async def _make_recruiter_and_employer(
    session: AsyncSession, *, email: str, employer_name: str
) -> tuple[User, Employer]:
    user = User(email=email, role=UserRole.RECRUITER)
    session.add(user)
    await session.flush()
    employer = Employer(name=employer_name, name_norm=employer_name.lower())
    session.add(employer)
    await session.flush()
    session.add(EmployerUser(employer_id=employer.id, user_id=user.id, role="owner"))
    await session.flush()
    return user, employer


async def _make_job(session: AsyncSession, employer: Employer, *, title: str) -> Job:
    job = Job(
        employer_id=employer.id,
        title=title,
        description="Build distributed systems in Python and Postgres.",
        locations=["Bangalore"],
        min_exp_years=1,
        max_exp_years=5,
        status=JobStatus.OPEN,
    )
    session.add(job)
    await session.flush()
    return job


async def _make_applicant(session: AsyncSession, *, email: str) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Stage Test Applicant")
    session.add(applicant)
    await session.flush()
    return user, applicant


async def _make_application(
    session: AsyncSession, *, applicant: Applicant, job: Job
) -> Application:
    application = Application(
        applicant_id=applicant.id,
        job_id=job.id,
        status=ApplicationStatus.APPLIED,
    )
    session.add(application)
    await session.flush()
    return application


async def _setup(
    session: AsyncSession,
) -> tuple[User, Employer, Job, User, Applicant, Application]:
    """Recruiter + employer + job + applicant + a fresh 'applied' application."""
    tag = uuid.uuid4().hex[:8]
    recruiter, employer = await _make_recruiter_and_employer(
        session,
        email=f"stage-recruiter-{tag}@example.com",
        employer_name=f"StageCo-{tag}",
    )
    job = await _make_job(session, employer, title=f"Stage Job {tag}")
    applicant_user, applicant = await _make_applicant(
        session, email=f"stage-applicant-{tag}@example.com"
    )
    application = await _make_application(session, applicant=applicant, job=job)
    await session.commit()
    return recruiter, employer, job, applicant_user, applicant, application


async def test_stage_change_happy_path(async_client: AsyncClient, session: AsyncSession) -> None:
    recruiter, _, job, applicant_user, _, application = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 200
    assert r.json()["stage"] == "shortlisted"

    events = (
        (
            await session.execute(
                select(ApplicationStageEvent).where(
                    ApplicationStageEvent.application_id == application.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert [(e.from_stage, e.to_stage) for e in events] == [("applied", "shortlisted")]
    assert events[0].actor_user_id == recruiter.id

    notifs = (
        (
            await session.execute(
                select(Notification).where(Notification.kind == "application_stage_changed")
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 2  # EMAIL + IN_APP
    assert {n.channel.value for n in notifs} == {"email", "in_app"}
    assert all(n.user_id == applicant_user.id for n in notifs)
    assert notifs[0].payload["stage"] == "shortlisted"
    assert notifs[0].payload["job_title"] == job.title

    audit = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "application.stage_changed")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1


async def test_same_stage_noop_writes_nothing(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    h = _token_headers(recruiter)
    await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "interview"},
        headers=h,
    )

    async def _counts() -> tuple[int, int, int]:
        events = (
            (
                await session.execute(
                    select(ApplicationStageEvent).where(
                        ApplicationStageEvent.application_id == application.id
                    )
                )
            )
            .scalars()
            .all()
        )
        notifs = (
            (
                await session.execute(
                    select(Notification).where(Notification.kind == "application_stage_changed")
                )
            )
            .scalars()
            .all()
        )
        audit = (
            (
                await session.execute(
                    select(AuditLog).where(AuditLog.action == "application.stage_changed")
                )
            )
            .scalars()
            .all()
        )
        return len(events), len(notifs), len(audit)

    baseline_events, baseline_notifs, baseline_audit = await _counts()
    assert (baseline_events, baseline_notifs, baseline_audit) == (1, 2, 1)

    r2 = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "interview"},
        headers=h,
    )
    assert r2.status_code == 200

    events_after, notifs_after, audit_after = await _counts()
    assert events_after == 1  # second call wrote no event
    assert notifs_after == baseline_notifs  # no new notifications
    assert audit_after == baseline_audit  # no new audit row


async def test_free_movement_including_backwards(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    h = _token_headers(recruiter)
    for stage in ("offer", "interview", "rejected", "shortlisted"):
        r = await async_client.patch(
            f"/v1/jobs/{job.id}/applications/{application.id}/stage",
            json={"stage": stage},
            headers=h,
        )
        assert r.status_code == 200, stage


async def test_applied_not_a_settable_target(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "applied"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 422


async def test_withdrawn_application_409(async_client: AsyncClient, session: AsyncSession) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    application.status = ApplicationStatus.WITHDRAWN
    await session.commit()
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "application_withdrawn"


async def test_uniform_404_other_employers_application(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, _ = await _setup(session)
    # An application under a DIFFERENT employer's job:
    _, _, other_job, _, _, other_app = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{other_app.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 404


async def test_stage_patch_unknown_application_404(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, _ = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{uuid.uuid4()}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 404


async def test_applicant_role_gets_403_or_404(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    _, _, job, applicant_user, _, application = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(applicant_user),
    )
    # _load_recruiter_job's guard runs _require_recruiter() before any job
    # lookup, so a non-recruiter caller always gets 403 not_a_recruiter here
    # (never 404) — tightened from the general "403 or 404" contract.
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"
