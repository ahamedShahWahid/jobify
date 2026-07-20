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

import uuid
from datetime import datetime
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import (
    Application,
    ApplicationStageEvent,
    Employer,
    EmployerUser,
    Job,
    Resume,
    User,
)
from jobify.integrations.storage.base import Storage
from jobify_api.applications.service import (
    ApplicationCommandError,
    apply_to_open_job,
    withdraw_application,
)
from jobify_api.auth.dependencies import (
    _require_recruiter,
    current_user,
)
from jobify_api.auth.dependencies import (
    require_applicant as _require_applicant,
)
from jobify_api.dependencies import get_session, get_storage
from jobify_api.pagination import decode_cursor, encode_cursor, make_weak_etag
from jobify_api.routes.applications_schemas import (
    ApplicationListItem,
    ApplicationListResponse,
    ApplicationRead,
    ApplyRequest,
    WithdrawRequest,
)
from jobify_api.routes.schemas import EmployerRead, JobRead

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["applications"])

# ---------------------------------------------------------------------------
# Cursor helpers (keyed on created_at + application_id — distinct from feed)
# ---------------------------------------------------------------------------


def encode_cursor_apps(created_at: datetime, application_id: uuid.UUID) -> str:
    """Pack (created_at, application_id) into an opaque base64 string."""
    return encode_cursor(
        {"created_at": created_at.isoformat(), "application_id": str(application_id)}
    )


def decode_cursor_apps(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    payload = decode_cursor(cursor)
    try:
        return datetime.fromisoformat(payload["created_at"]), uuid.UUID(payload["application_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"invalid_cursor: {exc}") from exc


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

    try:
        outcome = await apply_to_open_job(
            session,
            applicant_id=applicant.id,
            user_id=user.id,
            job_id=job_id,
            source=body.source,
        )
    except ApplicationCommandError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    result = ApplicationRead.model_validate(outcome.application)
    if outcome.created:
        return result
    return Response(
        content=result.model_dump_json(),
        status_code=status.HTTP_200_OK,
        media_type="application/json",
    )


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

    try:
        application = await withdraw_application(
            session,
            applicant_id=applicant.id,
            application_id=application_id,
            target_status=body.status,
        )
    except ApplicationCommandError as exc:
        error_status = 404 if exc.detail == "application_not_found" else 400
        raise HTTPException(status_code=error_status, detail=exc.detail) from exc
    return ApplicationRead.model_validate(application)


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
                job=JobRead.from_job_and_employer(job, employer),
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


# ---------------------------------------------------------------------------
# GET /v1/applications/{application_id}/resume — recruiter downloads latest resume
# ---------------------------------------------------------------------------


def _content_disposition_attachment(filename: str) -> str:
    """RFC 6266 Content-Disposition for an applicant-controlled filename.

    The filename comes from the upload (attacker-controlled): quotes,
    backslashes and control chars would break out of the quoted-string (or
    split the header). ASCII fallback replaces them with "_"; the exact
    original name travels percent-encoded in the filename* parameter.
    """
    fallback = "".join(c if 32 <= ord(c) < 127 else "_" for c in filename)
    fallback = fallback.replace('"', "_").replace("\\", "_")
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


@router.get("/applications/{application_id}/resume")
async def recruiter_download_application_resume(
    application_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> Response:
    """Download the latest resume of the applicant who applied to one of the
    recruiter's jobs.

    Error ladder:
    - 401 — no/invalid bearer token (current_user).
    - 403 not_a_recruiter — caller is not a recruiter.
    - 404 not found — application doesn't exist, belongs to another employer's
      job, applicant has no resume, or the application is soft-deleted.
      Deliberately uniform to avoid existence leaks.

    Emits structured audit log ``recruiter.resume-accessed`` on success.
    """
    await _require_recruiter(user)

    # Single query: join Application → Job → EmployerUser (scoped to caller) →
    # outerjoin Resume (latest first). If the application doesn't belong to one
    # of the caller's jobs, the EmployerUser join returns nothing.
    row = (
        await session.execute(
            select(Application, Job, Resume)
            .join(Job, Job.id == Application.job_id)
            .join(
                EmployerUser,
                and_(
                    EmployerUser.employer_id == Job.employer_id,
                    EmployerUser.user_id == user.id,
                    EmployerUser.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                Resume,
                and_(
                    Resume.applicant_id == Application.applicant_id,
                    Resume.deleted_at.is_(None),
                ),
            )
            .where(
                Application.id == application_id,
                Application.deleted_at.is_(None),
                Job.deleted_at.is_(None),
            )
            .order_by(Resume.created_at.desc())
        )
    ).first()

    if row is None or row.Resume is None:
        raise HTTPException(status_code=404, detail="not found")

    application, job, resume = row.Application, row.Job, row.Resume

    if resume.storage_key is None or resume.original_filename is None:
        raise HTTPException(status_code=404, detail="not found")

    _log.info(
        "recruiter.resume-accessed",
        recruiter_user_id=str(user.id),
        employer_id=str(job.employer_id),
        application_id=str(application.id),
        applicant_id=str(application.applicant_id),
        resume_id=str(resume.id),
    )
    await audit_log(
        session,
        action="resume.accessed",
        actor=user,
        resource_type="resume",
        resource_id=resume.id,
        context={
            "request_id": request.state.request_id,
            "application_id": str(application.id),
            "applicant_id": str(application.applicant_id),
            "employer_id": str(job.employer_id),
        },
    )
    # Commit BEFORE the blob read so the DB connection is released during
    # storage I/O (local disk today, S3 later) — and so the canonical
    # structlog → audit_log → side-effect order holds.
    await session.commit()

    content = await storage.read(resume.storage_key)

    return Response(
        content=content,
        media_type=resume.content_type,
        headers={"Content-Disposition": _content_disposition_attachment(resume.original_filename)},
    )


# ---------------------------------------------------------------------------
# GET /v1/applications/{application_id}/timeline — applicant's stage journey
# ---------------------------------------------------------------------------


class StageEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_stage: str
    to_stage: str
    created_at: datetime


class ApplicationTimelineResponse(BaseModel):
    items: list[StageEventRead]


@router.get(
    "/applications/{application_id}/timeline",
    response_model=ApplicationTimelineResponse,
)
async def get_application_timeline(
    application_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ApplicationTimelineResponse:
    """The applicant's stage journey. Owner-only (token identity), uniform
    404 across unknown-id and other-owner; actor identity never exposed."""
    applicant = await _require_applicant(user, session)
    owned = (
        await session.execute(
            select(Application.id).where(
                Application.id == application_id,
                Application.applicant_id == applicant.id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if owned is None:
        raise HTTPException(status_code=404, detail="application_not_found")

    events = (
        (
            await session.execute(
                select(ApplicationStageEvent)
                .where(
                    ApplicationStageEvent.application_id == application_id,
                    ApplicationStageEvent.deleted_at.is_(None),
                )
                .order_by(ApplicationStageEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return ApplicationTimelineResponse(items=[StageEventRead.model_validate(e) for e in events])
