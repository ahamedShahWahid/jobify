from __future__ import annotations

import pytest
from sqlalchemy import select

from jobify.db.models import EmployerUser, User, UserRole

pytestmark = pytest.mark.integration


async def test_create_employer_happy_path_flips_role(
    async_client, session, applicant_user_and_token
):
    """Sign-in defaulted role=APPLICANT; POST /v1/employers flips it to RECRUITER."""
    user, token = applicant_user_and_token

    resp = await async_client.post(
        "/v1/employers",
        json={"name": "Acme Corp", "gst": "29ABCDE1234F1Z5"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Acme Corp"
    assert body["gst"] == "29ABCDE1234F1Z5"
    assert body["verified_at"] is None

    # Side effect: user.role flipped to RECRUITER
    refreshed_role = await session.scalar(select(User.role).where(User.id == user.id))
    assert refreshed_role == UserRole.RECRUITER

    link = await session.scalar(
        select(EmployerUser.id).where(
            EmployerUser.user_id == user.id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    assert link is not None


async def test_create_employer_duplicate_name_returns_409(
    async_client, session, applicant_user_and_token
):
    """A second user attempting the same employer name (after normalization) gets 409."""
    _, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme Corp"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201, r1.text

    # Second user attempts the same name
    from jobify.auth.tokens import mint_access_token
    from jobify.db.models import User, UserRole

    other = User(email="other@example.com", role=UserRole.APPLICANT)
    session.add(other)
    await session.flush()
    other_token = mint_access_token(
        user_id=other.id,
        role=other.role.value,
        secret="x" * 32,
        ttl_seconds=600,
    )

    r2 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme Corp"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"] == "employer_name_taken"


async def test_create_employer_normalizes_name_for_dedup(
    async_client, session, applicant_user_and_token
):
    """Server-side normalization (lowercase + collapse whitespace) is enforced for dedup."""
    user, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme   Corp"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201, r1.text

    # Same name, different casing/whitespace, from the SAME user: must still 409
    # (a recruiter can create multiple employers but not duplicate normalized names).
    r2 = await async_client.post(
        "/v1/employers",
        json={"name": "  acme corp "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409


async def test_create_employer_unauthenticated_returns_401(async_client):
    r = await async_client.post("/v1/employers", json={"name": "Acme"})
    assert r.status_code == 401


async def test_create_employer_recruiter_can_create_second_employer(
    async_client, session, applicant_user_and_token
):
    """A recruiter (after a first POST flipped their role) can post a second employer."""
    user, token = applicant_user_and_token
    r1 = await async_client.post(
        "/v1/employers",
        json={"name": "Acme Corp"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201, r1.text

    r2 = await async_client.post(
        "/v1/employers",
        json={"name": "Beta Co"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 201, r2.text

    from sqlalchemy import func as sa_func

    n = await session.scalar(
        select(sa_func.count(EmployerUser.id)).where(
            EmployerUser.user_id == user.id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    assert n == 2
