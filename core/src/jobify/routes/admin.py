"""Admin moderation endpoints — /v1/admin/*.

All routes require ADMIN role. Layer order per CLAUDE.md error-ladder
convention: current_user → 401 invariants (already done by the dep) →
_require_admin → 403 not_an_admin → DB read for the target resource.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.auth.dependencies import _require_admin, current_user
from jobify.db.models import AuditLog, Employer, User
from jobify.db.session import get_session
from jobify.pagination import decode_cursor, encode_cursor

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
    return encode_cursor({"c": created_at.isoformat(), "i": str(row_id)})


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = decode_cursor(cursor)
        return datetime.fromisoformat(payload["c"]), uuid.UUID(payload["i"])
    except (ValueError, KeyError, TypeError) as exc:
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


# ---------------------------------------------------------------------------
# Employer verification review — /v1/admin/employers
#
# The verification tri-state is DERIVED from two nullable timestamps on
# `employers` (migration 0020), never stored as an enum:
#   verified_at set                         -> "verified"
#   rejected_at set (and verified_at NULL)  -> "rejected"
#   neither                                 -> "pending"
# Verify and reject are mutually exclusive: each action clears the other's
# timestamp, so re-verifying a previously-rejected employer just works. Setting
# verified_at also flips the `employer_verified` trust badge surfaced in /v1/feed
# and the recruiter EmployerRead (both read `verified_at IS NOT NULL`).
# ---------------------------------------------------------------------------

EmployerVerificationStatus = Literal["pending", "verified", "rejected"]


class AdminEmployerRead(BaseModel):
    """Admin view of an employer's verification state. `reviewed_at`/`reason`
    are derived — there is no separate review table; `audit_logs` is the history."""

    id: uuid.UUID
    name: str
    gst: str | None
    status: EmployerVerificationStatus
    created_at: datetime
    reviewed_at: datetime | None
    reason: str | None

    @classmethod
    def from_employer(cls, employer: Employer) -> AdminEmployerRead:
        if employer.verified_at is not None:
            return cls(
                id=employer.id,
                name=employer.name,
                gst=employer.gst,
                status="verified",
                created_at=employer.created_at,
                reviewed_at=employer.verified_at,
                reason=None,
            )
        if employer.rejected_at is not None:
            return cls(
                id=employer.id,
                name=employer.name,
                gst=employer.gst,
                status="rejected",
                created_at=employer.created_at,
                reviewed_at=employer.rejected_at,
                reason=employer.rejection_reason,
            )
        return cls(
            id=employer.id,
            name=employer.name,
            gst=employer.gst,
            status="pending",
            created_at=employer.created_at,
            reviewed_at=None,
            reason=None,
        )


class AdminEmployerListResponse(BaseModel):
    items: list[AdminEmployerRead]
    next_cursor: str | None = None


class RejectEmployerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=255)


def _status_filters(status: EmployerVerificationStatus) -> list[Any]:
    """SQL predicates that partition live employers by derived status. Exhaustive
    over the Literal — a status param outside it never reaches here (422 first)."""
    if status == "verified":
        return [Employer.verified_at.is_not(None)]
    if status == "rejected":
        return [Employer.verified_at.is_(None), Employer.rejected_at.is_not(None)]
    return [Employer.verified_at.is_(None), Employer.rejected_at.is_(None)]


@router.get("/employers", response_model=AdminEmployerListResponse)
async def list_employers_for_verification(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    status: Annotated[EmployerVerificationStatus, Query()] = "pending",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminEmployerListResponse:
    await _require_admin(user)

    filters: list[Any] = [Employer.deleted_at.is_(None), *_status_filters(status)]
    if cursor is not None:
        cursor_created, cursor_id = _decode_cursor(cursor)
        filters.append(
            (Employer.created_at < cursor_created)
            | ((Employer.created_at == cursor_created) & (Employer.id < cursor_id))
        )

    stmt = (
        select(Employer)
        .where(and_(*filters))
        .order_by(Employer.created_at.desc(), Employer.id.desc())
        .limit(limit + 1)
    )
    rows = (await session.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    items = [AdminEmployerRead.from_employer(e) for e in rows[:limit]]
    next_cursor = (
        _encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if has_more else None
    )
    return AdminEmployerListResponse(items=items, next_cursor=next_cursor)


async def _load_employer_for_review(session: AsyncSession, employer_id: uuid.UUID) -> Employer:
    employer = await session.get(Employer, employer_id)
    if employer is None or employer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="employer_not_found")
    return employer


@router.post("/employers/{employer_id}/verify", response_model=AdminEmployerRead)
async def verify_employer(
    employer_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AdminEmployerRead:
    await _require_admin(user)

    await _load_employer_for_review(session, employer_id)

    now = func.now()
    await session.execute(
        update(Employer)
        .where(Employer.id == employer_id)
        .values(verified_at=now, rejected_at=None, rejection_reason=None, updated_at=now)
    )

    # An audit row every call (re-verify is evidence) — mirrors admin.user.suspended.
    await audit_log(
        session,
        action="admin.employer.verified",
        actor=user,
        resource_type="employer",
        resource_id=employer_id,
        context={"request_id": request.state.request_id},
    )
    await session.commit()

    refreshed = (
        await session.execute(select(Employer).where(Employer.id == employer_id))
    ).scalar_one()
    _log.info(
        "admin.employer-verified",
        admin_user_id=str(user.id),
        employer_id=str(employer_id),
    )
    return AdminEmployerRead.from_employer(refreshed)


@router.post("/employers/{employer_id}/reject", response_model=AdminEmployerRead)
async def reject_employer(
    employer_id: uuid.UUID,
    body: RejectEmployerRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AdminEmployerRead:
    await _require_admin(user)

    await _load_employer_for_review(session, employer_id)

    now = func.now()
    await session.execute(
        update(Employer)
        .where(Employer.id == employer_id)
        .values(rejected_at=now, rejection_reason=body.reason, verified_at=None, updated_at=now)
    )

    await audit_log(
        session,
        action="admin.employer.rejected",
        actor=user,
        resource_type="employer",
        resource_id=employer_id,
        context={"request_id": request.state.request_id, "reason": body.reason},
    )
    await session.commit()

    refreshed = (
        await session.execute(select(Employer).where(Employer.id == employer_id))
    ).scalar_one()
    _log.info(
        "admin.employer-rejected",
        admin_user_id=str(user.id),
        employer_id=str(employer_id),
        reason=body.reason,
    )
    return AdminEmployerRead.from_employer(refreshed)
