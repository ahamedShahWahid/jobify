"""Admin Match QA — the relevance metric + the rated-matches list.

GET /v1/admin/match-feedback          — keyset-paginated rated matches
                                        (?rating=up|down filter).
GET /v1/admin/match-feedback/summary  — up-share all-time + rolling 30d;
                                        this is the BRD "match relevance"
                                        number (share = up / (up + down)).

Gated by _require_admin AFTER current_user (401 → 403 ladder), like every
admin route. Match join is OUTER (deleted_at in the ON clause) so a rating
whose match row was since soft-deleted still lists, with null score.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Employer,
    Job,
    Match,
    MatchFeedback,
    MatchFeedbackRating,
    User,
)
from jobify_api.auth.dependencies import _require_admin, current_user
from jobify_api.dependencies import get_session
from jobify_api.routes.admin._common import decode_admin_cursor, encode_admin_cursor

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class AdminMatchFeedbackRead(BaseModel):
    id: uuid.UUID
    rating: Literal["up", "down"]
    created_at: datetime
    updated_at: datetime
    job_id: uuid.UUID
    job_title: str
    employer_name: str
    applicant_id: uuid.UUID
    applicant_name: str | None  # null once DSR-tombstoned
    total_score: float | None  # null if the match row was soft-deleted since
    explanation: dict[str, str] | None


class AdminMatchFeedbackListResponse(BaseModel):
    items: list[AdminMatchFeedbackRead]
    next_cursor: str | None


class FeedbackWindowStats(BaseModel):
    up: int
    down: int
    share: float | None  # up / (up + down); null when nothing rated


class AdminMatchFeedbackSummary(BaseModel):
    all_time: FeedbackWindowStats
    last_30d: FeedbackWindowStats


@router.get("/match-feedback", response_model=AdminMatchFeedbackListResponse)
async def list_match_feedback(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    rating: Literal["up", "down"] | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AdminMatchFeedbackListResponse:
    await _require_admin(user)

    stmt = (
        select(MatchFeedback, Job, Employer, Applicant, Match)
        .join(Job, Job.id == MatchFeedback.job_id)
        .join(Employer, Employer.id == Job.employer_id)
        .join(Applicant, Applicant.id == MatchFeedback.applicant_id)
        .outerjoin(
            Match,
            and_(
                Match.applicant_id == MatchFeedback.applicant_id,
                Match.job_id == MatchFeedback.job_id,
                Match.deleted_at.is_(None),
            ),
        )
        .where(MatchFeedback.deleted_at.is_(None))
    )
    if rating is not None:
        stmt = stmt.where(MatchFeedback.rating == rating)
    if cursor is not None:
        cursor_created, cursor_id = decode_admin_cursor(cursor)
        stmt = stmt.where(
            (MatchFeedback.created_at < cursor_created)
            | ((MatchFeedback.created_at == cursor_created) & (MatchFeedback.id < cursor_id))
        )
    stmt = stmt.order_by(MatchFeedback.created_at.desc(), MatchFeedback.id.desc()).limit(limit + 1)

    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [
        AdminMatchFeedbackRead(
            id=fb.id,
            rating=fb.rating,  # DB CHECK pins the vocab to "up"/"down"
            created_at=fb.created_at,
            updated_at=fb.updated_at,
            job_id=job.id,
            job_title=job.title,
            employer_name=employer.name,
            applicant_id=applicant.id,
            applicant_name=applicant.full_name,
            total_score=float(match.total_score) if match is not None else None,
            explanation=match.explanation if match is not None else None,
        )
        for fb, job, employer, applicant, match in rows
    ]
    next_cursor = encode_admin_cursor(rows[-1][0].created_at, rows[-1][0].id) if has_more else None
    return AdminMatchFeedbackListResponse(items=items, next_cursor=next_cursor)


def _stats(up: int, down: int) -> FeedbackWindowStats:
    total = up + down
    return FeedbackWindowStats(up=up, down=down, share=round(up / total, 4) if total else None)


@router.get("/match-feedback/summary", response_model=AdminMatchFeedbackSummary)
async def match_feedback_summary(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AdminMatchFeedbackSummary:
    await _require_admin(user)

    cutoff = datetime.now(UTC) - timedelta(days=30)
    up_v = MatchFeedbackRating.UP.value
    down_v = MatchFeedbackRating.DOWN.value
    row = (
        await session.execute(
            select(
                func.count(case((MatchFeedback.rating == up_v, 1))),
                func.count(case((MatchFeedback.rating == down_v, 1))),
                func.count(
                    case(
                        (
                            and_(
                                MatchFeedback.rating == up_v,
                                MatchFeedback.created_at >= cutoff,
                            ),
                            1,
                        )
                    )
                ),
                func.count(
                    case(
                        (
                            and_(
                                MatchFeedback.rating == down_v,
                                MatchFeedback.created_at >= cutoff,
                            ),
                            1,
                        )
                    )
                ),
            ).where(MatchFeedback.deleted_at.is_(None))
        )
    ).one()
    return AdminMatchFeedbackSummary(
        all_time=_stats(row[0], row[1]),
        last_30d=_stats(row[2], row[3]),
    )
