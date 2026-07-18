"""Transactional employer-team commands independent of HTTP transport."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import (
    Applicant,
    Employer,
    EmployerInvite,
    EmployerInviteStatus,
    EmployerUser,
    Notification,
    NotificationChannel,
    User,
)
from jobify_api.employers.membership import flip_to_recruiter, maybe_demote_to_applicant

_log = structlog.get_logger(__name__)


class TeamCommandError(Exception):
    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class MemberSnapshot:
    user_id: uuid.UUID
    email: str | None
    display_name: str | None
    role: str
    added_at: datetime


async def _count_live_owners(
    session: AsyncSession, employer_id: uuid.UUID, *, lock: bool = False
) -> int:
    stmt = select(EmployerUser.id).where(
        EmployerUser.employer_id == employer_id,
        EmployerUser.role == "owner",
        EmployerUser.deleted_at.is_(None),
    )
    if lock:
        stmt = stmt.with_for_update()
    return len((await session.execute(stmt)).scalars().all())


async def _member_snapshot(
    session: AsyncSession, link: EmployerUser, target: User | None
) -> MemberSnapshot:
    full_name = await session.scalar(
        select(Applicant.full_name).where(
            Applicant.user_id == link.user_id,
            Applicant.deleted_at.is_(None),
        )
    )
    return MemberSnapshot(
        user_id=link.user_id,
        email=target.email if target else None,
        display_name=full_name,
        role=link.role,
        added_at=link.created_at,
    )


async def add_member(
    session: AsyncSession,
    *,
    employer_id: uuid.UUID,
    email: str,
    role: str,
    actor: User,
) -> MemberSnapshot:
    target = (
        await session.execute(
            select(User).where(func.lower(User.email) == email, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if target is None:
        raise TeamCommandError("user_not_found", status_code=404)
    existing = await session.scalar(
        select(EmployerUser.id).where(
            EmployerUser.employer_id == employer_id,
            EmployerUser.user_id == target.id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise TeamCommandError("already_a_member", status_code=409)

    link = EmployerUser(employer_id=employer_id, user_id=target.id, role=role)
    session.add(link)
    await flip_to_recruiter(session, target.id)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise TeamCommandError("already_a_member", status_code=409) from exc
    snapshot = await _member_snapshot(session, link, target)
    await audit_log(
        session,
        action="employer.member_added",
        actor=actor,
        resource_type="employer",
        resource_id=employer_id,
        context={"target_user_id": str(target.id), "email": email, "role": role},
    )
    await session.commit()
    return snapshot


async def change_member_role(
    session: AsyncSession,
    *,
    employer_id: uuid.UUID,
    member_user_id: uuid.UUID,
    role: str,
    actor: User,
) -> MemberSnapshot:
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
        raise TeamCommandError("not found", status_code=404)
    target = await session.get(User, member_user_id)
    if link.role == role:
        return await _member_snapshot(session, link, target)
    if link.role == "owner" and role != "owner":
        if await _count_live_owners(session, employer_id, lock=True) <= 1:
            raise TeamCommandError("last_owner", status_code=400)

    link.role = role
    link.updated_at = func.now()
    await session.flush()
    snapshot = await _member_snapshot(session, link, target)
    await audit_log(
        session,
        action="employer.member_role_changed",
        actor=actor,
        resource_type="employer",
        resource_id=employer_id,
        context={"target_user_id": str(member_user_id), "new_role": role},
    )
    await session.commit()
    return snapshot


async def remove_member(
    session: AsyncSession,
    *,
    employer_id: uuid.UUID,
    member_user_id: uuid.UUID,
    actor: User,
) -> None:
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
        raise TeamCommandError("not found", status_code=404)
    if link.role == "owner" and await _count_live_owners(session, employer_id, lock=True) <= 1:
        raise TeamCommandError("last_owner", status_code=400)

    link.deleted_at = func.now()
    await session.flush()
    demoted = await maybe_demote_to_applicant(session, member_user_id)
    await audit_log(
        session,
        action="employer.member_removed",
        actor=actor,
        resource_type="employer",
        resource_id=employer_id,
        context={
            "target_user_id": str(member_user_id),
            "demoted_to_applicant": demoted,
        },
    )
    await session.commit()


async def create_invite(
    session: AsyncSession,
    *,
    employer_id: uuid.UUID,
    email: str,
    role: str,
    actor: User,
    ttl_days: int,
) -> EmployerInvite:
    employer = await session.get(Employer, employer_id)
    if employer is None or employer.deleted_at is not None:
        raise TeamCommandError("not found", status_code=404)
    target = (
        await session.execute(
            select(User).where(func.lower(User.email) == email, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if target is not None:
        existing = await session.scalar(
            select(EmployerUser.id).where(
                EmployerUser.employer_id == employer_id,
                EmployerUser.user_id == target.id,
                EmployerUser.deleted_at.is_(None),
            )
        )
        if existing is not None:
            raise TeamCommandError("already_a_member", status_code=409)

    invite = EmployerInvite(
        employer_id=employer_id,
        email=email,
        role=role,
        invited_by_user_id=actor.id,
        expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
        status=EmployerInviteStatus.PENDING,
    )
    session.add(invite)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise TeamCommandError("invite_already_pending", status_code=409) from exc

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
                    "employer_name": employer.name,
                    "role": role,
                },
            )
        )
    else:
        _log.info(
            "invite.email-no-account",
            invite_id=str(invite.id),
            employer_id=str(employer_id),
        )
    await audit_log(
        session,
        action="employer.invite_created",
        actor=actor,
        resource_type="employer_invite",
        resource_id=invite.id,
        context={"email": email, "role": role},
    )
    await session.commit()
    await session.refresh(invite)
    return invite


async def revoke_invite(
    session: AsyncSession,
    *,
    employer_id: uuid.UUID,
    invite_id: uuid.UUID,
    actor: User,
) -> None:
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
        raise TeamCommandError("not found", status_code=404)
    invite.status = EmployerInviteStatus.REVOKED
    invite.deleted_at = func.now()
    invite.updated_at = func.now()
    await session.flush()
    await audit_log(
        session,
        action="employer.invite_revoked",
        actor=actor,
        resource_type="employer_invite",
        resource_id=invite.id,
        context={"email": invite.email},
    )
    await session.commit()
