"""Integration tests for PUT/DELETE /v1/jobs/{job_id}/match-feedback."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Employer,
    Job,
    JobStatus,
    Match,
    MatchFeedback,
    User,
    UserRole,
)
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


async def _make_applicant(
    session: AsyncSession, email: str = "feed@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Feed Test")
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


async def _make_match(
    session: AsyncSession,
    *,
    applicant_id: uuid.UUID,
    job_id: uuid.UUID,
    total_score: float,
    surfaced: bool = True,
) -> Match:
    m = Match(
        applicant_id=applicant_id,
        job_id=job_id,
        vector_score=total_score,
        structured_score=total_score,
        total_score=total_score,
        score_components={"location": 1.0, "exp": 1.0, "ctc": 1.0},
        model_versions={"applicant_model": "test", "job_model": "test"},
        surfaced_at=datetime.now(UTC) if surfaced else None,
        explanation={
            "fit": "test",
            "caveat": "",
            "generator": "templated",
            "generator_version": "1",
        },
    )
    session.add(m)
    await session.flush()
    return m


def _token_headers(user: User) -> dict[str, str]:
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    return {"Authorization": f"Bearer {token}"}


async def _setup(session: AsyncSession) -> tuple[User, Applicant, Job]:
    user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job, _ = await _make_job_and_employer(session)
    await _make_match(
        session, applicant_id=applicant.id, job_id=job.id, total_score=0.8, surfaced=True
    )
    await session.commit()
    return user, applicant, job


async def test_put_creates_rating(async_client: AsyncClient, session: AsyncSession) -> None:
    user, _, job = await _setup(session)
    r = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback",
        json={"rating": "down"},
        headers=_token_headers(user),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rating"] == "down"
    assert body["job_id"] == str(job.id)


async def test_put_rerate_updates_same_row(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, job = await _setup(session)
    h = _token_headers(user)
    r1 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "down"}, headers=h
    )
    r2 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "up"}, headers=h
    )
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]  # same live row, rating flipped
    rows = (
        (
            await session.execute(
                select(MatchFeedback).where(MatchFeedback.applicant_id == applicant.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1 and rows[0].rating == "up"


async def test_delete_soft_deletes_and_reput_creates_fresh_row(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, job = await _setup(session)
    h = _token_headers(user)
    r1 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "down"}, headers=h
    )
    rd = await async_client.delete(f"/v1/jobs/{job.id}/match-feedback", headers=h)
    assert rd.status_code == 204
    r2 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "down"}, headers=h
    )
    assert r2.status_code == 200
    assert r2.json()["id"] != r1.json()["id"]  # fresh row after soft-delete
    rows = (
        (
            await session.execute(
                select(MatchFeedback).where(MatchFeedback.applicant_id == applicant.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert sum(1 for x in rows if x.deleted_at is None) == 1


async def test_delete_absent_is_204_noop(async_client: AsyncClient, session: AsyncSession) -> None:
    user, _, job = await _setup(session)
    r = await async_client.delete(f"/v1/jobs/{job.id}/match-feedback", headers=_token_headers(user))
    assert r.status_code == 204


async def test_put_404_when_match_not_surfaced(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job, _ = await _make_job_and_employer(session)
    await _make_match(
        session, applicant_id=applicant.id, job_id=job.id, total_score=0.3, surfaced=False
    )
    await session.commit()
    r = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback",
        json={"rating": "up"},
        headers=_token_headers(user),
    )
    assert r.status_code == 404


async def test_put_404_when_no_match_at_all(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _ = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    r = await async_client.put(
        f"/v1/jobs/{uuid.uuid4()}/match-feedback",
        json={"rating": "up"},
        headers=_token_headers(user),
    )
    assert r.status_code == 404


async def test_put_rejects_bad_rating(async_client: AsyncClient, session: AsyncSession) -> None:
    user, _, job = await _setup(session)
    r = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback",
        json={"rating": "meh"},
        headers=_token_headers(user),
    )
    assert r.status_code == 422


async def test_requires_auth(async_client: AsyncClient) -> None:
    r = await async_client.put(f"/v1/jobs/{uuid.uuid4()}/match-feedback", json={"rating": "up"})
    assert r.status_code == 401
