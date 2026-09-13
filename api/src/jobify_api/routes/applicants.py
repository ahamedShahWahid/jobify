"""Applicant profile update — PATCH /v1/applicants/me.

The authenticated applicant edits their own profile fields. A change to
years_experience stages a durable rescore intent in the update transaction (it
feeds the structured score). locations/expected_ctc moved to
applicant_preferences — see PATCH /v1/applicants/me/preferences below.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Applicant, ApplicantPreferences, RoleCategory, User
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
# _MATCHING_FIELDS; the sets are disjoint). `language` doesn't change the
# structured score — it's here so a language switch regenerates the LLM match
# explanation in the applicant's chosen language (scores identical).
_PREFERENCES_MATCHING_FIELDS = {"locations", "expected_ctc", "language"}


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
        # NOT `or ""` — MeResponse.email is `str | None` on purpose (see
        # routes/me.py): null on the wire is honest, whereas "" would pass for
        # a broken address downstream. GET /v1/me and this PATCH must agree.
        email=user.email,
        role=user.role.value,
        applicant=ApplicantRead.model_validate(applicant, from_attributes=True),
    )
    return response


class PreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    desired_role: RoleCategory | None
    locations: list[str]
    expected_ctc: Decimal | None
    language: Literal["en", "hi"]


class PreferencesUpdate(BaseModel):
    """Partial preferences update — same partial-update contract as
    ProfileUpdate. `desired_role`/`expected_ctc` are nullable and accept an
    explicit null to clear; `locations` is non-nullable (empty list clears
    it instead); `language` is non-nullable (a bare `Literal` rejects an
    explicit null with a 422, same as `locations`)."""

    model_config = ConfigDict(extra="forbid")

    desired_role: RoleCategory | None = Field(default=None)
    locations: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(
        default=None, max_length=10
    )
    expected_ctc: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))
    language: Literal["en", "hi"] = Field(default="en")

    @model_validator(mode="after")
    def _no_null_for_locations(self) -> PreferencesUpdate:
        if "locations" in self.model_fields_set and self.locations is None:
            raise ValueError("locations cannot be null")
        return self


async def _require_preferences_row(
    applicant_id: UUID, session: AsyncSession
) -> ApplicantPreferences:
    """Return the applicant's live preferences row, provisioning it if it never
    existed.

    New applicants get the row eagerly at signup (AuthService._upsert_identity),
    but accounts created before migration 0021 had none until 0028 backfilled
    them — and seeded/out-of-band applicants can still lack one. "No row at all"
    is therefore provisioned with defaults. A row that exists but is only
    soft-deleted is a different case: an invariant violation surfaced as the
    pinned 500 slug, never silently resurrected."""
    rows = (
        (
            await session.execute(
                select(ApplicantPreferences).where(
                    ApplicantPreferences.applicant_id == applicant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    live = next((row for row in rows if row.deleted_at is None), None)
    if live is not None:
        return live
    if rows:
        _log.error("preferences.row-missing-for-applicant", applicant_id=str(applicant_id))
        raise HTTPException(status_code=500, detail="applicant_preferences_missing")

    # INSERT … SELECT from the LIVE applicant, not VALUES: a DSR erasure that
    # committed after require_applicant (prefs hard-deleted, applicant
    # soft-deleted) leaves "no row at all", and a bare VALUES insert would
    # recreate a live row — which PATCH then fills with location/CTC. ON
    # CONFLICT against the live partial-unique index: concurrent first reads
    # (the client fires several in parallel) must not trip a unique violation.
    await session.execute(
        insert(ApplicantPreferences)
        .from_select(
            ["applicant_id"],
            select(Applicant.id).where(
                Applicant.id == applicant_id, Applicant.deleted_at.is_(None)
            ),
        )
        .on_conflict_do_nothing(
            index_elements=[ApplicantPreferences.applicant_id],
            index_where=ApplicantPreferences.deleted_at.is_(None),
        )
    )
    await session.commit()
    live = (
        await session.execute(
            select(ApplicantPreferences).where(
                ApplicantPreferences.applicant_id == applicant_id,
                ApplicantPreferences.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if live is None:
        _log.error("preferences.row-missing-for-applicant", applicant_id=str(applicant_id))
        raise HTTPException(status_code=500, detail="applicant_preferences_missing")
    _log.warning("preferences.row-provisioned", applicant_id=str(applicant_id))
    return live


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
