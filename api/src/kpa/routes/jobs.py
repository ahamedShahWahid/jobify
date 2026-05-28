"""GET /v1/jobs/{id} — single job + employer + match for current applicant.
GET /v1/jobs/me — recruiter's own jobs with counts + cursor pagination.
POST /v1/jobs — create a new job posting (recruiter-only).
"""

from __future__ import annotations

import base64
import json as _json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import (
    _require_recruiter,
    _require_recruiter_at_employer,
    current_user,
)
from kpa.db.models import (
    Applicant,
    Application,
    Employer,
    EmployerUser,
    Job,
    JobStatus,
    Match,
    User,
    UserRole,
)
from kpa.db.session import get_session
from kpa.routes.feed import (
    EmployerRead,
    JobDetailResponse,
    JobRead,
    MatchRead,
    make_weak_etag,
)

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["jobs"])


async def _require_applicant(
    user: User,
    session: AsyncSession,
) -> Applicant:
    if user.role != UserRole.APPLICANT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_an_applicant")
    applicant = (
        await session.execute(select(Applicant).where(Applicant.user_id == user.id))
    ).scalar_one_or_none()
    if applicant is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="applicant_missing",
        )
    return applicant


class RecruiterJobRow(JobRead):
    applicant_count: int
    surfaced_match_count: int


class RecruiterJobsPage(BaseModel):
    items: list[RecruiterJobRow]
    next_cursor: str | None


