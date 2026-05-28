from __future__ import annotations

import pytest
from sqlalchemy import select

from kpa.db.models import Employer, Job

pytestmark = pytest.mark.integration


async def test_create_job_happy_path(async_client, session, applicant_user_and_token):
    _, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201
    emp_id = r1.json()["id"]

    body = {
        "employer_id": emp_id,
        "title": "Senior Python Engineer",
        "description": "Build distributed systems in Python and Postgres.",
        "locations": ["Bangalore", "Remote"],
        "min_exp_years": 4,
        "max_exp_years": 8,
        "ctc_min": 2000000,
        "ctc_max": 4000000,
    }
    r = await async_client.post(
        "/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    job = await session.scalar(select(Job).where(Job.id == job_id))
    assert job is not None
    assert job.title == "Senior Python Engineer"
    assert job.status.value == "open"


async def test_create_job_not_at_employer_returns_404(
    async_client, session, applicant_user_and_token
):
    """Recruiter cannot post to an employer they're not on (uniform 404)."""
    user, token = applicant_user_and_token
    # User becomes recruiter at Acme
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201

    # Another employer exists, created out-of-band
    other_emp = Employer(name="Other Co", name_norm="other co")
    session.add(other_emp)
    await session.flush()

    body = {
        "employer_id": str(other_emp.id),
        "title": "Hijack",
        "description": "X" * 50,
        "locations": ["A"],
        "min_exp_years": 0,
        "max_exp_years": 1,
    }
    r = await async_client.post(
        "/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 404


async def test_create_job_not_a_recruiter_returns_403(
    async_client, applicant_user_and_token
):
    _, token = applicant_user_and_token
    body = {
        "employer_id": "00000000-0000-0000-0000-000000000000",
        "title": "X",
        "description": "Y" * 50,
        "locations": ["A"],
        "min_exp_years": 0,
        "max_exp_years": 1,
    }
    r = await async_client.post(
        "/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"


async def test_create_job_invalid_exp_band_returns_422(
    async_client, applicant_user_and_token
):
    _, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    emp_id = r1.json()["id"]
    body = {
        "employer_id": emp_id,
        "title": "X",
        "description": "Y" * 50,
        "locations": ["A"],
        "min_exp_years": 5,
        "max_exp_years": 2,  # max < min
    }
    r = await async_client.post(
        "/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 422


async def test_create_job_dispatches_embed(
    async_client, applicant_user_and_token, monkeypatch
):
    """The route must fire-and-forget embed_job.delay(job_id_str) after commit."""
    _, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    emp_id = r1.json()["id"]

    called_with: list[str] = []

    class _Stub:
        def delay(self, job_id: str) -> None:
            called_with.append(job_id)

    import kpa.routes.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod, "embed_job", _Stub())

    body = {
        "employer_id": emp_id,
        "title": "T",
        "description": "D" * 50,
        "locations": ["A"],
        "min_exp_years": 1,
        "max_exp_years": 3,
    }
    r = await async_client.post(
        "/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 201
    assert called_with == [r.json()["id"]]
