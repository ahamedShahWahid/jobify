"""Integration tests for GET /v1/notifications and POST /v1/notifications/{id}/read."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.tokens import mint_access_token
from jobify.db.models import (
    Applicant,
    Notification,
    NotificationChannel,
    NotificationStatus,
    User,
    UserRole,
)

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_applicant(
    session: AsyncSession, email: str = "notif@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Notif Test", locations=["Bangalore"])
    session.add(applicant)
    await session.flush()
    return user, applicant


def _token_headers(user: User) -> dict[str, str]:
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    return {"Authorization": f"Bearer {token}"}


async def _make_notification(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str = "application_received",
    channel: NotificationChannel = NotificationChannel.IN_APP,
    status: NotificationStatus = NotificationStatus.PENDING,
    payload: dict | None = None,
    read_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        kind=kind,
        channel=channel,
        status=status,
        payload=payload or {"kind": kind},
        read_at=read_at,
        deleted_at=deleted_at,
    )
    session.add(notif)
    await session.flush()
    return notif


# ---------------------------------------------------------------------------
# GET /v1/notifications tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_inbox_returns_users_notifications(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Pending, dispatching, and sent notifications for the current user are returned."""
    user, _ = await _make_applicant(session, email="inbox-returns@example.com")
    await _make_notification(session, user_id=user.id, status=NotificationStatus.PENDING)
    await _make_notification(session, user_id=user.id, status=NotificationStatus.DISPATCHING)
    await _make_notification(session, user_id=user.id, status=NotificationStatus.SENT)
    await session.commit()

    resp = await async_client.get("/v1/notifications", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    assert body["next_cursor"] is None
    # Each item has a "notification" key.
    for item in body["items"]:
        assert "notification" in item
        assert item["notification"]["kind"] == "application_received"


@pytest.mark.integration
async def test_inbox_excludes_other_users(session: AsyncSession, async_client: AsyncClient) -> None:
    """Notifications belonging to another user are not returned."""
    user_a, _ = await _make_applicant(session, email="inbox-a@example.com")
    user_b, _ = await _make_applicant(session, email="inbox-b@example.com")
    # Create one notification for B, none for A.
    await _make_notification(session, user_id=user_b.id, status=NotificationStatus.PENDING)
    await session.commit()

    resp = await async_client.get("/v1/notifications", headers=_token_headers(user_a))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 0


@pytest.mark.integration
async def test_inbox_excludes_failed(session: AsyncSession, async_client: AsyncClient) -> None:
    """FAILED notifications are excluded from the inbox (admin-only)."""
    user, _ = await _make_applicant(session, email="inbox-failed@example.com")
    await _make_notification(session, user_id=user.id, status=NotificationStatus.SENT)
    await _make_notification(session, user_id=user.id, status=NotificationStatus.FAILED)
    await session.commit()

    resp = await async_client.get("/v1/notifications", headers=_token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    # Only the SENT row should appear.
    assert len(body["items"]) == 1
    assert body["items"][0]["notification"]["status"] == "sent"


@pytest.mark.integration
async def test_inbox_pagination(session: AsyncSession, async_client: AsyncClient) -> None:
    """Cursor pagination returns items in correct order and produces a next_cursor."""
    user, _ = await _make_applicant(session, email="inbox-page@example.com")
    # Insert 3 notifications.
    for i in range(3):
        await _make_notification(
            session,
            user_id=user.id,
            kind=f"kind_{i}",
            status=NotificationStatus.PENDING,
        )
    await session.commit()

    # First page — limit=2.
    r1 = await async_client.get("/v1/notifications?limit=2", headers=_token_headers(user))
    assert r1.status_code == 200
    b1 = r1.json()
    assert len(b1["items"]) == 2
    assert b1["next_cursor"] is not None

    # Second page — use cursor from first page.
    r2 = await async_client.get(
        f"/v1/notifications?limit=2&cursor={b1['next_cursor']}",
        headers=_token_headers(user),
    )
    assert r2.status_code == 200
    b2 = r2.json()
    assert len(b2["items"]) == 1
    assert b2["next_cursor"] is None

    # Combined IDs cover all 3 unique notifications.
    ids_1 = {item["notification"]["id"] for item in b1["items"]}
    ids_2 = {item["notification"]["id"] for item in b2["items"]}
    assert len(ids_1 | ids_2) == 3


@pytest.mark.integration
async def test_inbox_etag_round_trip(session: AsyncSession, async_client: AsyncClient) -> None:
    """Second request with If-None-Match matching the ETag returns 304."""
    user, _ = await _make_applicant(session, email="inbox-etag@example.com")
    await _make_notification(session, user_id=user.id, status=NotificationStatus.SENT)
    await session.commit()

    r1 = await async_client.get("/v1/notifications", headers=_token_headers(user))
    assert r1.status_code == 200
    etag = r1.headers["etag"]
    assert etag.startswith('W/"')

    r2 = await async_client.get(
        "/v1/notifications",
        headers={**_token_headers(user), "If-None-Match": etag},
    )
    assert r2.status_code == 304


# ---------------------------------------------------------------------------
# POST /v1/notifications/{id}/read tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_mark_read_sets_read_at(session: AsyncSession, async_client: AsyncClient) -> None:
    """Mark-read sets read_at and returns the updated notification."""
    user, _ = await _make_applicant(session, email="mark-read@example.com")
    notif = await _make_notification(session, user_id=user.id, status=NotificationStatus.SENT)
    await session.commit()

    assert notif.read_at is None

    resp = await async_client.post(
        f"/v1/notifications/{notif.id}/read",
        headers=_token_headers(user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(notif.id)
    assert body["read_at"] is not None

    # Verify in DB.
    await session.refresh(notif)
    assert notif.read_at is not None


@pytest.mark.integration
async def test_mark_read_idempotent(session: AsyncSession, async_client: AsyncClient) -> None:
    """Calling mark-read twice on an already-read notification returns 200 both times."""
    user, _ = await _make_applicant(session, email="mark-read-idem@example.com")
    notif = await _make_notification(
        session,
        user_id=user.id,
        status=NotificationStatus.SENT,
        read_at=datetime.now(UTC),
    )
    await session.commit()

    r1 = await async_client.post(
        f"/v1/notifications/{notif.id}/read",
        headers=_token_headers(user),
    )
    assert r1.status_code == 200
    first_read_at = r1.json()["read_at"]

    r2 = await async_client.post(
        f"/v1/notifications/{notif.id}/read",
        headers=_token_headers(user),
    )
    assert r2.status_code == 200
    # read_at must not change on a second call.
    assert r2.json()["read_at"] == first_read_at


@pytest.mark.integration
async def test_mark_read_other_user_returns_404(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Trying to mark another user's notification as read returns 404."""
    user_a, _ = await _make_applicant(session, email="mark-read-a@example.com")
    user_b, _ = await _make_applicant(session, email="mark-read-b@example.com")
    notif_b = await _make_notification(
        session, user_id=user_b.id, status=NotificationStatus.PENDING
    )
    await session.commit()

    resp = await async_client.post(
        f"/v1/notifications/{notif_b.id}/read",
        headers=_token_headers(user_a),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "notification_not_found"
