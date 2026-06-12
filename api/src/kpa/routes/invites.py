"""Invitee-facing employer-invite routes (R4).

GET  /v1/me/invites                 — pending, non-expired invites for the caller's email.
POST /v1/me/invites/{id}/accept     — join the employer (membership + role flip).
POST /v1/me/invites/{id}/decline    — decline (marks the invite revoked).

Authorization is by email match (``invite.email == current_user.email``), NOT by
employer membership — the whole point is that a non-member accepts. Acceptance is
authenticated + email-matched; the reserved ``token`` column (unauthenticated
email-link accept) is unused at MVP. Expiry is lazy: a ``pending`` invite past its
``expires_at`` is flipped to ``expired`` on read/accept (no beat task — spec §5.3).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.auth.dependencies import current_user
from kpa.db.models import (
    Employer,
    EmployerInvite,
    EmployerInviteStatus,
    EmployerUser,
    User,
)
from kpa.db.session import get_session
from kpa.employers.membership import flip_to_recruiter

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["invites"])


class MyInviteRead(BaseModel):
    id: uuid.UUID
    employer_id: uuid.UUID
    employer_name: str
    role: str
    expires_at: datetime
    created_at: datetime


class AcceptResult(BaseModel):
    employer_id: uuid.UUID
    role: str
    status: str


def _caller_email(user: User) -> str | None:
    return user.email.strip().lower() if user.email else None


@router.get("/me/invites", response_model=list[MyInviteRead])
async def list_my_invites(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[MyInviteRead]:
    email = _caller_email(user)
    if email is None:
        return []

    rows = (
        await session.execute(
            select(EmployerInvite, Employer.name)
            .join(Employer, Employer.id == EmployerInvite.employer_id)
            .where(
                func.lower(EmployerInvite.email) == email,
                EmployerInvite.status == EmployerInviteStatus.PENDING,
                EmployerInvite.deleted_at.is_(None),
                Employer.deleted_at.is_(None),
            )
            .order_by(EmployerInvite.created_at.desc())
        )
    ).all()

    now = datetime.now(UTC)
    result: list[MyInviteRead] = []
    expired_any = False
    for invite, employer_name in rows:
        if invite.expires_at < now:
            # Lazy expiry — flip and exclude.
            invite.status = EmployerInviteStatus.EXPIRED
            expired_any = True
            continue
        result.append(
            MyInviteRead(
                id=invite.id,
                employer_id=invite.employer_id,
                employer_name=employer_name,
                role=invite.role,
                expires_at=invite.expires_at,
                created_at=invite.created_at,
            )
        )
    if expired_any:
        await session.commit()
    return result


async def _load_invite_for_caller(
    invite_id: uuid.UUID, user: User, session: AsyncSession
) -> EmployerInvite:
    """Load a live invite addressed to the caller, or uniform 404.

    Email mismatch and unknown id collapse to the same 404 so we never leak
    whether an invite exists for someone else. The email match lives in the
    WHERE clause (``func.lower``) so it shares one normalization path with
    ``list_my_invites`` instead of a divergent Python-side comparison.
    """
    email = _caller_email(user)
    if email is None:
        raise HTTPException(status_code=404, detail="not found")
    invite = (
        await session.execute(
            select(EmployerInvite).where(
                EmployerInvite.id == invite_id,
                func.lower(EmployerInvite.email) == email,
                EmployerInvite.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="not found")
    return invite


@router.post("/me/invites/{invite_id}/accept", response_model=AcceptResult)
async def accept_invite(
    invite_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AcceptResult:
    invite = await _load_invite_for_caller(invite_id, user, session)

    if invite.status != EmployerInviteStatus.PENDING:
        # Already accepted/revoked/expired — uniform 404 (don't leak prior state).
        raise HTTPException(status_code=404, detail="not found")

    if invite.expires_at < datetime.now(UTC):
        invite.status = EmployerInviteStatus.EXPIRED
        await session.commit()
        raise HTTPException(status_code=410, detail="invite_expired")

    # The employer must still be live — don't resurrect a membership into a
    # soft-deleted employer (unreachable today; defensive before employer
    # deletion ships).
    employer_live = await session.scalar(
        select(Employer.id).where(
            Employer.id == invite.employer_id,
            Employer.deleted_at.is_(None),
        )
    )
    if employer_live is None:
        raise HTTPException(status_code=404, detail="not found")

    # Idempotent membership: if already a live member (joined by another path),
    # don't insert a duplicate link — just mark the invite accepted.
    existing = await session.scalar(
        select(EmployerUser.id).where(
            EmployerUser.employer_id == invite.employer_id,
            EmployerUser.user_id == user.id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    if existing is None:
        session.add(
            EmployerUser(
                employer_id=invite.employer_id,
                user_id=user.id,
                role=invite.role,
            )
        )

    invite.status = EmployerInviteStatus.ACCEPTED
    invite.accepted_user_id = user.id
    invite.updated_at = func.now()
    await flip_to_recruiter(session, user.id)
    try:
        await session.flush()
    except IntegrityError as e:
        # Concurrent accept raced us to the membership partial-UNIQUE.
        await session.rollback()
        raise HTTPException(status_code=409, detail="already_a_member") from e

    await audit_log(
        session,
        action="employer.invite_accepted",
        actor=user,
        resource_type="employer_invite",
        resource_id=invite.id,
        context={"employer_id": str(invite.employer_id), "role": invite.role},
    )
    await session.commit()
    return AcceptResult(
        employer_id=invite.employer_id,
        role=invite.role,
        status=EmployerInviteStatus.ACCEPTED.value,
    )


@router.post("/me/invites/{invite_id}/decline", status_code=status.HTTP_200_OK)
async def decline_invite(
    invite_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AcceptResult:
    invite = await _load_invite_for_caller(invite_id, user, session)
    if invite.status != EmployerInviteStatus.PENDING:
        raise HTTPException(status_code=404, detail="not found")

    # Decline reuses the `revoked` status (no separate enum value — spec §5.3).
    invite.status = EmployerInviteStatus.REVOKED
    invite.deleted_at = func.now()
    invite.updated_at = func.now()
    await session.flush()

    await audit_log(
        session,
        action="employer.invite_revoked",
        actor=user,
        resource_type="employer_invite",
        resource_id=invite.id,
        context={"email": invite.email, "declined_by_invitee": True},
    )
    await session.commit()
    return AcceptResult(
        employer_id=invite.employer_id,
        role=invite.role,
        status=EmployerInviteStatus.REVOKED.value,
    )
