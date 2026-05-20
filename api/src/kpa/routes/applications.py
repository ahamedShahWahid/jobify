"""Application endpoints — apply, withdraw, and list application history.

POST /v1/jobs/{job_id}/apply    — apply to a job (idempotent; re-apply after
                                  withdraw updates the existing withdrawn row).
PATCH /v1/applications/{id}     — withdraw an application (applied→withdrawn only).
GET   /v1/applications          — paginated rich application history (incl. withdrawn).

Cursor format: base64 of {"created_at": ISO8601, "application_id": uuid}.
Ordering: created_at DESC, id DESC.
ETag: W/"sha256(applicant_id|max_updated_at|count)".
"""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import current_user
from kpa.db.models import (
    Applicant,
    Application,
    ApplicationStatus,
    Employer,
    Job,
    JobStatus,
    User,
    UserRole,
)
from kpa.db.session import get_session
from kpa.routes.feed import EmployerRead, JobRead, make_weak_etag

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["applications"])

# ---------------------------------------------------------------------------
# Pydantic shapes
# ---------------------------------------------------------------------------


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    status: str  # "applied" | "withdrawn"
    source: str
    created_at: datetime
    updated_at: datetime


class ApplicationListItem(BaseModel):
    application: ApplicationRead
    job: JobRead
    employer: EmployerRead


class ApplicationListResponse(BaseModel):
    items: list[ApplicationListItem]
    next_cursor: str | None


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "feed"


class WithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str  # must be "withdrawn"


# ---------------------------------------------------------------------------
# Cursor helpers (keyed on created_at + application_id — distinct from feed)
# ---------------------------------------------------------------------------


