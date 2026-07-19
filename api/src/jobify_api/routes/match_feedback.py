"""Match feedback — applicant thumbs up/down on a surfaced match.

PUT    /v1/jobs/{job_id}/match-feedback  {"rating": "up"|"down"} → 200 stored row.
DELETE /v1/jobs/{job_id}/match-feedback  → 204 (soft-delete; no-op if absent).

A rating requires a live, SURFACED match on a live job — uniform 404 otherwise
(never leaks job existence). rating='down' excludes the job from /v1/feed
(see routes/feed.py). Keyed on (applicant_id, job_id): re-rate UPDATEs the
live row; re-rate after DELETE inserts a fresh row (saved_jobs precedent).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Job, Match, MatchFeedback, User
from jobify_api.auth.dependencies import current_user
from jobify_api.auth.dependencies import require_applicant as _require_applicant
from jobify_api.dependencies import get_session

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["match_feedback"])


class MatchFeedbackWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Literal["up", "down"]


class MatchFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    rating: Literal["up", "down"]
    created_at: datetime
    updated_at: datetime


async def _load_surfaced_match(
    session: AsyncSession, *, applicant_id: uuid.UUID, job_id: uuid.UUID
) -> Match | None:
    """The applicant's live surfaced match on a live job — or None (→ 404)."""
    return (
        await session.execute(
            select(Match)
            .join(Job, Job.id == Match.job_id)
            .where(
                Match.applicant_id == applicant_id,
                Match.job_id == job_id,
                Match.deleted_at.is_(None),
                Match.surfaced_at.is_not(None),
                Job.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


@router.put(
    "/jobs/{job_id}/match-feedback",
    status_code=status.HTTP_200_OK,
    response_model=MatchFeedbackRead,
)
async def put_match_feedback(
    job_id: uuid.UUID,
    body: MatchFeedbackWrite,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MatchFeedbackRead:
    """Rate the current applicant's surfaced match for this job (idempotent upsert).

    Error ladder: 401 (auth) → 403 (role) → 404 (no live surfaced match).
    """
    applicant = await _require_applicant(user, session)

    match = await _load_surfaced_match(session, applicant_id=applicant.id, job_id=job_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="match_not_found")

    existing = (
        await session.execute(
            select(MatchFeedback).where(
                MatchFeedback.applicant_id == applicant.id,
                MatchFeedback.job_id == job_id,
                MatchFeedback.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.rating = body.rating
        await session.commit()
        await session.refresh(existing)
        row = existing
    else:
        row = MatchFeedback(applicant_id=applicant.id, job_id=job_id, rating=body.rating)
        session.add(row)
        await session.commit()
        await session.refresh(row)

    _log.info(
        "match_feedback.rated",
        job_id=str(job_id),
        rating=body.rating,
    )
    return MatchFeedbackRead.model_validate(row)


@router.delete(
    "/jobs/{job_id}/match-feedback",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_match_feedback(
    job_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Clear the rating (soft-delete). 204 whether or not a live row existed —
    the UI calls this optimistically (Undo). Error ladder: 401 → 403 only."""
    applicant = await _require_applicant(user, session)

    existing = (
        await session.execute(
            select(MatchFeedback).where(
                MatchFeedback.applicant_id == applicant.id,
                MatchFeedback.job_id == job_id,
                MatchFeedback.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.execute(
            update(MatchFeedback)
            .where(MatchFeedback.id == existing.id)
            .values(deleted_at=func.now(), updated_at=func.now())
        )
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
