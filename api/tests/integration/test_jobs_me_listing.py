from __future__ import annotations

import pytest

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
    r = await async_client.post(
        "/v1/jobs", json=body, headers={"Authorization": f"Bearer {token}"}
    )
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


async def test_me_hides_closed_by_default_shows_with_filter(
    async_client, applicant_user_and_token
):
    _, token = applicant_user_and_token
    emp_id = await _setup_employer(async_client, token)
    open_id = await _create_job(async_client, token, emp_id, "Open Role")
    closing_id = await _create_job(async_client, token, emp_id, "Closing Role")
    await async_client.patch(
        f"/v1/jobs/{closing_id}",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {token}"},
    )

    r1 = await async_client.get(
        "/v1/jobs/me", headers={"Authorization": f"Bearer {token}"}
    )
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

    r1 = await async_client.get(
        "/v1/jobs/me?limit=2", headers={"Authorization": f"Bearer {token}"}
    )
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


async def test_me_applicant_returns_403(async_client, applicant_user_and_token):
    _, token = applicant_user_and_token
    r = await async_client.get("/v1/jobs/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"
