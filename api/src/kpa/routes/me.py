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

from kpa.auth.dependencies import current_user
from kpa.db.models import Applicant, User, UserRole
from kpa.db.session import get_session

router = APIRouter(prefix="/v1", tags=["me"])


class ApplicantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    locations: list[str]
    notice_period_days: int | None
    current_ctc: Decimal | None
    expected_ctc: Decimal | None
    years_experience: Decimal | None


class MeResponse(BaseModel):
    id: UUID
    email: str
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
        email=user.email or "",
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
