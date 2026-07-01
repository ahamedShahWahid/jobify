"""Applicant profile update — PATCH /v1/applicants/me.

The authenticated applicant edits their own profile fields. A change to
years_experience fires a fire-and-forget rescore post-commit (it feeds the
structured score). locations/expected_ctc moved to
applicant_preferences — see PATCH /v1/applicants/me/preferences below.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import User
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
# Same list, for the preferences endpoint below.
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


def _dispatch_score(applicant_id: UUID) -> None:
    """Fire score_applicant dispatch post-commit, fire-and-forget. A broker
    outage MUST NOT fail the save — same pattern as embed.py:_dispatch_score."""
    from jobify.celery_app import enqueue

    try:
        enqueue("jobify.score_applicant", str(applicant_id))
    except Exception:
        _log.warning("score.dispatch-failed", applicant_id=str(applicant_id), exc_info=True)


@router.patch("", response_model=MeResponse, status_code=status.HTTP_200_OK)
async def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeResponse:
    applicant = await _require_applicant(user, session)

    changed_matching = False
    for name in payload.model_fields_set:
        setattr(applicant, name, getattr(payload, name))
        if name in _MATCHING_FIELDS:
            changed_matching = True
    await session.flush()
    await session.commit()
    await session.refresh(applicant)

    response = MeResponse(
        id=user.id,
        email=user.email or "",
        role=user.role.value,
        applicant=ApplicantRead.model_validate(applicant, from_attributes=True),
    )
    if changed_matching:
        _dispatch_score(applicant.id)
    return response
