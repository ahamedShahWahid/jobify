"""GET /v1/jobs/{id} — single job + employer + match for current applicant.
POST /v1/jobs — create a new job posting (recruiter-only).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import (
    _require_recruiter,
    _require_recruiter_at_employer,
    current_user,
)
from kpa.db.models import (
    Applicant,
    Employer,
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
        job=JobRead.model_validate(job),
        employer=EmployerRead(
            id=employer.id,
            name=employer.name,
            verified=employer.verified_at is not None,
        ),
        match=MatchRead.model_validate(match) if match is not None else None,
    )


class _LazyEmbedJob:
    """Lazy proxy for the ``embed_job`` Celery task.

    The real task lives in ``kpa.workers.tasks.embed_job``, which imports
    ``kpa.workers.celery_app`` at module level — that module calls
    ``Settings()`` immediately and requires KPA_* env vars.  A module-level
    import of the task would break test collection (conftest loads
    ``app_factory`` before ``pytest_configure`` sets the env-var defaults).

    Exposing this proxy as a module-level name lets tests replace it via
    ``monkeypatch.setattr(jobs_mod, "embed_job", _Stub())`` while keeping the
    real import deferred until the first actual dispatch call.
    """

    _task: Any = None  # populated on first use; class-level so the proxy is stateless

    def delay(self, job_id: str) -> None:
        if self._task is None:
            from kpa.workers.tasks.embed_job import embed_job as _t

            type(self)._task = _t
        self._task.delay(job_id)


embed_job: _LazyEmbedJob = _LazyEmbedJob()


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employer_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
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

    try:
        embed_job.delay(str(job.id))
    except Exception:
        _log.warning("embed.dispatch-failed", job_id=str(job.id), exc_info=True)

    return JobRead.model_validate(job)
