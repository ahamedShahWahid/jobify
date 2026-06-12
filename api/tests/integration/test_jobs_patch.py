from __future__ import annotations

import pytest

import jobify.workers.tasks.embed_job as _embed_job_mod

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


class _RecordingStub:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def delay(self, job_id: str) -> None:
        self.calls.append(job_id)


async def test_patch_content_field_redispatches_embed(
    async_client, applicant_user_and_token, monkeypatch
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    stub = _RecordingStub()
    monkeypatch.setattr(_embed_job_mod, "embed_job", stub, raising=False)

    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"title": "Renamed Role"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Renamed Role"
    assert stub.calls == [job_id]


async def test_patch_status_only_does_not_redispatch_embed(
    async_client, applicant_user_and_token, monkeypatch
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    stub = _RecordingStub()
    monkeypatch.setattr(_embed_job_mod, "embed_job", stub, raising=False)

    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"
    assert stub.calls == []


async def test_patch_combined_content_and_status_redispatches_once(
    async_client, applicant_user_and_token, monkeypatch
):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    stub = _RecordingStub()
    monkeypatch.setattr(_embed_job_mod, "embed_job", stub, raising=False)

    r = await async_client.patch(
        f"/v1/jobs/{job_id}",
        json={"title": "New Title", "status": "closed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert stub.calls == [job_id]


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


async def test_patch_other_employer_returns_404(async_client, session, applicant_user_and_token):
    _, token = applicant_user_and_token
    _, job_id = await _make_recruiter_and_job(async_client, token)

    # Second recruiter from a different employer
    from jobify.auth.tokens import mint_access_token
    from jobify.db.models import User, UserRole

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
