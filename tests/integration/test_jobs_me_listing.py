from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Applicant, Application, ApplicationStatus, Match, User, UserRole

pytestmark = pytest.mark.integration


async def _setup_employer(async_client, token):
    emp = await async_client.post(
        "/v1/employers", json={"name": "Acme"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert emp.status_code == 201
    return emp.json()["id"]


async def _create_job(async_client, token, emp_id, title):
    body = {
        "employer_id": emp_id,
        "title": title,
        "description": "Build distributed systems." * 2,
        "locations": ["Bangalore"],
        "min_exp_years": 1,
        "max_exp_years": 5,
    }
    r = await async_client.post("/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_me_lists_my_jobs(async_client, applicant_user_and_token):
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    ids = [await _create_job(async_client, token, emp_id, f"Role {i}") for i in range(3)]

    r = await async_client.get("/v1/jobs/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    returned_ids = [j["id"] for j in body["items"]]
    assert set(returned_ids) == set(ids)
    for row in body["items"]:
        assert row["applicant_count"] == 0
        assert row["surfaced_match_count"] == 0
        # JobRead.employer_verified field flows through
        assert row["employer_verified"] is False


async def test_me_hides_closed_by_default_shows_with_filter(async_client, applicant_user_and_token):
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    open_id = await _create_job(async_client, token, emp_id, "Open Role")
    closing_id = await _create_job(async_client, token, emp_id, "Closing Role")
    await async_client.patch(
        f"/v1/jobs/{closing_id}",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {token}"},
    )

    r1 = await async_client.get("/v1/jobs/me", headers={"Authorization": f"Bearer {token}"})
    assert [j["id"] for j in r1.json()["items"]] == [open_id]

    r2 = await async_client.get(
        "/v1/jobs/me?status=closed", headers={"Authorization": f"Bearer {token}"}
    )
    returned = set(j["id"] for j in r2.json()["items"])
    assert returned == {open_id, closing_id}


async def test_me_pagination(async_client, applicant_user_and_token):
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    ids = [await _create_job(async_client, token, emp_id, f"Role {i}") for i in range(5)]

    r1 = await async_client.get("/v1/jobs/me?limit=2", headers={"Authorization": f"Bearer {token}"})
    body1 = r1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    r2 = await async_client.get(
        f"/v1/jobs/me?limit=2&cursor={body1['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    body2 = r2.json()
    assert len(body2["items"]) == 2
    assert body2["next_cursor"] is not None

    r3 = await async_client.get(
        f"/v1/jobs/me?limit=2&cursor={body2['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    body3 = r3.json()
    assert len(body3["items"]) == 1
    assert body3["next_cursor"] is None

    # Pages do not overlap
    seen = (
        [j["id"] for j in body1["items"]]
        + [j["id"] for j in body2["items"]]
        + [j["id"] for j in body3["items"]]
    )
    assert set(seen) == set(ids)


async def _make_other_applicant(session: AsyncSession, email: str) -> Applicant:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Counts Test")
    session.add(applicant)
    await session.flush()
    return applicant


async def test_me_counts_reflect_applications_and_surfaced_matches(
    async_client, applicant_user_and_token, session: AsyncSession
):
    """applicant_count/surfaced_match_count are correlated-subquery counts now
    (PERF-02: the old outer-join + DISTINCT query multiplied applications x
    matches per job before GROUP BY). Two applicants each with one application
    AND one match against the same job would return applicant_count=4 under a
    naive (non-distinct) join rewrite — this pins the real filtered count.
    """
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    job_id = await _create_job(async_client, token, emp_id, "Counted Role")

    applied = await _make_other_applicant(session, "counts-applied@example.com")
    withdrawn = await _make_other_applicant(session, "counts-withdrawn@example.com")
    surfaced_applicant = await _make_other_applicant(session, "counts-surfaced@example.com")
    unsurfaced_applicant = await _make_other_applicant(session, "counts-unsurfaced@example.com")

    session.add_all(
        [
            Application(applicant_id=applied.id, job_id=job_id, status=ApplicationStatus.APPLIED),
            Application(
                applicant_id=withdrawn.id, job_id=job_id, status=ApplicationStatus.WITHDRAWN
            ),
            Match(
                applicant_id=surfaced_applicant.id,
                job_id=job_id,
                vector_score=0.9,
                structured_score=0.9,
                total_score=0.9,
                score_components={},
                model_versions={},
                surfaced_at=datetime.now(UTC),
            ),
            Match(
                applicant_id=unsurfaced_applicant.id,
                job_id=job_id,
                vector_score=0.2,
                structured_score=0.2,
                total_score=0.2,
                score_components={},
                model_versions={},
                surfaced_at=None,
            ),
        ]
    )
    await session.commit()

    r = await async_client.get("/v1/jobs/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    row = next(j for j in r.json()["items"] if j["id"] == job_id)
    assert row["applicant_count"] == 1  # only the APPLIED row counts, not WITHDRAWN
    assert row["surfaced_match_count"] == 1  # only the surfaced match counts


async def test_me_applicant_returns_403(async_client, applicant_user_and_token):
    _, token = applicant_user_and_token
    r = await async_client.get("/v1/jobs/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"


async def test_me_rejects_unknown_status_filter(async_client, applicant_user_and_token):
    """?status only accepts "open"/"closed" — anything else is a 422.

    Pins the fail-closed contract: an unknown value must NOT silently bypass
    the default open-only filter.
    """
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    await _create_job(async_client, token, emp_id, "Role X")

    r = await async_client.get(
        "/v1/jobs/me?status=banana", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 422
