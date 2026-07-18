"""Integration tests for GET /v1/admin/audit-logs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import User, UserRole

pytestmark = pytest.mark.integration


async def _seed_audit_rows(session: AsyncSession, *, count: int = 5) -> User:
    """Make a user + N audit_logs rows tied to them."""
    user = User(email=f"u-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    for i in range(count):
        await audit_log(
            session,
            action=f"test.event_{i}",
            actor=user,
            resource_type="test",
            resource_id=uuid4(),
            context={"i": i},
        )
    return user


@pytest.mark.asyncio
async def test_audit_logs_returns_filtered_by_actor(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    actor = await _seed_audit_rows(session, count=3)
    # Noise: another user's audit rows.
    other = User(email=f"n-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(other)
    await session.flush()
    await audit_log(
        session,
        action="other.event",
        actor=other,
        resource_type="test",
    )
    await session.commit()

    resp = await async_client.get(
        f"/v1/admin/audit-logs?actor_user_id={actor.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    actions = sorted(it["action"] for it in body["items"])
    assert actions == ["test.event_0", "test.event_1", "test.event_2"]


@pytest.mark.asyncio
async def test_audit_logs_filtered_by_action(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    _user = await _seed_audit_rows(session, count=5)
    await session.commit()

    resp = await async_client.get(
        "/v1/admin/audit-logs?action=test.event_2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["action"] == "test.event_2"


@pytest.mark.asyncio
async def test_audit_logs_pagination(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    actor = await _seed_audit_rows(session, count=5)
    await session.commit()

    page1 = await async_client.get(
        f"/v1/admin/audit-logs?actor_user_id={actor.id}&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    page2 = await async_client.get(
        f"/v1/admin/audit-logs?actor_user_id={actor.id}&limit=2&cursor={body1['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["items"]) == 2
    # No overlap.
    page1_ids = {it["id"] for it in body1["items"]}
    page2_ids = {it["id"] for it in body2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_audit_logs_requires_admin(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _applicant, token = applicant_user_and_token
    resp = await async_client.get(
        "/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analytics_summary_aggregates_in_database(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    actor = User(email=f"analytics-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(actor)
    await session.flush()
    action = f"test.analytics.{uuid4().hex}"
    for _ in range(3):
        await audit_log(
            session,
            action=action,
            actor=actor,
            resource_type="test",
        )
    await session.commit()

    response = await async_client.get(
        "/v1/admin/analytics/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] >= 3
    assert body["distinct_actors"] >= 1
    assert body["last_24h"] >= 3
    assert {row["key"]: row["count"] for row in body["action_counts"]}[action] == 3
    assert sum(row["count"] for row in body["activity"]) == body["total_events"]
