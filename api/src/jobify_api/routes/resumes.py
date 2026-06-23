"""Resume upload + retrieval endpoints.

Both routes are nested under `/v1/applicants/me` and resolve the
authenticated applicant from the access JWT — never from the URL.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Applicant, Resume, ResumeParseStatus, User
from jobify.integrations.storage import Storage
from jobify.settings import Settings
from jobify_api.auth.dependencies import (
    current_user,
)
from jobify_api.auth.dependencies import (
    require_applicant as _require_applicant,
)
from jobify_api.dependencies import get_session, get_storage

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/applicants/me", tags=["resumes"])


# Content-Type → file extension. The original filename's extension is not
# trusted; we derive a safe one from the validated content-type.
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
_LEGACY_DOC_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


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


async def _read_upload_capped(file: UploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"file exceeds max_upload_bytes ({max_bytes})",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_resume_signature(*, content: bytes, content_type: str) -> None:
    """Reject obvious content-type spoofing before persisting the blob."""
    matches = False
    if content_type == "application/pdf":
        matches = content.startswith(b"%PDF-")
    elif content_type == "application/msword":
        matches = content.startswith(_LEGACY_DOC_MAGIC)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
            matches = "[Content_Types].xml" in names and "word/document.xml" in names
        except zipfile.BadZipFile:
            matches = False

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="file content does not match declared resume content_type",
        )


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

    content = await _read_upload_capped(file, max_bytes=settings.max_upload_bytes)
    _validate_resume_signature(content=content, content_type=file.content_type)

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
    storage_key = f"resumes/{resume.id}{ext}"
    resume.storage_key = storage_key

    await storage.save(key=storage_key, content=content, content_type=file.content_type)
    await session.commit()

    # Dispatch async parse — broker outages MUST NOT fail the upload because
    # the resume row + file are already durable. Admin tooling can replay
    # pending rows after the broker recovers.
    #
    try:
        from jobify.celery_app import enqueue

        enqueue("jobify.parse_resume", str(resume.id))
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
