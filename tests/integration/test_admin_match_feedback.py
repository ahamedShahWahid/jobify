"""Integration tests for the admin Match QA endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
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


async def _make_admin(session: AsyncSession) -> User:
    admin = User(email=f"admin-{uuid.uuid4()}@example.com", role=UserRole.ADMIN)
    session.add(admin)
    await session.flush()
    return admin


async def _seed_ratings(session: AsyncSession, *, up: int, down: int) -> None:
    for i in range(up + down):
        user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
        job, _ = await _make_job_and_employer(
            session, title=f"J{i}", employer_name=f"E{uuid.uuid4()}"
        )
        await _make_match(session, applicant_id=applicant.id, job_id=job.id, total_score=0.8)
        session.add(
            MatchFeedback(
                applicant_id=applicant.id,
                job_id=job.id,
                rating="up" if i < up else "down",
            )
        )
    await session.flush()


async def test_admin_required(async_client: AsyncClient, session: AsyncSession) -> None:
    user, _ = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    await session.commit()
    r = await async_client.get("/v1/admin/match-feedback", headers=_token_headers(user))
    assert r.status_code == 403


async def test_list_returns_joined_rows_and_filter(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _make_admin(session)
    await _seed_ratings(session, up=2, down=1)
    await session.commit()
    h = _token_headers(admin)

    r = await async_client.get("/v1/admin/match-feedback", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    row = body["items"][0]
    for key in (
        "id",
        "rating",
        "created_at",
        "job_id",
        "job_title",
        "employer_name",
        "applicant_id",
        "applicant_name",
        "total_score",
        "explanation",
    ):
        assert key in row

    r_down = await async_client.get("/v1/admin/match-feedback?rating=down", headers=h)
    assert [it["rating"] for it in r_down.json()["items"]] == ["down"]


async def test_list_paginates(async_client: AsyncClient, session: AsyncSession) -> None:
    admin = await _make_admin(session)
    await _seed_ratings(session, up=3, down=0)
    await session.commit()
    h = _token_headers(admin)

    r1 = await async_client.get("/v1/admin/match-feedback?limit=2", headers=h)
    assert len(r1.json()["items"]) == 2
    cursor = r1.json()["next_cursor"]
    assert cursor is not None
    r2 = await async_client.get(f"/v1/admin/match-feedback?limit=2&cursor={cursor}", headers=h)
    assert len(r2.json()["items"]) == 1
    assert r2.json()["next_cursor"] is None


async def test_summary_counts_and_share(async_client: AsyncClient, session: AsyncSession) -> None:
    admin = await _make_admin(session)
    await _seed_ratings(session, up=3, down=1)
    await session.commit()

    r = await async_client.get("/v1/admin/match-feedback/summary", headers=_token_headers(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["all_time"] == {"up": 3, "down": 1, "share": 0.75}
    # Everything just seeded is inside the 30-day window too.
    assert body["last_30d"] == {"up": 3, "down": 1, "share": 0.75}


async def test_summary_zero_denominator_share_is_null(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _make_admin(session)
    await session.commit()
    r = await async_client.get("/v1/admin/match-feedback/summary", headers=_token_headers(admin))
    assert r.status_code == 200
    assert r.json()["all_time"]["share"] is None


async def test_list_keeps_rating_when_match_soft_deleted(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    """ON-clause regression pin: a soft-deleted match must not drop the rating
    row from the list — it lists with null score/explanation instead."""
    admin = await _make_admin(session)
    _, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job, _ = await _make_job_and_employer(session, employer_name=f"E{uuid.uuid4()}")
    match = await _make_match(session, applicant_id=applicant.id, job_id=job.id, total_score=0.8)
    session.add(MatchFeedback(applicant_id=applicant.id, job_id=job.id, rating="up"))
    match.deleted_at = datetime.now(UTC)
    await session.commit()

    r = await async_client.get("/v1/admin/match-feedback", headers=_token_headers(admin))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["rating"] == "up"
    assert items[0]["total_score"] is None
    assert items[0]["explanation"] is None
