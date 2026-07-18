from __future__ import annotations

import pytest
from sqlalchemy import select

from jobify.db.models import Job
from tests.integration.outbox_helpers import task_event_args

pytestmark = pytest.mark.integration


async def _make_recruiter_and_job(async_client, token):
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
    job_resp = await async_client.post(
        "/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert job_resp.status_code == 201, job_resp.text
    return emp.json()["id"], job_resp.json()["id"]


async def test_patch_content_field_redispatches_embed(
    async_client, applicant_user_and_token, session
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    before = len(await task_event_args(session, "jobify.embed_job"))

    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"title": "Renamed Role"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Renamed Role"
    events = await task_event_args(session, "jobify.embed_job")
    assert len(events) == before + 1
    assert events[-1] == [job_id]


async def test_patch_status_only_does_not_redispatch_embed(
    async_client, applicant_user_and_token, session
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    before = len(await task_event_args(session, "jobify.embed_job"))

    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"
    assert len(await task_event_args(session, "jobify.embed_job")) == before


async def test_patch_combined_content_and_status_redispatches_once(
    async_client, applicant_user_and_token, session
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    before = len(await task_event_args(session, "jobify.embed_job"))

    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"title": "New Title", "status": "closed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    events = await task_event_args(session, "jobify.embed_job")
    assert len(events) == before + 1
    assert events[-1] == [job_id]


async def test_patch_unknown_status_returns_422(async_client, applicant_user_and_token):
    """Pydantic Literal['open','closed'] rejects unknown values at the validation layer."""
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)
    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"status": "archived"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "field",
    ["title", "description", "locations", "min_exp_years", "max_exp_years", "status"],
)
async def test_patch_rejects_null_for_required_job_fields(
    async_client, applicant_user_and_token, field
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    response = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={field: None},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


async def test_patch_rejects_invalid_merged_experience_band(
    async_client, applicant_user_and_token, session
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    response = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"min_exp_years": 6},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    unchanged = await session.scalar(select(Job).where(Job.id == job_id))
    assert unchanged is not None
    assert unchanged.min_exp_years == 1
    assert unchanged.max_exp_years == 5


async def test_patch_other_employer_returns_404(async_client, session, applicant_user_and_token):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    # Second recruiter from a different employer
    from jobify.db.models import User, UserRole
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

    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"title": "Hijack"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 404
