"""GET /v1/feed — paginated ranked matches for the current applicant.

Cursor pagination via opaque base64 of {score, match_id}. ETag is weak,
keyed off (applicant_id, max(updated_at), count). 401/403 ladder reuses the
existing current_user + _require_applicant deps from auth + resumes routes.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# --- Pydantic *Read models ---


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    total_score: float
    vector_score: float
    structured_score: float
    # DB column is score_components; wire shape is components (per spec §P2.3).
    components: dict[str, float] = Field(validation_alias="score_components")
    surfaced_at: datetime | None
    explanation: dict[str, str] | None


class EmployerRead(BaseModel):
    """Wire shape: a verified bool, not the underlying verified_at timestamp."""

    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    name: str
    verified: bool


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    locations: list[str]
    min_exp_years: int
    max_exp_years: int
    ctc_min: float | None
    ctc_max: float | None
    # StrEnum → serializes as its string value ("open"/"closed"). The web/mobile
    # client uses this to render closed-role state on the saved list.
    status: str
    posted_at: datetime
    employer_verified: bool

    @classmethod
    def from_job_and_employer(
        cls,
        job: Job,
        employer: Employer,
    ) -> JobRead:
        """Build a JobRead from a Job ORM row and its associated Employer row.

        Single construction point so every caller sets employer_verified
        consistently. The field is required (no default) to force all future
        callers through here.
        """
        return cls.model_validate(
            {
                "id": job.id,
                "title": job.title,
                "description": job.description,
                "locations": job.locations,
                "min_exp_years": job.min_exp_years,
                "max_exp_years": job.max_exp_years,
                "ctc_min": float(job.ctc_min) if job.ctc_min is not None else None,
                "ctc_max": float(job.ctc_max) if job.ctc_max is not None else None,
                "status": job.status.value,
                "posted_at": job.posted_at,
                "employer_verified": employer.verified_at is not None,
            }
        )


class FeedItemRead(BaseModel):
    match: MatchRead
    job: JobRead
    employer: EmployerRead


class FeedResponse(BaseModel):
    items: list[FeedItemRead]
    next_cursor: str | None


class JobDetailResponse(BaseModel):
    job: JobRead
    employer: EmployerRead
    match: MatchRead | None


# --- Cursor helpers ---


def encode_cursor(score: Decimal, match_id: uuid.UUID) -> str:
    """Pack (score, match_id) into an opaque base64 string."""
    payload = {"score": str(score), "match_id": str(match_id)}
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> tuple[Decimal, uuid.UUID]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw)
        return Decimal(payload["score"]), uuid.UUID(payload["match_id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError(f"invalid_cursor: {exc}") from exc


# --- ETag helper ---


def make_weak_etag(*parts: object) -> str:
    """W/\"<sha256-hex>\" of str-rendered parts joined by '|'.

    Weak ETag because the body is computed from joined data — we promise
    semantic equivalence, not byte-exact reproducibility.
    """
    raw = "|".join(str(p) for p in parts)
    return f'W/"{hashlib.sha256(raw.encode("utf-8")).hexdigest()}"'


# --- Imports for the handler section ---
import structlog  # noqa: E402
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from sqlalchemy import literal, select, tuple_  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from kpa.auth.dependencies import current_user  # noqa: E402
from kpa.db.models import (  # noqa: E402
    Applicant,
    Employer,
    Job,
    JobStatus,
    Match,
    User,
    UserRole,
)
from kpa.db.session import get_session  # noqa: E402

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["feed"])


async def _require_applicant(
    user: User,
    session: AsyncSession,
) -> Applicant:
    """Reject recruiter/admin tokens with 403 before any applicant-row read.

    Mirrors `routes/resumes.py:_require_applicant`. Don't extract to a shared
    helper in this slice — the resumes version has different downstream
    error semantics (500 applicant_missing) that the feed doesn't need.
    """
    if user.role != UserRole.APPLICANT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_an_applicant")
    applicant = (
        await session.execute(select(Applicant).where(Applicant.user_id == user.id))
    ).scalar_one_or_none()
    if applicant is None:
        # Defense in depth — sign-in provisions the applicants row.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="applicant_missing",
        )
    return applicant


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