def _encode_jobs_me_cursor(posted_at: datetime, job_id: uuid.UUID) -> str:
    raw = _json.dumps({"posted_at": posted_at.isoformat(), "id": str(job_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_jobs_me_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        obj = _json.loads(raw)
        return datetime.fromisoformat(obj["posted_at"]), uuid.UUID(obj["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid_cursor") from e


# NOTE: /v1/jobs/me MUST be registered BEFORE /v1/jobs/{job_id} — FastAPI
# matches routes in declaration order, and otherwise "me" is interpreted as
# a (failing) UUID path-param.
@router.get("/jobs/me", response_model=RecruiterJobsPage)
async def list_my_jobs(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> RecruiterJobsPage:
    await _require_recruiter(user)

    applicant_count_expr = func.count(
        distinct(
            case(
                (
                    and_(
                        Application.deleted_at.is_(None),
                        Application.status == "applied",
                    ),
                    Application.id,
                ),
            )
        )
    ).label("applicant_count")
    surfaced_match_count_expr = func.count(
        distinct(
            case(
                (
                    and_(
                        Match.deleted_at.is_(None),
                        Match.surfaced_at.is_not(None),
                    ),
                    Match.id,
                ),
            )
        )
    ).label("surfaced_match_count")

    stmt = (
        select(Job, Employer, applicant_count_expr, surfaced_match_count_expr)
        .join(EmployerUser, EmployerUser.employer_id == Job.employer_id)
        .join(Employer, Employer.id == Job.employer_id)
        .outerjoin(Application, Application.job_id == Job.id)
        .outerjoin(Match, Match.job_id == Job.id)
        .where(
            EmployerUser.user_id == user.id,
            EmployerUser.deleted_at.is_(None),
            Job.deleted_at.is_(None),
        )
        .group_by(Job.id, Employer.id)
        .order_by(Job.posted_at.desc(), Job.id.desc())
    )

    if status_filter is None:
        stmt = stmt.where(Job.status == JobStatus.OPEN)
    # ?status=closed surfaces both open + closed (the recruiter's full view).

    if cursor is not None:
        cur_posted, cur_id = _decode_jobs_me_cursor(cursor)
        stmt = stmt.where(
            or_(
                Job.posted_at < cur_posted,
                and_(Job.posted_at == cur_posted, Job.id < cur_id),
            )
        )

    stmt = stmt.limit(limit + 1)
    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items: list[RecruiterJobRow] = []
    for row in rows:
        job, employer, applicant_count, surfaced_match_count = row
        base = JobRead.from_job_and_employer(job, employer)
        items.append(
            RecruiterJobRow(
                **base.model_dump(),
                applicant_count=applicant_count or 0,
                surfaced_match_count=surfaced_match_count or 0,
            )
        )

    next_cursor = (
        _encode_jobs_me_cursor(rows[-1][0].posted_at, rows[-1][0].id)
        if has_more and rows
        else None
    )
    return RecruiterJobsPage(items=items, next_cursor=next_cursor)


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(
    request: Request,
    response: Response,
    job_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> JobDetailResponse | Response:
    applicant = await _require_applicant(user, session)

    # Job + employer, uniform 404 across unknown / closed / soft-deleted.
    row = (
        await session.execute(
            select(Job, Employer)
            .join(Employer, Employer.id == Job.employer_id)
            .where(
                Job.id == job_id,
                Job.deleted_at.is_(None),
                Job.status == JobStatus.OPEN,
                Employer.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    job, employer = row

    match = (
        await session.execute(
            select(Match).where(
                Match.applicant_id == applicant.id,
                Match.job_id == job_id,
                Match.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    etag_parts: list[object] = [job.id, job.updated_at]
    if match is not None:
        etag_parts.append(match.updated_at)
    etag = make_weak_etag(*etag_parts)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag

    return JobDetailResponse(
        job=JobRead.from_job_and_employer(job, employer),
        employer=EmployerRead(
            id=employer.id,
            name=employer.name,
            verified=employer.verified_at is not None,
        ),
        match=MatchRead.model_validate(match) if match is not None else None,
    )



class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employer_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=10, max_length=10_000)
    locations: list[str] = Field(min_length=1, max_length=20)
    min_exp_years: int = Field(ge=0, le=50)
    max_exp_years: int = Field(ge=0, le=50)
    ctc_min: Decimal | None = Field(default=None, ge=0)
    ctc_max: Decimal | None = Field(default=None, ge=0)
    status: Literal["open", "closed"] = "open"

    @model_validator(mode="after")
    def _ordered_bands(self) -> JobCreate:
        if self.max_exp_years < self.min_exp_years:
            raise ValueError("max_exp_years must be >= min_exp_years")
        if (
            self.ctc_min is not None
            and self.ctc_max is not None
            and self.ctc_max < self.ctc_min
        ):
            raise ValueError("ctc_max must be >= ctc_min")
        return self


@router.post("/jobs", response_model=JobRead, status_code=201)
async def create_job(
    payload: JobCreate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> JobRead:
    await _require_recruiter(user)
    await _require_recruiter_at_employer(user, payload.employer_id, session)

    job = Job(
        employer_id=payload.employer_id,
        title=payload.title,
        description=payload.description,
        locations=payload.locations,
        min_exp_years=payload.min_exp_years,
        max_exp_years=payload.max_exp_years,
        ctc_min=payload.ctc_min,
        ctc_max=payload.ctc_max,
        status=JobStatus(payload.status),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Lazy import: kpa.workers.celery_app instantiates Settings() at module
    # level (needs KPA_REDIS_URL). Deferring the import to request time avoids
    # import-time failures in test collection where env vars aren't yet set.
    try:
        from kpa.workers.tasks.embed_job import embed_job

        embed_job.delay(str(job.id))
    except Exception:
        _log.warning("embed.dispatch-failed", job_id=str(job.id), exc_info=True)

    emp = await session.scalar(select(Employer).where(Employer.id == job.employer_id))
    if emp is None:  # pragma: no cover — FK constraint makes this unreachable
        raise HTTPException(status_code=500, detail="employer_missing")
    return JobRead.from_job_and_employer(job, emp)


_EMBED_TRIGGERING_FIELDS = frozenset(
    {
        "title",
        "description",
        "locations",
        "min_exp_years",
        "max_exp_years",
        "ctc_min",
        "ctc_max",
    }
)


class JobPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=10_000)
    locations: list[str] | None = Field(default=None, min_length=1, max_length=20)
    min_exp_years: int | None = Field(default=None, ge=0, le=50)
    max_exp_years: int | None = Field(default=None, ge=0, le=50)
    ctc_min: Decimal | None = Field(default=None, ge=0)
    ctc_max: Decimal | None = Field(default=None, ge=0)
    status: Literal["open", "closed"] | None = None


async def _load_recruiter_job(
    job_id: uuid.UUID, user: User, session: AsyncSession
) -> Job:
    """Uniform 404 for unknown / wrong-employer / soft-deleted job."""
    await _require_recruiter(user)
    row = await session.execute(
        select(Job)
        .join(EmployerUser, EmployerUser.employer_id == Job.employer_id)
        .where(
            Job.id == job_id,
            Job.deleted_at.is_(None),
            EmployerUser.user_id == user.id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    job = row.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="not found")
    return job


@router.patch("/jobs/{job_id}", response_model=JobRead)
async def patch_job(
    job_id: uuid.UUID,
    payload: JobPatch,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> JobRead:
    job = await _load_recruiter_job(job_id, user, session)

    fields = payload.model_dump(exclude_unset=True)
    content_changed = bool(_EMBED_TRIGGERING_FIELDS & fields.keys())

    for key, value in fields.items():
        if key == "status":
            setattr(job, key, JobStatus(value))
        else:
            setattr(job, key, value)
    await session.commit()
    await session.refresh(job)

    if content_changed:
        try:
            from kpa.workers.tasks.embed_job import embed_job

            embed_job.delay(str(job.id))
        except Exception:
            _log.warning("embed.dispatch-failed", job_id=str(job.id), exc_info=True)

    emp = await session.scalar(select(Employer).where(Employer.id == job.employer_id))
    if emp is None:  # pragma: no cover — FK constraint makes this unreachable
        raise HTTPException(status_code=500, detail="employer_missing")
    return JobRead.from_job_and_employer(job, emp)


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(
    job_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    job = await _load_recruiter_job(job_id, user, session)
    job.deleted_at = func.now()
    await session.commit()
    return Response(status_code=204)


