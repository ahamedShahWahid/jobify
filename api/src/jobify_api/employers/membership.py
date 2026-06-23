"""Membership-derived role flips for employer team management (R4).

Recruiter access is a *computed consequence* of live ``employer_users`` rows
(spec §1). Joining any employer raises ``APPLICANT → RECRUITER``; losing the
last live membership drops ``RECRUITER → APPLICANT``. Both flips are bounded so
they never touch ``ADMIN``. ``current_user`` re-fetches the user row per request,
so a demotion takes effect within the access-token TTL — no token revocation.

These helpers do NOT commit; the caller owns the transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import EmployerUser, User, UserRole


async def flip_to_recruiter(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Bounded-flip ``APPLICANT → RECRUITER``. No-op for RECRUITER/ADMIN."""
    await session.execute(
        update(User)
        .where(User.id == user_id, User.role == UserRole.APPLICANT)
        .values(role=UserRole.RECRUITER, updated_at=func.now())
    )


async def maybe_demote_to_applicant(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """Drop ``RECRUITER → APPLICANT`` iff the user has zero live memberships left.

    Returns True if a demotion happened. Never touches ADMIN/APPLICANT (only a
    RECRUITER flips). Call AFTER the membership soft-delete has flushed so the
    live-membership count is current.
    """
    live_count = await session.scalar(
        select(func.count())
        .select_from(EmployerUser)
        .where(
            EmployerUser.user_id == user_id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    if live_count and live_count > 0:
        return False
    user_obj = await session.get(User, user_id)
    if user_obj is None or user_obj.role != UserRole.RECRUITER:
        return False
    user_obj.role = UserRole.APPLICANT
    return True