def encode_cursor_apps(created_at: datetime, application_id: uuid.UUID) -> str:
    """Pack (created_at, application_id) into an opaque base64 string."""
    payload = {
        "created_at": created_at.isoformat(),
        "application_id": str(application_id),
    }
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor_apps(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw)
        return datetime.fromisoformat(payload["created_at"]), uuid.UUID(payload["application_id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError(f"invalid_cursor: {exc}") from exc


# ---------------------------------------------------------------------------
# Auth helper (inline — mirrors feed.py and resumes.py, intentionally)
# ---------------------------------------------------------------------------


async def _require_applicant(user: User, session: AsyncSession) -> Applicant:
    """Reject non-applicant tokens with 403 before any applicant-row read.

    Raises 500 applicant_missing as defence-in-depth (sign-in provisions the row).
    Mirrors the helper in routes/feed.py and routes/resumes.py — not extracted
    per the CLAUDE.md convention for this slice.
    """
    if user.role != UserRole.APPLICANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not_an_applicant",
        )
    applicant = (
        await session.execute(
            select(Applicant).where(
                Applicant.user_id == user.id,
                Applicant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if applicant is None:
        _log.error("applicant.row-missing-for-applicant-role", user_id=str(user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="applicant_missing",
        )
    return applicant


# ---------------------------------------------------------------------------
# POST /v1/jobs/{job_id}/apply
# ---------------------------------------------------------------------------


@router.post(
    "/jobs/{job_id}/apply",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationRead,
)
async def apply_to_job(
    job_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    body: ApplyRequest = Depends(),  # noqa: B008
) -> Response | ApplicationRead:
    """Apply to an open job.

    Idempotent:
    - Existing applied row → 200 with the existing row.
    - Existing withdrawn row → UPDATE back to applied, refresh created_at.
    - No existing row → INSERT. → 201.

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

    # Look up existing live application for this (applicant, job) pair.
    existing = (
        await session.execute(
            select(Application).where(
                Application.applicant_id == applicant.id,
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.status == ApplicationStatus.APPLIED:
            # Already applied — idempotent 200.
            return Response(
                content=ApplicationRead.model_validate(existing).model_dump_json(),
                status_code=status.HTTP_200_OK,
                media_type="application/json",
            )
        # existing.status == WITHDRAWN — update back to applied, refresh created_at.
        await session.execute(
            update(Application)
            .where(Application.id == existing.id)
            .values(
                status=ApplicationStatus.APPLIED,
                source=body.source,
                created_at=func.now(),
                updated_at=func.now(),
            )
        )
        await session.commit()
        # Re-fetch to get DB-resolved timestamps.
        refreshed = (
            await session.execute(select(Application).where(Application.id == existing.id))
        ).scalar_one()
        return Response(
            content=ApplicationRead.model_validate(refreshed).model_dump_json(),
            status_code=status.HTTP_200_OK,
            media_type="application/json",
        )

    # No existing row — INSERT.
    new_application = Application(
        applicant_id=applicant.id,
        job_id=job_id,
        status=ApplicationStatus.APPLIED,
        source=body.source,
    )
    session.add(new_application)
    await session.commit()
    await session.refresh(new_application)
    return ApplicationRead.model_validate(new_application)


# ---------------------------------------------------------------------------
# PATCH /v1/applications/{application_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/applications/{application_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApplicationRead,
)
async def patch_application(
    application_id: uuid.UUID,
    body: WithdrawRequest,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ApplicationRead:
    """Withdraw an application.

    Only ``applied → withdrawn`` is accepted.  Re-withdraw is a 200 no-op.
    Any other target status → 400 invalid_transition.
    """
    applicant = await _require_applicant(user, session)

    # Load the application scoped to the current applicant.
    application = (
        await session.execute(
            select(Application).where(
                Application.id == application_id,
                Application.applicant_id == applicant.id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="application_not_found",
        )

    # Validate the requested target status.
    if body.status != "withdrawn":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_transition",
        )

    # Re-withdraw no-op.
    if application.status == ApplicationStatus.WITHDRAWN:
        return ApplicationRead.model_validate(application)

    # applied → withdrawn.
    if application.status == ApplicationStatus.APPLIED:
        await session.execute(
            update(Application)
            .where(Application.id == application.id)
            .values(status=ApplicationStatus.WITHDRAWN, updated_at=func.now())
        )
        await session.commit()
        refreshed = (
            await session.execute(select(Application).where(Application.id == application.id))
        ).scalar_one()
        return ApplicationRead.model_validate(refreshed)

    # Defensive — unexpected status value.
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="invalid_transition",
    )


# ---------------------------------------------------------------------------
# GET /v1/applications
# ---------------------------------------------------------------------------


@router.get(
    "/applications",
    status_code=status.HTTP_200_OK,
    response_model=ApplicationListResponse,
)
async def list_applications(
    request: Request,
    response: Response,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
) -> ApplicationListResponse | Response:
    """Paginated list of the current applicant's applications (incl. withdrawn).

    Cursor: base64 of {"created_at": ISO8601, "application_id": uuid}.
    Order:  created_at DESC, id DESC.
    ETag:   W/"sha256(applicant_id|max_updated_at|count)".
    """
    applicant = await _require_applicant(user, session)

    cursor_created_at: datetime | None = None
    cursor_app_id: uuid.UUID | None = None
    if cursor is not None:
        try:
            cursor_created_at, cursor_app_id = decode_cursor_apps(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_cursor",
            ) from None

    stmt = (
        select(Application, Job, Employer)
        .join(Job, Job.id == Application.job_id)
        .join(Employer, Employer.id == Job.employer_id)
        .where(
            Application.applicant_id == applicant.id,
            Application.deleted_at.is_(None),
            Job.deleted_at.is_(None),
        )
        .order_by(Application.created_at.desc(), Application.id.desc())
        .limit(limit + 1)  # peek-one for next_cursor
    )

    if cursor_created_at is not None and cursor_app_id is not None:
        # Emulate (created_at DESC, id DESC) keyset pagination.
        # Row qualifies if: created_at < cursor_created_at
        #                OR (created_at == cursor_created_at AND id < cursor_app_id)
        stmt = stmt.where(
            (Application.created_at < cursor_created_at)
            | ((Application.created_at == cursor_created_at) & (Application.id < cursor_app_id))
        )

    rows = (await session.execute(stmt)).all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items: list[ApplicationListItem] = []
    max_updated_at: datetime | None = None
    for application, job, employer in rows:
        items.append(
            ApplicationListItem(
                application=ApplicationRead.model_validate(application),
                job=JobRead.model_validate(job),
                employer=EmployerRead(
                    id=employer.id,
                    name=employer.name,
                    verified=employer.verified_at is not None,
                ),
            )
        )
        if max_updated_at is None or application.updated_at > max_updated_at:
            max_updated_at = application.updated_at

    next_cursor: str | None = None
    if has_more and rows:
        last_app = rows[-1][0]
        next_cursor = encode_cursor_apps(last_app.created_at, last_app.id)

    etag = make_weak_etag(applicant.id, max_updated_at, len(items))
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag

    return ApplicationListResponse(items=items, next_cursor=next_cursor)
