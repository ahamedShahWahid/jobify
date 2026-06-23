"""Notification inbox endpoints.

GET  /v1/notifications                     — paginated inbox for current applicant.
POST /v1/notifications/{notification_id}/read — mark a notification as read.

Cursor format: base64 of {"created_at": ISO8601, "notification_id": uuid}.
Ordering: created_at DESC, id DESC.
ETag: W/"sha256(user_id|max_updated_at|count)".

Inbox shows pending, dispatching, sent rows only. failed is admin-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Notification,
    NotificationStatus,
    User,
)
from jobify_api.auth.dependencies import (
    current_user,
)
from jobify_api.auth.dependencies import (
    require_applicant as _require_applicant,
)
from jobify_api.dependencies import get_session
from jobify_api.pagination import decode_cursor, encode_cursor, make_weak_etag

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["notifications"])

# ---------------------------------------------------------------------------
# Pydantic shapes
# ---------------------------------------------------------------------------

_INBOX_STATUSES = (
    NotificationStatus.PENDING,
    NotificationStatus.DISPATCHING,
    NotificationStatus.SENT,
)


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    channel: str
    status: str
    payload: dict[str, object]
    send_after: datetime
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class NotificationListItem(BaseModel):
    notification: NotificationRead


class NotificationListResponse(BaseModel):
    items: list[NotificationListItem]
    next_cursor: str | None


# ---------------------------------------------------------------------------
# Cursor helpers (keyed on created_at + notification_id)
# ---------------------------------------------------------------------------


def encode_cursor_notifications(created_at: datetime, notification_id: uuid.UUID) -> str:
    """Pack (created_at, notification_id) into an opaque base64 string."""
    return encode_cursor(
        {"created_at": created_at.isoformat(), "notification_id": str(notification_id)}
    )


def decode_cursor_notifications(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    payload = decode_cursor(cursor)
    try:
        return datetime.fromisoformat(payload["created_at"]), uuid.UUID(payload["notification_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"invalid_cursor: {exc}") from exc


# ---------------------------------------------------------------------------
# GET /v1/notifications
# ---------------------------------------------------------------------------


@router.get(
    "/notifications",
    status_code=status.HTTP_200_OK,
    response_model=NotificationListResponse,
)
async def list_notifications(
    request: Request,
    response: Response,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
) -> NotificationListResponse | Response:
    """Paginated list of the current applicant's notifications.

    Returns pending, dispatching, and sent rows. Failed rows are excluded
    (admin-only). Cursor: base64 of {"created_at": ISO8601, "notification_id": uuid}.
    Order: created_at DESC, id DESC. ETag: W/"sha256(user_id|max_updated_at|count)".
    """
    await _require_applicant(user, session)

    cursor_created_at: datetime | None = None
    cursor_notif_id: uuid.UUID | None = None
    if cursor is not None:
        try:
            cursor_created_at, cursor_notif_id = decode_cursor_notifications(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_cursor",
            ) from None

    stmt = (
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
            Notification.status.in_(_INBOX_STATUSES),
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit + 1)  # peek-one for next_cursor
    )

    if cursor_created_at is not None and cursor_notif_id is not None:
        stmt = stmt.where(
            (Notification.created_at < cursor_created_at)
            | ((Notification.created_at == cursor_created_at) & (Notification.id < cursor_notif_id))
        )

    rows = (await session.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    rows = list(rows[:limit])

    items: list[NotificationListItem] = []
    max_updated_at: datetime | None = None
    for notification in rows:
        items.append(
            NotificationListItem(
                notification=NotificationRead.model_validate(notification),
            )
        )
        if max_updated_at is None or notification.updated_at > max_updated_at:
            max_updated_at = notification.updated_at

    next_cursor: str | None = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor_notifications(last.created_at, last.id)

    etag = make_weak_etag(user.id, max_updated_at, len(items))
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag

    return NotificationListResponse(items=items, next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# POST /v1/notifications/{notification_id}/read
# ---------------------------------------------------------------------------


@router.post(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_200_OK,
    response_model=NotificationRead,
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> NotificationRead:
    """Mark a notification as read.

    Scoped to the current user. 404 for missing or another user's notification.
    Idempotent: already-read notifications return 200 with the existing read_at.
    """
    await _require_applicant(user, session)

    notification = (
        await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user.id,
                Notification.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="notification_not_found",
        )

    if notification.read_at is None:
        from sqlalchemy import func

        notification.read_at = func.now()
        await session.commit()
        await session.refresh(notification)

    return NotificationRead.model_validate(notification)
