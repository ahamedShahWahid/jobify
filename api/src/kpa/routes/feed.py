"""GET /v1/feed — paginated ranked matches for the current applicant.

Cursor pagination via opaque base64 of {score, match_id}. ETag is weak,
keyed off (applicant_id, max(updated_at), count). 401/403 ladder reuses the
current_user + require_applicant deps from kpa.auth.dependencies.

Shared response shapes (JobRead, EmployerRead, …) live in
``routes/schemas.py``; cursor/ETag primitives in ``kpa.pagination``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import (
    current_user,
)
from kpa.auth.dependencies import (
    require_applicant as _require_applicant,
)
from kpa.db.models import Employer, Job, JobStatus, Match, User
from kpa.db.session import get_session
from kpa.pagination import decode_cursor as _decode_cursor_payload
from kpa.pagination import encode_cursor as _encode_cursor_payload
from kpa.pagination import make_weak_etag
from kpa.routes.schemas import (
    EmployerRead,
    FeedItemRead,
    FeedResponse,
    JobRead,
    MatchRead,
)

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["feed"])


# --- Cursor helpers (typed wrappers over kpa.pagination) ---


def encode_cursor(score: Decimal, match_id: uuid.UUID) -> str:
    """Pack (score, match_id) into an opaque base64 string."""
    return _encode_cursor_payload({"score": str(score), "match_id": str(match_id)})


def decode_cursor(cursor: str) -> tuple[Decimal, uuid.UUID]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    payload = _decode_cursor_payload(cursor)
    try:
        return Decimal(payload["score"]), uuid.UUID(payload["match_id"])
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        # ArithmeticError covers decimal.InvalidOperation on a garbage score.
        raise ValueError(f"invalid_cursor: {exc}") from exc


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    request: Request,
    response: Response,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
) -> FeedResponse | Response:
    applicant = await _require_applicant(user, session)

    cursor_score: Decimal | None = None
    cursor_mid: uuid.UUID | None = None
    if cursor is not None:
        try:
            cursor_score, cursor_mid = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid_cursor") from None

    # Query: match JOIN job JOIN employer; surfaced + live + open.
    stmt = (
        select(Match, Job, Employer)
        .join(Job, Job.id == Match.job_id)
        .join(Employer, Employer.id == Job.employer_id)
        .where(
            Match.applicant_id == applicant.id,
            Match.deleted_at.is_(None),
            Match.surfaced_at.is_not(None),
            Job.deleted_at.is_(None),
            Job.status == JobStatus.OPEN,
            Employer.deleted_at.is_(None),
        )
        .order_by(Match.total_score.desc(), Match.id.desc())
        .limit(limit + 1)  # peek-one
    )
    if cursor_score is not None and cursor_mid is not None:
        # Tuple comparison maps cleanly to (total_score DESC, id DESC) ordering.
        # literal() wraps plain Python values so SQLAlchemy (and mypy) treats
        # them as column expressions.
        stmt = stmt.where(
            tuple_(Match.total_score, Match.id) < tuple_(literal(cursor_score), literal(cursor_mid))
        )

    rows = (await session.execute(stmt)).all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items: list[FeedItemRead] = []
    max_updated_at: datetime | None = None
    for match, job, employer in rows:
        items.append(
            FeedItemRead(
                match=MatchRead.model_validate(match),
                job=JobRead.from_job_and_employer(job, employer),
                employer=EmployerRead(
                    id=employer.id,
                    name=employer.name,
                    verified=employer.verified_at is not None,
                ),
            )
        )
        if max_updated_at is None or match.updated_at > max_updated_at:
            max_updated_at = match.updated_at

    next_cursor: str | None = None
    if has_more and rows:
        last_match = rows[-1][0]
        next_cursor = encode_cursor(last_match.total_score, last_match.id)

    etag = make_weak_etag(applicant.id, max_updated_at, len(items))
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag

    return FeedResponse(items=items, next_cursor=next_cursor)
