"""Applicant-facing job detail — GET /v1/jobs/{job_id}.

Returns the job + employer + the caller's match/application/saved state. The match
is returned unconditionally when a row exists (ignores ``surfaced_at`` — a pasted
URL shows the score). Uniform 404 across unknown / closed / soft-deleted.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Application, Employer, Job, JobStatus, Match, SavedJob, User
from jobify_api.auth.dependencies import current_user
from jobify_api.auth.dependencies import require_applicant as _require_applicant
from jobify_api.dependencies import get_session
from jobify_api.pagination import make_weak_etag
from jobify_api.routes.schemas import (
    EmployerRead,
    JobDetailApplicationRead,
    JobDetailResponse,
    JobDetailSavedJobRead,
    JobRead,
    MatchRead,
)

router = APIRouter(prefix="/v1", tags=["jobs"])


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

    # Current applicant's live application for this job (any status — applied
    # or withdrawn — see CLAUDE.md "Applications + saved jobs routes": withdraw
    # does NOT soft-delete, it flips status). The Flutter ActionBar uses
    # status to decide between Apply / Withdraw, so we must include withdrawn
    # rows too — otherwise re-apply after withdraw won't UPDATE the existing
    # row and the partial-UNIQUE INSERT collides.
    application = (
        await session.execute(
            select(Application).where(
                Application.applicant_id == applicant.id,
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    saved_job = (
        await session.execute(
            select(SavedJob).where(
                SavedJob.applicant_id == applicant.id,
                SavedJob.job_id == job_id,
                SavedJob.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    # ETag includes application + saved_job updated_at so the client sees a
    # fresh response (not 304) after applying / withdrawing / saving.
    etag_parts: list[object] = [job.id, job.updated_at]
    if match is not None:
        etag_parts.append(match.updated_at)
    if application is not None:
        etag_parts.append(application.updated_at)
    if saved_job is not None:
        etag_parts.append(saved_job.updated_at)
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
        application=(
            JobDetailApplicationRead.model_validate(application)
            if application is not None
            else None
        ),
        saved_job=(
            JobDetailSavedJobRead.model_validate(saved_job) if saved_job is not None else None
        ),
    )
