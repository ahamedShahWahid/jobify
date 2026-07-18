"""Applicant profile update — PATCH /v1/applicants/me.

The authenticated applicant edits their own profile fields. A change to
years_experience stages a durable rescore intent in the update transaction (it
feeds the structured score). locations/expected_ctc moved to
applicant_preferences — see PATCH /v1/applicants/me/preferences below.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import ApplicantPreferences, RoleCategory, User
from jobify.outbox import enqueue_task
from jobify_api.auth.dependencies import (
    current_user,
)
from jobify_api.auth.dependencies import (
    require_applicant as _require_applicant,
)
from jobify_api.dependencies import get_session
from jobify_api.routes.me import ApplicantRead, MeResponse

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/applicants/me", tags=["applicants"])

# Fields whose change must trigger a rescore (they drive the structured score).
_MATCHING_FIELDS = {"years_experience"}
# Rescore-trigger fields for the preferences endpoint below (same purpose as
# _MATCHING_FIELDS; the sets are disjoint).
_PREFERENCES_MATCHING_FIELDS = {"locations", "expected_ctc"}


class ProfileUpdate(BaseModel):
    """Partial profile update. Only keys present in the request are applied
    (`model_fields_set`); an explicit null clears a nullable column.
    `full_name` is non-nullable and rejects an explicit null."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    current_ctc: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))
    years_experience: Decimal | None = Field(default=None, ge=0, le=Decimal("60"))

    @model_validator(mode="after")
    def _no_null_for_required(self) -> ProfileUpdate:
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("full_name cannot be null")
        return self


@router.patch("", response_model=MeResponse, status_code=status.HTTP_200_OK)
async def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeResponse:
    applicant = await _require_applicant(user, session)

    changed_matching = False
    # setattr-from-model_fields_set is safe only because extra="forbid" closes
    # the field set to declared columns — removing it opens mass assignment.
    for name in payload.model_fields_set:
        setattr(applicant, name, getattr(payload, name))
        if name in _MATCHING_FIELDS:
            changed_matching = True
    if changed_matching:
        enqueue_task(session, "jobify.score_applicant", str(applicant.id))
    await session.flush()
    await session.commit()
    await session.refresh(applicant)

    response = MeResponse(
        id=user.id,
        email=user.email or "",
        role=user.role.value,
        applicant=ApplicantRead.model_validate(applicant, from_attributes=True),
    )
    return response


class PreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    desired_role: RoleCategory | None
    locations: list[str]
    expected_ctc: Decimal | None


class PreferencesUpdate(BaseModel):
    """Partial preferences update — same partial-update contract as
    ProfileUpdate. `desired_role`/`expected_ctc` are nullable and accept an
    explicit null to clear; `locations` is non-nullable (empty list clears
    it instead)."""

    model_config = ConfigDict(extra="forbid")

    desired_role: RoleCategory | None = Field(default=None)
    locations: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(
        default=None, max_length=10
    )
    expected_ctc: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))

    @model_validator(mode="after")
    def _no_null_for_locations(self) -> PreferencesUpdate:
        if "locations" in self.model_fields_set and self.locations is None:
            raise ValueError("locations cannot be null")
        return self


async def _require_preferences_row(
    applicant_id: UUID, session: AsyncSession
) -> ApplicantPreferences:
    """Every applicant gets a live preferences row eagerly at signup
    (AuthService._upsert_identity) — a missing row here is unreachable in
    the real system but guarded defensively, same shape as
    require_applicant's applicant_missing 500."""
    row = (
        await session.execute(
            select(ApplicantPreferences).where(
                ApplicantPreferences.applicant_id == applicant_id,
                ApplicantPreferences.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        _log.error("preferences.row-missing-for-applicant", applicant_id=str(applicant_id))
        raise HTTPException(status_code=500, detail="applicant_preferences_missing")
    return row


@router.get("/preferences", response_model=PreferencesRead, status_code=status.HTTP_200_OK)
async def get_preferences(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PreferencesRead:
    applicant = await _require_applicant(user, session)
    row = await _require_preferences_row(applicant.id, session)
    return PreferencesRead.model_validate(row, from_attributes=True)


@router.patch("/preferences", response_model=PreferencesRead, status_code=status.HTTP_200_OK)
async def update_preferences(
    payload: PreferencesUpdate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PreferencesRead:
    applicant = await _require_applicant(user, session)
    row = await _require_preferences_row(applicant.id, session)

    changed_matching = False
    # setattr-from-model_fields_set is safe only because extra="forbid" closes
    # the field set to declared columns — removing it opens mass assignment.
    for name in payload.model_fields_set:
        setattr(row, name, getattr(payload, name))
        if name in _PREFERENCES_MATCHING_FIELDS:
            changed_matching = True
    if changed_matching:
        enqueue_task(session, "jobify.score_applicant", str(applicant.id))
    await session.flush()
    await session.commit()
    await session.refresh(row)

    return PreferencesRead.model_validate(row, from_attributes=True)
