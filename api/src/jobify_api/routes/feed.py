"""GET /v1/feed — paginated ranked matches for the current applicant.

Cursor pagination via opaque base64 of {score, match_id[, f]} (f = optional
filter-set hash, binding the cursor to the filters it was minted under).
ETag is weak, keyed off (applicant_id, max(updated_at), count). 401/403
ladder reuses the current_user + require_applicant deps from
jobify_api.auth.dependencies.

Shared response shapes (JobRead, EmployerRead, …) live in
``routes/schemas.py``; cursor/ETag primitives in ``jobify.pagination``.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import StringConstraints
from sqlalchemy import and_, exists, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Employer,
    Job,
    JobStatus,
    Match,
    MatchFeedback,
    MatchFeedbackRating,
    User,
)
from jobify_api.auth.dependencies import (
    current_user,
)
from jobify_api.auth.dependencies import (
    require_applicant as _require_applicant,
)
from jobify_api.dependencies import get_session
from jobify_api.pagination import decode_cursor as _decode_cursor_payload
from jobify_api.pagination import encode_cursor as _encode_cursor_payload
from jobify_api.pagination import make_weak_etag
from jobify_api.routes.schemas import (
    EmployerRead,
    FeedItemRead,
    FeedResponse,
    JobSummaryRead,
    MatchRead,
)

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["feed"])


# --- Cursor helpers (typed wrappers over jobify.pagination) ---


def filters_hash(
    q: str | None,
    locations: list[str] | None,
    min_years: int | None,
    min_ctc: Decimal | None,
) -> str | None:
    """Short stable hash of the canonicalized filter set; None = no filters.

    Inputs must already be normalized (trimmed, empties dropped) — this
    function only canonicalizes case + location order.
    """
    if q is None and not locations and min_years is None and min_ctc is None:
        return None
    canon = json.dumps(
        {
            "q": q.lower() if q is not None else None,
            "loc": sorted(loc.lower() for loc in locations) if locations else None,
            "years": min_years,
            "ctc": str(min_ctc) if min_ctc is not None else None,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def encode_cursor(score: Decimal, match_id: uuid.UUID, fhash: str | None = None) -> str:
    """Pack (score, match_id[, filter-set hash]) into an opaque base64 string."""
    payload: dict[str, str] = {"score": str(score), "match_id": str(match_id)}
    if fhash is not None:
        payload["f"] = fhash
    return _encode_cursor_payload(payload)


def decode_cursor(cursor: str) -> tuple[Decimal, uuid.UUID, str | None]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    payload = _decode_cursor_payload(cursor)
    try:
        f = payload.get("f")
        if f is not None and not isinstance(f, str):
            raise TypeError("f is not a string")
        return Decimal(payload["score"]), uuid.UUID(payload["match_id"]), f
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        # ArithmeticError covers decimal.InvalidOperation on a garbage score.
        raise ValueError(f"invalid_cursor: {exc}") from exc


_LIKE_ESCAPE = "\\"


def _escape_like(term: str) -> str:
    """Escape ILIKE metacharacters so user input matches literally."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


_LocationItem = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    request: Request,
    response: Response,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    q: str | None = Query(None, max_length=100),
    location: list[_LocationItem] | None = Query(None, max_length=20),  # noqa: B008
    min_years: int | None = Query(None, ge=0, le=80),
    min_ctc: Decimal | None = Query(None, ge=0),  # noqa: B008
) -> FeedResponse | Response:
    applicant = await _require_applicant(user, session)

    # Normalize BEFORE hashing so the cursor hash sees canonical values.
    q_norm = (q or "").strip() or None
    locations = list(location or [])
    fhash = filters_hash(q_norm, locations, min_years, min_ctc)

    cursor_score: Decimal | None = None
    cursor_mid: uuid.UUID | None = None
    if cursor is not None:
        try:
            cursor_score, cursor_mid, cursor_f = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid_cursor") from None
        if cursor_f != fhash:
            # A cursor minted under a different filter set can't be resumed —
            # silently mixing pages would be worse than a clean 400.
            raise HTTPException(status_code=400, detail="invalid_cursor")

    # Query: match JOIN job JOIN employer; surfaced + live + open. One outer
    # join to the live feedback row does double duty: rating='down' EXCLUDES
    # the job; rating='up' is surfaced as match.my_feedback. The deleted_at
    # and key predicates MUST stay in the ON clause — in WHERE they would
    # turn the outer join inner and a soft-deleted (cleared) rating would
    # silently drop the row.
    stmt = (
        select(Match, Job, Employer, MatchFeedback.rating, MatchFeedback.updated_at)
        .join(Job, Job.id == Match.job_id)
        .join(Employer, Employer.id == Job.employer_id)
        .outerjoin(
            MatchFeedback,
            and_(
                MatchFeedback.applicant_id == Match.applicant_id,
                MatchFeedback.job_id == Match.job_id,
                MatchFeedback.deleted_at.is_(None),
            ),
        )
        .where(
            Match.applicant_id == applicant.id,
            Match.deleted_at.is_(None),
            Match.surfaced_at.is_not(None),
            Job.deleted_at.is_(None),
            Job.status == JobStatus.OPEN,
            Employer.deleted_at.is_(None),
            or_(
                MatchFeedback.id.is_(None),
                MatchFeedback.rating != MatchFeedbackRating.DOWN.value,
            ),
        )
        .order_by(Match.total_score.desc(), Match.id.desc())
        .limit(limit + 1)  # peek-one
    )
    if q_norm is not None:
        pat = f"%{_escape_like(q_norm)}%"
        stmt = stmt.where(
            or_(
                Job.title.ilike(pat, escape=_LIKE_ESCAPE),
                Employer.name.ilike(pat, escape=_LIKE_ESCAPE),
            )
        )
    if locations:
        loc_el = (
            func.unnest(Job.locations).table_valued("value", joins_implicitly=True).render_derived()
        )
        stmt = stmt.where(
            exists(
                select(literal(1))
                .select_from(loc_el)
                .where(func.lower(loc_el.c.value).in_([loc.lower() for loc in locations]))
            )
        )
    if min_years is not None:
        stmt = stmt.where(Job.min_exp_years <= min_years, Job.max_exp_years >= min_years)
    if min_ctc is not None:
        stmt = stmt.where(or_(Job.ctc_max.is_(None), Job.ctc_max >= min_ctc))
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
    for match, job, employer, my_rating, feedback_updated_at in rows:
        match_read = MatchRead.model_validate(match).model_copy(update={"my_feedback": my_rating})
        items.append(
            FeedItemRead(
                match=match_read,
                job=JobSummaryRead.from_job_and_employer(job, employer),
                employer=EmployerRead(
                    id=employer.id,
                    name=employer.name,
                    verified=employer.verified_at is not None,
                ),
            )
        )
        if max_updated_at is None or match.updated_at > max_updated_at:
            max_updated_at = match.updated_at
        if feedback_updated_at is not None and (
            max_updated_at is None or feedback_updated_at > max_updated_at
        ):
            max_updated_at = feedback_updated_at

    next_cursor: str | None = None
    if has_more and rows:
        last_match = rows[-1][0]
        next_cursor = encode_cursor(last_match.total_score, last_match.id, fhash)

    etag = make_weak_etag(applicant.id, max_updated_at, len(items))
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag

    return FeedResponse(items=items, next_cursor=next_cursor)
