"""Employer team management (R4) — members + invites.

Owner mutates members/invites; any member reads. Role is DERIVED from membership
(``flip_to_recruiter`` / ``maybe_demote_to_applicant`` are the only ``users.role``
writers here). Last-owner guards lock owner rows (``_count_live_owners(lock=True)``)
to avoid a TOCTOU race. See ``api/CLAUDE.md`` for the full invariant list.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    EmployerInvite,
    EmployerInviteStatus,
    EmployerUser,
    User,
)
from jobify_api.auth.dependencies import (
    _require_employer_member,
    _require_employer_owner,
    current_user,
)
from jobify_api.dependencies import get_session
from jobify_api.employers.team_service import (
    MemberSnapshot,
    TeamCommandError,
)
from jobify_api.employers.team_service import (
    add_member as add_member_command,
)
from jobify_api.employers.team_service import (
    change_member_role as change_member_role_command,
)
from jobify_api.employers.team_service import (
    create_invite as create_invite_command,
)
from jobify_api.employers.team_service import (
    remove_member as remove_member_command,
)
from jobify_api.employers.team_service import (
    revoke_invite as revoke_invite_command,
)

router = APIRouter(prefix="/v1", tags=["employers"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


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


def _member_read(snapshot: MemberSnapshot) -> MemberRead:
    return MemberRead(
        user_id=snapshot.user_id,
        email=snapshot.email,
        display_name=snapshot.display_name,
        role=snapshot.role,
        added_at=snapshot.added_at,
    )


def _raise_http(exc: TeamCommandError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


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
    try:
        snapshot = await add_member_command(
            session,
            employer_id=employer_id,
            email=payload.email,
            role=payload.role,
            actor=user,
        )
    except TeamCommandError as exc:
        _raise_http(exc)
    return _member_read(snapshot)


@router.patch("/employers/{employer_id}/members/{member_user_id}", response_model=MemberRead)
async def change_member_role(
    employer_id: uuid.UUID,
    member_user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MemberRead:
    await _require_employer_owner(user, employer_id, session)
    try:
        snapshot = await change_member_role_command(
            session,
            employer_id=employer_id,
            member_user_id=member_user_id,
            role=payload.role,
            actor=user,
        )
    except TeamCommandError as exc:
        _raise_http(exc)
    return _member_read(snapshot)


@router.delete("/employers/{employer_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    employer_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    await _require_employer_owner(user, employer_id, session)
    try:
        await remove_member_command(
            session,
            employer_id=employer_id,
            member_user_id=member_user_id,
            actor=user,
        )
    except TeamCommandError as exc:
        _raise_http(exc)
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
    try:
        invite = await create_invite_command(
            session,
            employer_id=employer_id,
            email=payload.email,
            role=payload.role,
            actor=user,
            ttl_days=request.app.state.settings.employer_invite_ttl_days,
        )
    except TeamCommandError as exc:
        _raise_http(exc)
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
    try:
        await revoke_invite_command(
            session,
            employer_id=employer_id,
            invite_id=invite_id,
            actor=user,
        )
    except TeamCommandError as exc:
        _raise_http(exc)
    return Response(status_code=204)
