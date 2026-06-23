from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from jobify.db.models import EmployerUser

pytestmark = pytest.mark.integration


async def test_me_returns_recruiters_employers(async_client, applicant_user_and_token):
    """A recruiter (post role-flip) sees every employer they're on."""
    _, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201, r1.text
    r2 = await async_client.post(
        "/v1/employers",
        json={"name": "Beta"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 201, r2.text

    r = await async_client.get(
        "/v1/employers/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    names = sorted(e["name"] for e in r.json())
    assert names == ["Acme", "Beta"]


async def test_me_returns_403_for_applicant(async_client, applicant_user_and_token):
    """An APPLICANT (no employer-create call yet) gets 403 not_a_recruiter."""
    _, token = applicant_user_and_token
    r = await async_client.get(
        "/v1/employers/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "not_a_recruiter"


async def test_me_excludes_soft_deleted_link(async_client, session, applicant_user_and_token):
    """If the employer_users link is soft-deleted, the employer is hidden from /me."""
    user, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201
    emp_id = r1.json()["id"]

    link = await session.scalar(
        select(EmployerUser).where(
            EmployerUser.employer_id == emp_id,
            EmployerUser.user_id == user.id,
        )
    )
    assert link is not None
    link.deleted_at = datetime.now(UTC)
    await session.commit()

    r = await async_client.get(
        "/v1/employers/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    # User's role is still RECRUITER (one-way), but no live links → empty list.
    assert r.status_code == 200
    assert r.json() == []
