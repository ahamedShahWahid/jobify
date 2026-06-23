"""Integration tests for GET /v1/feed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Employer,
    Job,
    JobStatus,
    Match,
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
    applicant = Applicant(user_id=user.id, full_name="Feed Test", locations=["Bangalore"])
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


@pytest.mark.integration
async def test_feed_empty_returns_empty_items(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session)
    await session.commit()
    resp = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


@pytest.mark.integration
async def test_feed_returns_surfaced_only(session: AsyncSession, async_client: AsyncClient) -> None:
    user, applicant = await _make_applicant(session, email="surf@example.com")
    j1, _ = await _make_job_and_employer(session, title="A", employer_name="Alpha")
    j2, _ = await _make_job_and_employer(session, title="B", employer_name="Beta")
    j3, _ = await _make_job_and_employer(session, title="C", employer_name="Gamma")
    await _make_match(session, applicant_id=applicant.id, job_id=j1.id, total_score=0.9)
    await _make_match(session, applicant_id=applicant.id, job_id=j2.id, total_score=0.8)
    await _make_match(
        session, applicant_id=applicant.id, job_id=j3.id, total_score=0.3, surfaced=False
    )
    await session.commit()

    resp = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert [item["job"]["title"] for item in items] == ["A", "B"]

    # Each item carries an explanation.
    for item in items:
        assert item["match"]["explanation"] is not None
        assert "fit" in item["match"]["explanation"]


@pytest.mark.integration
async def test_feed_excludes_closed_jobs(session: AsyncSession, async_client: AsyncClient) -> None:
    user, applicant = await _make_applicant(session, email="closed@example.com")
    j, _ = await _make_job_and_employer(session, status_value=JobStatus.CLOSED)
    await _make_match(session, applicant_id=applicant.id, job_id=j.id, total_score=0.9)
    await session.commit()

    resp = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.integration
async def test_feed_excludes_soft_deleted_jobs(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, applicant = await _make_applicant(session, email="softdel@example.com")
    j, _ = await _make_job_and_employer(session)
    j.deleted_at = datetime.now(UTC)
    await _make_match(session, applicant_id=applicant.id, job_id=j.id, total_score=0.9)
    await session.commit()

    resp = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.integration
async def test_feed_pagination(session: AsyncSession, async_client: AsyncClient) -> None:
    user, applicant = await _make_applicant(session, email="page@example.com")
    scores = [0.9, 0.8, 0.7, 0.6, 0.5]
    for i, sc in enumerate(scores):
        j, _ = await _make_job_and_employer(session, title=f"J{i}", employer_name=f"E{i}")
        await _make_match(session, applicant_id=applicant.id, job_id=j.id, total_score=sc)
    await session.commit()

    # Page 1
    resp = await async_client.get("/v1/feed?limit=2", headers=_token_headers(user))
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None
    titles_page1 = [it["job"]["title"] for it in body["items"]]

    # Page 2
    resp = await async_client.get(
        f"/v1/feed?limit=2&cursor={body['next_cursor']}",
        headers=_token_headers(user),
    )
    body2 = resp.json()
    assert len(body2["items"]) == 2
    assert body2["next_cursor"] is not None
    titles_page2 = [it["job"]["title"] for it in body2["items"]]

    # Page 3
    resp = await async_client.get(
        f"/v1/feed?limit=2&cursor={body2['next_cursor']}",
        headers=_token_headers(user),
    )
    body3 = resp.json()
    assert len(body3["items"]) == 1
    assert body3["next_cursor"] is None

    all_titles = titles_page1 + titles_page2 + [it["job"]["title"] for it in body3["items"]]
    # Highest-score first
    assert all_titles == ["J0", "J1", "J2", "J3", "J4"]


@pytest.mark.integration
async def test_feed_invalid_cursor_returns_400(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="invcur@example.com")
    await session.commit()
    resp = await async_client.get("/v1/feed?cursor=not_base64!!!", headers=_token_headers(user))
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_cursor"


@pytest.mark.integration
async def test_feed_limit_out_of_range_returns_validation_error(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, _ = await _make_applicant(session, email="lim@example.com")
    await session.commit()
    # FastAPI's Query(ge=1, le=50) returns 422; the error-handler middleware
    # converts that to RFC 7807 with a problem+json body.
    resp = await async_client.get("/v1/feed?limit=200", headers=_token_headers(user))
    assert resp.status_code in (400, 422)


@pytest.mark.integration
async def test_feed_missing_token_returns_401(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    resp = await async_client.get("/v1/feed")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_feed_recruiter_token_returns_403(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user = User(email="rec-feed@example.com", role=UserRole.RECRUITER)
    session.add(user)
    await session.commit()
    resp = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"


@pytest.mark.integration
async def test_feed_etag_round_trip_returns_304(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, applicant = await _make_applicant(session, email="etag304@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="EtagCo")
    await _make_match(session, applicant_id=applicant.id, job_id=j.id, total_score=0.9)
    await session.commit()

    r1 = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert r1.status_code == 200
    etag = r1.headers["ETag"]

    r2 = await async_client.get(
        "/v1/feed",
        headers={**_token_headers(user), "If-None-Match": etag},
    )
    assert r2.status_code == 304
    assert r2.content == b""


@pytest.mark.integration
async def test_feed_etag_changes_on_match_update(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, applicant = await _make_applicant(session, email="etagchg@example.com")
    j, _ = await _make_job_and_employer(session, employer_name="EtagChgCo")
    m = await _make_match(session, applicant_id=applicant.id, job_id=j.id, total_score=0.9)
    await session.commit()

    r1 = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert r1.status_code == 200
    etag_before = r1.headers["ETag"]

    # Mutate the match — bump score and updated_at so the ETag key changes.
    m.total_score = Decimal("0.95")
    m.updated_at = datetime.now(UTC)
    await session.commit()

    r2 = await async_client.get(
        "/v1/feed",
        headers={**_token_headers(user), "If-None-Match": etag_before},
    )
    assert r2.status_code == 200
    assert r2.headers["ETag"] != etag_before


@pytest.mark.integration
async def test_feed_soft_deleted_applicant_gets_500(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """A tombstoned (DSR-scrubbed) applicant row must not be resolvable.

    Pins the `deleted_at IS NULL` filter in the applicant guard — without it,
    a user inside the access-token TTL window after a DSR delete could still
    reach the feed via their scrubbed applicant row.
    """
    user, applicant = await _make_applicant(session, email="tombstone@example.com")
    applicant.deleted_at = datetime.now(UTC)
    await session.commit()

    r = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert r.status_code == 500
    assert r.json()["detail"] == "applicant_missing"
