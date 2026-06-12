"""Saved-job endpoints — save, unsave, and list saved jobs.

POST   /v1/jobs/{job_id}/save — save an open job (idempotent; re-save returns existing).
DELETE /v1/jobs/{job_id}/save — unsave (soft-delete); 204 no-op if not saved.
GET    /v1/saved              — paginated rich list of saved jobs.

Cursor format: base64 of {"created_at": ISO8601, "saved_job_id": uuid}.
Ordering: created_at DESC, id DESC.
ETag: W/"sha256(applicant_id|max(updated_at)|count)".
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.dependencies import (
    current_user,
)
from jobify.auth.dependencies import (
    require_applicant as _require_applicant,
)
from jobify.db.models import (
    Employer,
    Job,
    JobStatus,
    SavedJob,
    User,
)
from jobify.db.session import get_session
from jobify.pagination import decode_cursor, encode_cursor, make_weak_etag
from jobify.routes.schemas import EmployerRead, JobRead

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["saved_jobs"])

# ---------------------------------------------------------------------------
# Pydantic shapes
# ---------------------------------------------------------------------------


class SavedJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SavedJobListItem(BaseModel):
    saved_job: SavedJobRead
    job: JobRead
    employer: EmployerRead


class SavedJobListResponse(BaseModel):
    items: list[SavedJobListItem]
    next_cursor: str | None


# ---------------------------------------------------------------------------
# Cursor helpers (keyed on created_at + saved_job_id — distinct from applications)
# ---------------------------------------------------------------------------


def encode_cursor_saved(created_at: datetime, saved_job_id: uuid.UUID) -> str:
    """Pack (created_at, saved_job_id) into an opaque base64 string."""
    return encode_cursor({"created_at": created_at.isoformat(), "saved_job_id": str(saved_job_id)})


def decode_cursor_saved(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    payload = decode_cursor(cursor)
    try:
        return datetime.fromisoformat(payload["created_at"]), uuid.UUID(payload["saved_job_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"invalid_cursor: {exc}") from exc


# ---------------------------------------------------------------------------
# POST /v1/jobs/{job_id}/save
# ---------------------------------------------------------------------------


@router.post(
    "/jobs/{job_id}/save",
    status_code=status.HTTP_201_CREATED,
    response_model=SavedJobRead,
)
async def save_job(
    job_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response | SavedJobRead:
    """Save an open job for the current applicant.

    Idempotent — re-saving an already-saved job returns 200 with the existing row.
    New save → 201.

    Error ladder: 401 (auth) → 403 (role) → 404 (job missing/closed/deleted).
    """
    applicant = await _require_applicant(user, session)

    # Load the job — must be open and not soft-deleted.
    job = (
        await session.execute(
            select(Job).where(
                Job.id == job_id,
                Job.status == JobStatus.OPEN,
                Job.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    # Look up existing live saved-job row for this (applicant, job) pair.
    existing = (
        await session.execute(
            select(SavedJob).where(
                SavedJob.applicant_id == applicant.id,
                SavedJob.job_id == job_id,
                SavedJob.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Already saved — idempotent 200.
        return Response(
            content=SavedJobRead.model_validate(existing).model_dump_json(),
            status_code=status.HTTP_200_OK,
            media_type="application/json",
        )

    # No live row — INSERT.
    new_saved = SavedJob(
        applicant_id=applicant.id,
        job_id=job_id,
    )
    session.add(new_saved)
    await session.commit()
    await session.refresh(new_saved)
    return SavedJobRead.model_validate(new_saved)


# ---------------------------------------------------------------------------
# DELETE /v1/jobs/{job_id}/save
# ---------------------------------------------------------------------------


@router.delete(
    "/jobs/{job_id}/save",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unsave_job(
    job_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Unsave a job (soft-delete the saved-job row).

    204 No Content regardless of whether the row existed — the UI calls this
    optimistically without checking state first.

    Error ladder: 401 (auth) → 403 (role). No 404 — missing row is a no-op.
    """
    applicant = await _require_applicant(user, session)

    # Look up the live row.
    existing = (
        await session.execute(
            select(SavedJob).where(
                SavedJob.applicant_id == applicant.id,
                SavedJob.job_id == job_id,
                SavedJob.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        await session.execute(
            update(SavedJob)
            .where(SavedJob.id == existing.id)
            .values(deleted_at=func.now(), updated_at=func.now())
        )
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# GET /v1/saved
# ---------------------------------------------------------------------------


@router.get(
    "/saved",
    status_code=status.HTTP_200_OK,
    response_model=SavedJobListResponse,
)
async def list_saved_jobs(
    request: Request,
    response: Response,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
) -> SavedJobListResponse | Response:
    """Paginated list of the current applicant's saved jobs.

    Saved jobs that have since been closed still appear — only the job
    soft-delete is filtered. Unsaved rows (deleted_at IS NOT NULL) are excluded.

    Cursor: base64 of {"created_at": ISO8601, "saved_job_id": uuid}.
    Order:  created_at DESC, id DESC.
    ETag:   W/"sha256(applicant_id|max_updated_at|count)".
    """
    applicant = await _require_applicant(user, session)

    cursor_created_at: datetime | None = None
    cursor_saved_id: uuid.UUID | None = None
    if cursor is not None:
        try:
            cursor_created_at, cursor_saved_id = decode_cursor_saved(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_cursor",
            ) from None

    stmt = (
        select(SavedJob, Job, Employer)
        .join(Job, Job.id == SavedJob.job_id)
        .join(Employer, Employer.id == Job.employer_id)
        .where(
            SavedJob.applicant_id == applicant.id,
            SavedJob.deleted_at.is_(None),
            Job.deleted_at.is_(None),
        )
        .order_by(SavedJob.created_at.desc(), SavedJob.id.desc())
        .limit(limit + 1)  # peek-one for next_cursor
    )

    if cursor_created_at is not None and cursor_saved_id is not None:
        # Emulate (created_at DESC, id DESC) keyset pagination.
        # Row qualifies if: created_at < cursor_created_at
        #                OR (created_at == cursor_created_at AND id < cursor_saved_id)
        stmt = stmt.where(
            (SavedJob.created_at < cursor_created_at)
            | ((SavedJob.created_at == cursor_created_at) & (SavedJob.id < cursor_saved_id))
        )

    rows = (await session.execute(stmt)).all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items: list[SavedJobListItem] = []
    max_updated_at: datetime | None = None
    for saved_job, job, employer in rows:
        items.append(
            SavedJobListItem(
                saved_job=SavedJobRead.model_validate(saved_job),
                job=JobRead.from_job_and_employer(job, employer),
                employer=EmployerRead(
                    id=employer.id,
                    name=employer.name,
                    verified=employer.verified_at is not None,
                ),
            )
        )
        if max_updated_at is None or saved_job.updated_at > max_updated_at:
            max_updated_at = saved_job.updated_at

    next_cursor: str | None = None
    if has_more and rows:
        last_saved = rows[-1][0]
        next_cursor = encode_cursor_saved(last_saved.created_at, last_saved.id)

    etag = make_weak_etag(applicant.id, max_updated_at, len(items))
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag

    return SavedJobListResponse(items=items, next_cursor=next_cursor)
