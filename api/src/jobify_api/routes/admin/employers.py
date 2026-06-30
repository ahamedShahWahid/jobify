"""Employer verification review — /v1/admin/employers.

The verification tri-state is DERIVED from two nullable timestamps on
``employers`` (migration 0020), never stored as an enum:
    verified_at set                         -> "verified"
    rejected_at set (and verified_at NULL)  -> "rejected"
    neither                                 -> "pending"
Verify and reject are mutually exclusive: each action clears the other's
timestamp, so re-verifying a previously-rejected employer just works. Setting
verified_at also flips the ``employer_verified`` trust badge surfaced in /v1/feed
and the recruiter EmployerRead (both read ``verified_at IS NOT NULL``).
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
from jobify.db.models import Employer, User
from jobify_api.auth.dependencies import _require_admin, current_user
from jobify_api.dependencies import get_session
from jobify_api.routes.admin._common import decode_admin_cursor, encode_admin_cursor

router = APIRouter(prefix="/v1/admin", tags=["admin"])
_log = structlog.get_logger(__name__)

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
        cursor_created, cursor_id = decode_admin_cursor(cursor)
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
        encode_admin_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if has_more else None
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
