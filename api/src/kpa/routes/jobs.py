"""GET /v1/jobs/{id} — single job + employer + match for current applicant."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import current_user
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
