"""Integration tests for /v1/admin/users/{id}/suspend (POST + DELETE)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import AuditLog, User, UserRole
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration


async def _make_user(session: AsyncSession, role: UserRole = UserRole.APPLICANT) -> User:
    user = User(email=f"u-{uuid4().hex[:8]}@example.com", role=role)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_suspend_user_happy_path(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    target = await _make_user(session)
    await session.commit()

    resp = await async_client.post(
        f"/v1/admin/users/{target.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "spam_signup"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suspended_at"] is not None
    assert body["suspension_reason"] == "spam_signup"

    refreshed = (await session.execute(select(User).where(User.id == target.id))).scalar_one()
    assert refreshed.suspended_at is not None
    assert refreshed.suspension_reason == "spam_signup"

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == admin.id,
                    AuditLog.action == "admin.user.suspended",
                    AuditLog.resource_id == target.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].context["reason"] == "spam_signup"


@pytest.mark.asyncio
async def test_suspend_self_blocked(
    async_client: AsyncClient,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    resp = await async_client.post(
        f"/v1/admin/users/{admin.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "oops"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "cannot_suspend_self"


@pytest.mark.asyncio
async def test_suspend_unknown_user_404(
    async_client: AsyncClient,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    resp = await async_client.post(
        f"/v1/admin/users/{uuid4()}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suspend_requires_admin_role(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _applicant, token = applicant_user_and_token
    resp = await async_client.post(
        f"/v1/admin/users/{uuid4()}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_admin"


@pytest.mark.asyncio
async def test_suspended_user_gets_401_user_suspended_on_subsequent_request(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, admin_token = admin_user_and_token

    # Make a victim user with their own token.
    victim = await _make_user(session)
    victim_token = mint_access_token(
        user_id=victim.id, role=victim.role.value, secret="x" * 32, ttl_seconds=600
    )
    await session.commit()

    # Suspend victim via admin.
    suspend_resp = await async_client.post(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "abuse"},
    )
    assert suspend_resp.status_code == 200

    # Victim hits an authenticated endpoint with their token → 401 user_suspended.
    me_resp = await async_client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {victim_token}"},
    )
    assert me_resp.status_code == 401
    assert me_resp.json()["detail"] == "user_suspended"


@pytest.mark.asyncio
async def test_unsuspend_user_clears_and_audits(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    victim = await _make_user(session)
    await session.commit()

    await async_client.post(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "abuse"},
    )

    resp = await async_client.delete(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["suspended_at"] is None
    assert resp.json()["suspension_reason"] is None

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == admin.id,
                    AuditLog.action == "admin.user.unsuspended",
                    AuditLog.resource_id == victim.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_unsuspend_already_active_is_noop_no_audit(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    victim = await _make_user(session)
    await session.commit()

    resp = await async_client.delete(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == admin.id,
                    AuditLog.action == "admin.user.unsuspended",
                )
            )
        )
        .scalars()
        .all()
    )
    assert audits == []
