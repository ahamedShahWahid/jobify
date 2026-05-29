"""Integration tests for GET + PATCH /v1/me/consents."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import mint_access_token
from kpa.consent import seed_default_consents
from kpa.db.models import DEFAULT_CONSENTS, AuditLog, User, UserRole

pytestmark = pytest.mark.integration


@pytest.fixture
async def applicant_with_consents(
    session: AsyncSession,
) -> tuple[User, str]:
    user = User(email=f"croute-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)
    await session.commit()  # commit the savepoint so async_client sees it
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, token


@pytest.mark.asyncio
async def test_get_consents_returns_all_seeded_scopes(
    async_client: AsyncClient, applicant_with_consents: tuple[User, str]
) -> None:
    _user, token = applicant_with_consents
    resp = await async_client.get(
        "/v1/me/consents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == len(DEFAULT_CONSENTS)
    by_scope = {it["scope"]: it["granted"] for it in body["items"]}
    for scope, default in DEFAULT_CONSENTS.items():
        assert by_scope[scope.value] is default


@pytest.mark.asyncio
async def test_patch_consent_flips_and_writes_audit(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_with_consents: tuple[User, str],
) -> None:
    user, token = applicant_with_consents
    resp = await async_client.patch(
        "/v1/me/consents/email_marketing",
        headers={"Authorization": f"Bearer {token}"},
        json={"granted": True},
    )
    assert resp.status_code == 200
    assert resp.json()["granted"] is True

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,
                    AuditLog.action == "consent.granted",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].context["scope"] == "email_marketing"


@pytest.mark.asyncio
async def test_patch_consent_unknown_scope_returns_422(
    async_client: AsyncClient, applicant_with_consents: tuple[User, str]
) -> None:
    _user, token = applicant_with_consents
    resp = await async_client.patch(
        "/v1/me/consents/not_a_real_scope",
        headers={"Authorization": f"Bearer {token}"},
        json={"granted": True},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_consent_extra_field_returns_422(
    async_client: AsyncClient, applicant_with_consents: tuple[User, str]
) -> None:
    _user, token = applicant_with_consents
    resp = await async_client.patch(
        "/v1/me/consents/email_marketing",
        headers={"Authorization": f"Bearer {token}"},
        json={"granted": True, "extra": "nope"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_consent_requires_auth(async_client: AsyncClient) -> None:
    resp = await async_client.patch("/v1/me/consents/email_marketing", json={"granted": True})
    assert resp.status_code == 401
