"""Admin moderation endpoints — /v1/admin/*.

All routes require ADMIN role. Layer order per CLAUDE.md error-ladder
convention: current_user → 401 invariants (already done by the dep) →
_require_admin → 403 not_an_admin → DB read for the target resource.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.auth.dependencies import _require_admin, current_user
from kpa.db.models import AuditLog, User
from kpa.db.session import get_session

router = APIRouter(prefix="/v1/admin", tags=["admin"])
_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic shapes
# ---------------------------------------------------------------------------


class _UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    role: str
    suspended_at: datetime | None
    suspension_reason: str | None


class SuspendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=255)


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_role: str
    action: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    context: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# POST /v1/admin/users/{user_id}/suspend
# ---------------------------------------------------------------------------


@router.post("/users/{user_id}/suspend", response_model=_UserRead)
async def suspend_user(
    user_id: uuid.UUID,
    body: SuspendRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> _UserRead:
    await _require_admin(user)

    if user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot_suspend_self")

    target = await session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="user_not_found")

    now = func.now()
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            suspended_at=now,
            suspension_reason=body.reason,
            updated_at=now,
        )
    )

    await audit_log(
        session,
        action="admin.user.suspended",
        actor=user,
        resource_type="user",
        resource_id=user_id,
        context={
            "request_id": request.state.request_id,
            "reason": body.reason,
            "target_user_role": target.role.value,
        },
    )

    await session.commit()

    refreshed = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    _log.info(
        "admin.user-suspended",
        admin_user_id=str(user.id),
        target_user_id=str(user_id),
        reason=body.reason,
    )
    return _UserRead.model_validate(refreshed)


# ---------------------------------------------------------------------------
# DELETE /v1/admin/users/{user_id}/suspend
# ---------------------------------------------------------------------------


@router.delete("/users/{user_id}/suspend", response_model=_UserRead)
async def unsuspend_user(
    user_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> _UserRead:
    await _require_admin(user)

    target = await session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="user_not_found")

    # No-op on noop — same pattern as set_consent in PR #26.
    if target.suspended_at is None and target.suspension_reason is None:
        return _UserRead(
            id=target.id,
            email=target.email,
            role=target.role.value,
            suspended_at=None,
            suspension_reason=None,
        )

    now = func.now()
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            suspended_at=None,
            suspension_reason=None,
            updated_at=now,
        )
    )

    await audit_log(
        session,
        action="admin.user.unsuspended",
        actor=user,
        resource_type="user",
        resource_id=user_id,
        context={"request_id": request.state.request_id},
    )

    await session.commit()

    refreshed = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    _log.info(
        "admin.user-unsuspended",
        admin_user_id=str(user.id),
        target_user_id=str(user_id),
    )
    return _UserRead.model_validate(refreshed)


# ---------------------------------------------------------------------------
# GET /v1/admin/audit-logs
# ---------------------------------------------------------------------------


def _encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    payload = {"c": created_at.isoformat(), "i": str(row_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return datetime.fromisoformat(payload["c"]), uuid.UUID(payload["i"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid_cursor") from exc


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    action: str | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditLogListResponse:
    await _require_admin(user)

    stmt = select(AuditLog)
    filters = []
    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    if resource_type is not None:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        filters.append(AuditLog.resource_id == resource_id)
    if action is not None:
        filters.append(AuditLog.action == action)
    if from_ is not None:
        filters.append(AuditLog.created_at >= from_)
    if to is not None:
        filters.append(AuditLog.created_at <= to)

    if cursor is not None:
        cursor_created, cursor_id = _decode_cursor(cursor)
        # Tuple comparison: (created_at, id) < (cursor_created, cursor_id).
        filters.append(
            (AuditLog.created_at < cursor_created)
            | ((AuditLog.created_at == cursor_created) & (AuditLog.id < cursor_id))
        )

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1)
    rows = (await session.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    items = [AuditLogRead.model_validate(r) for r in rows[:limit]]
    next_cursor = (
        _encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if has_more else None
    )
    return AuditLogListResponse(items=items, next_cursor=next_cursor)
