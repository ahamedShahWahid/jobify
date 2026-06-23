"""Wire-shape contract tests.

These tests pin down the exact JSON key sets of the responses the Flutter
client reads, so that any future backend field rename / drop / addition is
caught at CI time — not when the Flutter app silently parses a field as
null (the failure mode that hid the "Apply button after applying" bug).

Each test seeds a minimal happy-path fixture, hits the endpoint, and
asserts ``set(body[...].keys()) == EXPECTED``. If the backend response
shape changes legitimately, **the Flutter DTO must change in the same PR**
— failing this test is the signal.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


# ---------------------------------------------------------------------------
# Expected key sets — bumping any of these is a wire-contract change.
# When you bump one, bump the matching Flutter DTO in the SAME PR.
# ---------------------------------------------------------------------------

# routes/feed.py
_JOB_READ_KEYS = {
    "id",
    "title",
    "description",
    "locations",
    "min_exp_years",
    "max_exp_years",
    "ctc_min",
    "ctc_max",
    "status",
    "posted_at",
    "employer_verified",
}
_EMPLOYER_READ_KEYS = {"id", "name", "verified"}
_MATCH_READ_KEYS = {
    "id",
    "total_score",
    "vector_score",
    "structured_score",
    # DB column is score_components; wire shape is `components` (see MatchRead
    # in routes/feed.py — Pydantic validation_alias renames it on parse but
    # the OUTPUT key is the field name). The Flutter MatchSummaryDto uses
    # @JsonKey(name: 'components').
    "components",
    "explanation",
    "surfaced_at",
}

# Slim DTOs introduced for JobDetailResponse (PR #23).
_JOB_DETAIL_APPLICATION_KEYS = {
    "id",
    "job_id",
    "status",
    "source",
    "created_at",
    "updated_at",
}
_JOB_DETAIL_SAVED_JOB_KEYS = {
    "id",
    "job_id",
    "created_at",
    "updated_at",
}

# routes/applications.py
_APPLICATION_READ_KEYS = {
    "id",
    "job_id",
    "status",
    "source",
    "created_at",
    "updated_at",
}

# routes/saved_jobs.py
_SAVED_JOB_READ_KEYS = {
    "id",
    "job_id",
    "created_at",
    "updated_at",
}

# Page / item / detail envelopes.
_FEED_ITEM_KEYS = {"match", "job", "employer"}
_FEED_PAGE_KEYS = {"items", "next_cursor"}

_APPLICATION_LIST_ITEM_KEYS = {"application", "job", "employer"}
_APPLICATION_LIST_PAGE_KEYS = {"items", "next_cursor"}

_SAVED_LIST_ITEM_KEYS = {"saved_job", "job", "employer"}
_SAVED_LIST_PAGE_KEYS = {"items", "next_cursor"}

_JOB_DETAIL_KEYS = {"job", "employer", "match", "application", "saved_job"}


# ---------------------------------------------------------------------------
# Helpers (mirror the patterns in the other integration test files)
# ---------------------------------------------------------------------------


async def _make_applicant(session: AsyncSession, email: str) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Wire Shape", locations=["Bangalore"])
    session.add(applicant)
    await session.flush()
    return user, applicant


async def _make_job_and_employer(
    session: AsyncSession,
    *,
    employer_name: str,
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
        title="Wire Shape Engineer",
        description="x" * 20,
        locations=["Bangalore"],
        min_exp_years=1,
        max_exp_years=5,
        status=JobStatus.OPEN,
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


# ---------------------------------------------------------------------------
# /v1/feed
# ---------------------------------------------------------------------------


async def test_feed_wire_shape(session: AsyncSession, async_client: AsyncClient) -> None:
    user, applicant = await _make_applicant(session, email="ws-feed@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="WsFeedCo")
    session.add(
        Match(
            applicant_id=applicant.id,
            job_id=job.id,
            vector_score=0.8,
            structured_score=0.8,
            total_score=0.8,
            score_components={"location": 1.0, "exp": 1.0, "ctc": 0.4},
            model_versions={},
            surfaced_at=datetime.now(UTC),
            explanation={
                "fit": "ok",
                "caveat": "",
                "generator": "templated",
                "generator_version": "1",
            },
        )
    )
    await session.commit()

    resp = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == _FEED_PAGE_KEYS
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert set(item.keys()) == _FEED_ITEM_KEYS
    assert set(item["job"].keys()) == _JOB_READ_KEYS
    assert set(item["employer"].keys()) == _EMPLOYER_READ_KEYS
    assert set(item["match"].keys()) == _MATCH_READ_KEYS


# ---------------------------------------------------------------------------
# /v1/applications
# ---------------------------------------------------------------------------


async def test_applications_list_wire_shape(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    user, applicant = await _make_applicant(session, email="ws-apps@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="WsAppsCo")
    session.add(
        Application(
            applicant_id=applicant.id,
            job_id=job.id,
            status="applied",
            source="feed",
        )
    )
    await session.commit()

    resp = await async_client.get("/v1/applications", headers=_token_headers(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == _APPLICATION_LIST_PAGE_KEYS
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert set(item.keys()) == _APPLICATION_LIST_ITEM_KEYS
    assert set(item["application"].keys()) == _APPLICATION_READ_KEYS
    assert set(item["job"].keys()) == _JOB_READ_KEYS
    assert set(item["employer"].keys()) == _EMPLOYER_READ_KEYS


# ---------------------------------------------------------------------------
# /v1/saved
# ---------------------------------------------------------------------------


async def test_saved_list_wire_shape(session: AsyncSession, async_client: AsyncClient) -> None:
    user, applicant = await _make_applicant(session, email="ws-saved@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="WsSavedCo")
    session.add(SavedJob(applicant_id=applicant.id, job_id=job.id))
    await session.commit()

    resp = await async_client.get("/v1/saved", headers=_token_headers(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == _SAVED_LIST_PAGE_KEYS
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert set(item.keys()) == _SAVED_LIST_ITEM_KEYS
    assert set(item["saved_job"].keys()) == _SAVED_JOB_READ_KEYS
    assert set(item["job"].keys()) == _JOB_READ_KEYS
    assert set(item["employer"].keys()) == _EMPLOYER_READ_KEYS


# ---------------------------------------------------------------------------
# /v1/jobs/{id}
# ---------------------------------------------------------------------------


async def test_job_detail_wire_shape_with_all_optional_fields_populated(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Most-populated path: match + application + saved_job all present.

    Verifies the *full* surface; the nullable-fields-absent path is covered
    by the existing test_job_detail.py cases.
    """
    user, applicant = await _make_applicant(session, email="ws-detail@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="WsDetailCo")
    session.add(
        Match(
            applicant_id=applicant.id,
            job_id=job.id,
            vector_score=0.7,
            structured_score=0.7,
            total_score=0.7,
            score_components={"location": 1.0, "exp": 1.0, "ctc": 0.4},
            model_versions={},
            surfaced_at=datetime.now(UTC),
            explanation={
                "fit": "ok",
                "caveat": "",
                "generator": "templated",
                "generator_version": "1",
            },
        )
    )
    session.add(
        Application(
            applicant_id=applicant.id,
            job_id=job.id,
            status="applied",
            source="feed",
        )
    )
    session.add(SavedJob(applicant_id=applicant.id, job_id=job.id))
    await session.commit()

    resp = await async_client.get(f"/v1/jobs/{job.id}", headers=_token_headers(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == _JOB_DETAIL_KEYS
    assert set(body["job"].keys()) == _JOB_READ_KEYS
    assert set(body["employer"].keys()) == _EMPLOYER_READ_KEYS
    assert set(body["match"].keys()) == _MATCH_READ_KEYS
    assert set(body["application"].keys()) == _JOB_DETAIL_APPLICATION_KEYS
    assert set(body["saved_job"].keys()) == _JOB_DETAIL_SAVED_JOB_KEYS
