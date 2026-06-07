"""Recruiter identity + employer self-service routes.

POST /v1/employers — creates an employer, links the caller as 'owner',
flips users.role APPLICANT→RECRUITER. 409 on duplicate name_norm.

GET  /v1/employers/me — lists every employer the caller is on.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.auth.dependencies import (
    _require_employer_member,
    _require_employer_owner,
    _require_recruiter,
    current_user,
)
from kpa.db.models import (
    Applicant,
    Employer,
    EmployerInvite,
    EmployerInviteStatus,
    EmployerUser,
    Notification,
    NotificationChannel,
    User,
    UserRole,
)
from kpa.db.session import get_session
from kpa.employers.membership import flip_to_recruiter, maybe_demote_to_applicant


def _normalize_email(email: str) -> str:
    return email.strip().lower()


_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["employers"])

_WHITESPACE = re.compile(r"\s+")


def _normalize_name(name: str) -> str:
    return _WHITESPACE.sub(" ", name).strip().lower()


class EmployerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=200)
    gst: str | None = Field(default=None, min_length=15, max_length=15)


class EmployerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    gst: str | None
    verified_at: datetime | None
    created_at: datetime


@router.post("/employers", response_model=EmployerRead, status_code=201)
async def create_employer(
    payload: EmployerCreate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EmployerRead:
    emp = Employer(
        name=payload.name,
        name_norm=_normalize_name(payload.name),
        gst=payload.gst,
        created_by_user_id=user.id,
    )
    session.add(emp)
    try:
        await session.flush()
    except IntegrityError as e:
        # SQLAlchemy wraps the asyncpg exception: e.orig is AsyncAdapt_asyncpg_dbapi.IntegrityError,
        # and the raw asyncpg UniqueViolationError (which carries constraint_name) sits at
        # e.orig.__cause__. Walk the cause chain to detect our partial-UNIQUE constraint.
        orig = getattr(e, "orig", None)
        cause = getattr(orig, "__cause__", None) or orig
        if (
            cause is not None
            and type(cause).__name__ == "UniqueViolationError"
            and getattr(cause, "constraint_name", None) == "ix_employers_name_norm_live"
        ):
            await session.rollback()
            raise HTTPException(status_code=409, detail="employer_name_taken") from e
        await session.rollback()
        raise

    session.add(EmployerUser(employer_id=emp.id, user_id=user.id, role="owner"))

    # Role flip: APPLICANT → RECRUITER. Bounded; never demotes ADMIN.
    # No-op for an existing recruiter.
    await session.execute(
        update(User)
        .where(User.id == user.id, User.role == UserRole.APPLICANT)
        .values(role=UserRole.RECRUITER, updated_at=func.now())
    )
    await session.commit()
    await session.refresh(emp)

    _log.info(
        "employer.created",
        employer_id=str(emp.id),
        created_by_user_id=str(user.id),
    )
    return EmployerRead.model_validate(emp)


@router.get("/employers/me", response_model=list[EmployerRead])
async def list_my_employers(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[EmployerRead]:
    await _require_recruiter(user)
    rows = (
        (
            await session.execute(
                select(Employer)
                .join(EmployerUser, EmployerUser.employer_id == Employer.id)
                .where(
                    EmployerUser.user_id == user.id,
                    EmployerUser.deleted_at.is_(None),
                    Employer.deleted_at.is_(None),
                )
                .order_by(Employer.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [EmployerRead.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Team management (R4) — members + invites
# ---------------------------------------------------------------------------


class MemberRead(BaseModel):
    user_id: uuid.UUID
    email: str | None
    display_name: str | None
    role: str
    added_at: datetime


class MemberAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    role: Literal["owner", "member"] = "member"

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        v = _normalize_email(v)
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("invalid email")
        return v


class MemberRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["owner", "member"]


class InviteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    role: Literal["owner", "member"] = "member"

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        v = _normalize_email(v)
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("invalid email")
        return v


class InviteRead(BaseModel):
    id: uuid.UUID
    employer_id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    invited_by_user_id: uuid.UUID | None


def _invite_read(inv: EmployerInvite) -> InviteRead:
    return InviteRead(
        id=inv.id,
        employer_id=inv.employer_id,
        email=inv.email,
        role=inv.role,
        status=inv.status.value,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
        invited_by_user_id=inv.invited_by_user_id,
    )


async def _count_live_owners(
    session: AsyncSession,
    employer_id: uuid.UUID,
    *,
    lock: bool = False,
) -> int:
    """Count an employer's live owners.

    With ``lock=True`` the matching owner rows are ``SELECT ... FOR UPDATE``'d so
    concurrent owner demotions/removals serialize — without it, two owners
    removing each other simultaneously could each pass the last-owner guard and
    leave the employer with zero owners (TOCTOU). Aggregates can't carry
    ``FOR UPDATE`` in Postgres, so we lock the rows and count them in Python.
    """
    stmt = select(EmployerUser.id).where(
        EmployerUser.employer_id == employer_id,
        EmployerUser.role == "owner",
        EmployerUser.deleted_at.is_(None),
    )
    if lock:
        stmt = stmt.with_for_update()
    rows = (await session.execute(stmt)).scalars().all()
    return len(rows)


@router.get("/employers/{employer_id}/members", response_model=list[MemberRead])
async def list_members(
    employer_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[MemberRead]:
    await _require_employer_member(user, employer_id, session)
    rows = (
        await session.execute(
            select(EmployerUser, User.email, Applicant.full_name)
            .join(User, User.id == EmployerUser.user_id)
            .outerjoin(
                Applicant,
                and_(Applicant.user_id == User.id, Applicant.deleted_at.is_(None)),
            )
            .where(
                EmployerUser.employer_id == employer_id,
                EmployerUser.deleted_at.is_(None),
            )
            .order_by(EmployerUser.created_at.asc())
        )
    ).all()
    return [
        MemberRead(
            user_id=eu.user_id,
            email=email,
            display_name=full_name,
            role=eu.role,
            added_at=eu.created_at,
        )
        for eu, email, full_name in rows
    ]


@router.post("/employers/{employer_id}/members", response_model=MemberRead, status_code=201)
async def add_member(
    employer_id: uuid.UUID,
    payload: MemberAddRequest,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MemberRead:
    await _require_employer_owner(user, employer_id, session)

    target = (
        await session.execute(
            select(User).where(
                func.lower(User.email) == payload.email,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if target is None:
        # No account for this email — the owner must invite instead.
        raise HTTPException(status_code=404, detail="user_not_found")

    existing = await session.scalar(
        select(EmployerUser.id).where(
            EmployerUser.employer_id == employer_id,
            EmployerUser.user_id == target.id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="already_a_member")

    link = EmployerUser(employer_id=employer_id, user_id=target.id, role=payload.role)
    session.add(link)
    await flip_to_recruiter(session, target.id)
    try:
        await session.flush()
    except IntegrityError as e:
        # Concurrent add raced us to the partial-UNIQUE ix_employer_users_pair_live.
        await session.rollback()
        raise HTTPException(status_code=409, detail="already_a_member") from e

    full_name = await session.scalar(
        select(Applicant.full_name).where(
            Applicant.user_id == target.id,
            Applicant.deleted_at.is_(None),
        )
    )

    await audit_log(
        session,
        action="employer.member_added",
        actor=user,
        resource_type="employer",
        resource_id=employer_id,
        context={
            "target_user_id": str(target.id),
            "email": payload.email,
            "role": payload.role,
        },
    )
    await session.commit()
    return MemberRead(
        user_id=target.id,
        email=target.email,
        display_name=full_name,
        role=payload.role,
        added_at=link.created_at,
    )


@router.patch("/employers/{employer_id}/members/{member_user_id}", response_model=MemberRead)
async def change_member_role(
    employer_id: uuid.UUID,
    member_user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MemberRead:
    await _require_employer_owner(user, employer_id, session)

    link = (
        await session.execute(
            select(EmployerUser).where(
                EmployerUser.employer_id == employer_id,
                EmployerUser.user_id == member_user_id,
                EmployerUser.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="not found")

    target = await session.get(User, member_user_id)
    full_name = await session.scalar(
        select(Applicant.full_name).where(
            Applicant.user_id == member_user_id,
            Applicant.deleted_at.is_(None),
        )
    )

    if link.role == payload.role:
        # No-op role change — no state change, no audit row.
        return MemberRead(
            user_id=member_user_id,
            email=target.email if target else None,
            display_name=full_name,
            role=link.role,
            added_at=link.created_at,
        )

    # Guard: don't demote the last owner. Lock owner rows to avoid a TOCTOU
    # race with a concurrent demote/remove.
    if link.role == "owner" and payload.role != "owner":
        if await _count_live_owners(session, employer_id, lock=True) <= 1:
            raise HTTPException(status_code=400, detail="last_owner")

    link.role = payload.role
    link.updated_at = func.now()
    await session.flush()

    await audit_log(
        session,
        action="employer.member_role_changed",
        actor=user,
        resource_type="employer",
        resource_id=employer_id,
        context={"target_user_id": str(member_user_id), "new_role": payload.role},
    )
    await session.commit()
    return MemberRead(
        user_id=member_user_id,
        email=target.email if target else None,
        display_name=full_name,
        role=payload.role,
        added_at=link.created_at,
    )


@router.delete("/employers/{employer_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    employer_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    await _require_employer_owner(user, employer_id, session)

    link = (
        await session.execute(
            select(EmployerUser).where(
                EmployerUser.employer_id == employer_id,
                EmployerUser.user_id == member_user_id,
                EmployerUser.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="not found")

    # Guard: removing the last owner (covers "remove yourself as sole owner").
    # Lock owner rows to avoid a TOCTOU race with a concurrent demote/remove.
    if link.role == "owner" and await _count_live_owners(session, employer_id, lock=True) <= 1:
        raise HTTPException(status_code=400, detail="last_owner")

    link.deleted_at = func.now()
    await session.flush()

    demoted = await maybe_demote_to_applicant(session, member_user_id)

    await audit_log(
        session,
        action="employer.member_removed",
        actor=user,
        resource_type="employer",
        resource_id=employer_id,
        context={
            "target_user_id": str(member_user_id),
            "demoted_to_applicant": demoted,
        },
    )
    await session.commit()
    return Response(status_code=204)


@router.post("/employers/{employer_id}/invites", response_model=InviteRead, status_code=201)
async def create_invite(
    employer_id: uuid.UUID,
    payload: InviteCreate,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> InviteRead:
    await _require_employer_owner(user, employer_id, session)

    emp = await session.get(Employer, employer_id)
    if emp is None or emp.deleted_at is not None:
        raise HTTPException(status_code=404, detail="not found")

    # 409 if an existing account is already a live member of this employer.
    target = (
        await session.execute(
            select(User).where(
                func.lower(User.email) == payload.email,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if target is not None:
        existing_link = await session.scalar(
            select(EmployerUser.id).where(
                EmployerUser.employer_id == employer_id,
                EmployerUser.user_id == target.id,
                EmployerUser.deleted_at.is_(None),
            )
        )
        if existing_link is not None:
            raise HTTPException(status_code=409, detail="already_a_member")

    settings = request.app.state.settings
    expires_at = datetime.now(UTC) + timedelta(days=settings.employer_invite_ttl_days)
    invite = EmployerInvite(
        employer_id=employer_id,
        email=payload.email,
        role=payload.role,
        invited_by_user_id=user.id,
        expires_at=expires_at,
        status=EmployerInviteStatus.PENDING,
    )
    session.add(invite)
    try:
        await session.flush()
    except IntegrityError as e:
        # Partial-UNIQUE ix_employer_invites_pending_live — a live pending invite
        # for (employer, email) already exists.
        await session.rollback()
        raise HTTPException(status_code=409, detail="invite_already_pending") from e

    # Outbox delivery rides the notifications table. We can only enqueue when the
    # email maps to an existing account (notifications.user_id is NOT NULL). For a
    # brand-new invitee the row is omitted — they discover the invite via
    # GET /v1/me/invites after signing up. Real email (SES) is deferred (spec §9).
    if target is not None:
        session.add(
            Notification(
                user_id=target.id,
                kind="employer_invite",
                channel=NotificationChannel.EMAIL,
                payload={
                    "kind": "employer_invite",
                    "invite_id": str(invite.id),
                    "employer_id": str(employer_id),
                    "employer_name": emp.name,
                    "role": payload.role,
                },
            )
        )
    else:
        _log.info("invite.email-no-account", invite_id=str(invite.id), employer_id=str(employer_id))

    await audit_log(
        session,
        action="employer.invite_created",
        actor=user,
        resource_type="employer_invite",
        resource_id=invite.id,
        context={"email": payload.email, "role": payload.role},
    )
    await session.commit()
    await session.refresh(invite)
    return _invite_read(invite)


@router.get("/employers/{employer_id}/invites", response_model=list[InviteRead])
async def list_invites(
    employer_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[InviteRead]:
    await _require_employer_member(user, employer_id, session)
    rows = (
        (
            await session.execute(
                select(EmployerInvite)
                .where(
                    EmployerInvite.employer_id == employer_id,
                    EmployerInvite.status == EmployerInviteStatus.PENDING,
                    EmployerInvite.deleted_at.is_(None),
                )
                .order_by(EmployerInvite.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_invite_read(r) for r in rows]


@router.delete("/employers/{employer_id}/invites/{invite_id}", status_code=204)
async def revoke_invite(
    employer_id: uuid.UUID,
    invite_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    await _require_employer_owner(user, employer_id, session)

    invite = (
        await session.execute(
            select(EmployerInvite).where(
                EmployerInvite.id == invite_id,
                EmployerInvite.employer_id == employer_id,
                EmployerInvite.status == EmployerInviteStatus.PENDING,
                EmployerInvite.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="not found")

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
        context={"email": invite.email},
    )
    await session.commit()
    return Response(status_code=204)
