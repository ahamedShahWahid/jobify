"""Employer identity — create + list.

POST /v1/employers — creates an employer, links the caller as 'owner',
flips users.role APPLICANT→RECRUITER. 409 on duplicate name_norm.

GET  /v1/employers/me — lists every employer the caller is on.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Employer, EmployerUser, User, UserRole
from jobify_api.auth.dependencies import _require_recruiter, current_user
from jobify_api.dependencies import get_session

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
