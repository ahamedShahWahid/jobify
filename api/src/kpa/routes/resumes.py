"""Resume upload + retrieval endpoints.

Both routes are nested under `/v1/applicants/me` and resolve the
authenticated applicant from the access JWT — never from the URL.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import current_user
from kpa.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole
from kpa.db.session import get_session
from kpa.integrations.storage import Storage, get_storage
from kpa.settings import Settings

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/applicants/me", tags=["resumes"])


# Content-Type → file extension. The original filename's extension is not
# trusted; we derive a safe one from the validated content-type.
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


class ResumeRead(BaseModel):
    """Response shape for resume metadata. Bytes are never returned here."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    applicant_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    parse_status: ResumeParseStatus
    created_at: datetime


async def _require_applicant(user: User, session: AsyncSession) -> Applicant:
    """Resolve the authenticated user to a live applicants row.

    Raises 403 not_an_applicant if user.role is not APPLICANT.
    Raises 500 applicant_missing if role=applicant but no row exists
    (theoretically unreachable; defense in depth against an auth
    auto-provisioning regression).
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
        # Should not happen — `AuthService._upsert_identity` creates the
        # applicants row on first sign-in. If we get here, an out-of-band
        # path created an APPLICANT user without the paired row, or the
        # row was soft-deleted. Either way it's a data-integrity bug worth
        # paging on.
        _log.error("applicant.row-missing-for-applicant-role", user_id=str(user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="applicant_missing",
        )
    return applicant


@router.post(
    "/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    request: Request,
    file: UploadFile,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> Resume:
    settings: Settings = request.app.state.settings

    allowed = settings.allowed_resume_content_types
    if isinstance(allowed, str):  # defensive — should never happen after validation
        allowed = [allowed]

    if file.content_type is None or file.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"content_type {file.content_type!r} is not in the resume whitelist",
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds max_upload_bytes ({settings.max_upload_bytes})",
        )

    applicant = await _require_applicant(user, session)

    resume = Resume(
        applicant_id=applicant.id,
        original_filename=file.filename or "(unnamed)",
        content_type=file.content_type,
        size_bytes=len(content),
        storage_key="",  # set below once we know the resume id
        parse_status=ResumeParseStatus.PENDING,
    )
    session.add(resume)
    await session.flush()  # populates resume.id

    ext = _CONTENT_TYPE_TO_EXT[file.content_type]
    resume.storage_key = f"resumes/{resume.id}{ext}"

    await storage.save(key=resume.storage_key, content=content, content_type=file.content_type)
    await session.commit()

    # Dispatch async parse — broker outages MUST NOT fail the upload because
    # the resume row + file are already durable. Admin tooling can replay
    # pending rows after the broker recovers.
    #
    # Lazy import: kpa.workers.celery_app instantiates Settings() at module
    # level (needs KPA_REDIS_URL). Deferring the import to request time avoids
    # import-time failures in test collection where env vars aren't yet set.
    try:
        from kpa.workers.tasks.parse import parse_resume

        parse_resume.delay(str(resume.id))
    except Exception as exc:
        # Broad catch is deliberate: the row + blob are already durable, so
        # any dispatch-time error (broker down, import failure, eager-mode
        # task crash) must NOT roll back what we already committed. The log
        # event name stays generic ("dispatch.failed") so eager-mode parser
        # bugs aren't mislabeled as broker outages; exc_info carries the
        # traceback so an operator can tell broker-down from a real bug.
        _log.warning(
            "dispatch.failed",
            resume_id=str(resume.id),
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=True,
        )

    await session.refresh(resume)
    return resume


@router.get("/resumes", response_model=list[ResumeRead])
async def list_resumes(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[ResumeRead]:
    """List the authenticated applicant's resumes, newest first."""
    applicant = await _require_applicant(user, session)
    # No applicant JOIN here (unlike get_resume): we resolved `applicant` one
    # await ago and there's no user-supplied resource id, so the soft-delete
    # race window can at worst yield a stale read, never an ownership leak.
    rows = (
        (
            await session.execute(
                select(Resume)
                .where(
                    Resume.applicant_id == applicant.id,
                    Resume.deleted_at.is_(None),
                )
                .order_by(Resume.created_at.desc(), Resume.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ResumeRead.model_validate(r) for r in rows]


@router.get(
    "/resumes/{resume_id}",
    response_model=ResumeRead,
)
async def get_resume(
    resume_id: UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Resume:
    applicant = await _require_applicant(user, session)
    # Both 404 cases (unknown resume id, resume owned by a different
    # applicant) are already collapsed by the `Resume.applicant_id ==
    # applicant.id` filter — it returns None for both. The JOIN on
    # Applicant is belt-and-braces against a race where the applicant
    # was soft-deleted between `_require_applicant` and this query.
    row = (
        await session.execute(
            select(Resume)
            .join(Applicant, Resume.applicant_id == Applicant.id)
            .where(
                Resume.id == resume_id,
                Resume.applicant_id == applicant.id,
                Resume.deleted_at.is_(None),
                Applicant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resume not found")
    return row
