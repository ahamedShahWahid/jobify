"""GET /v1/me — current user + role-shaped payload.

This slice only implements the applicant branch. Recruiter / admin shapes
land in their respective auth plans.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.dependencies import current_user
from jobify.db.models import Applicant, User, UserRole
from jobify.db.session import get_session

router = APIRouter(prefix="/v1", tags=["me"])


class ApplicantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # Nullable to mirror the DB schema — migration 0015 made full_name and
    # locations nullable for DSR scrubbing. A non-optional str here turns a
    # NULL row into a Pydantic ValidationError → 500.
    full_name: str | None
    locations: list[str] | None
    notice_period_days: int | None
    current_ctc: Decimal | None
    expected_ctc: Decimal | None
    years_experience: Decimal | None


class MeResponse(BaseModel):
    id: UUID
    # users.email is nullable (phone-only auth later); null on the wire is
    # honest — "" would pass for a (broken) address downstream.
    email: str | None
    role: str
    applicant: ApplicantRead | None = None


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeResponse:
    payload = MeResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
    )
    if user.role == UserRole.APPLICANT:
        row = (
            await session.execute(
                select(Applicant).where(
                    Applicant.user_id == user.id,
                    Applicant.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            # Should not happen — sign-in auto-provisions an applicants row.
            raise HTTPException(500, "applicant_missing")
        payload.applicant = ApplicantRead.model_validate(row, from_attributes=True)
    return payload
