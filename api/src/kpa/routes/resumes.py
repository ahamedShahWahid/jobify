"""Resume upload + retrieval endpoints.

Routes are nested under the applicant id; no auth in this slice (the
applicant id is supplied directly in the path). Auth lands later and
adds a /v1/applicants/me/resumes alias.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import Applicant, Resume, ResumeParseStatus
from kpa.db.session import get_session
from kpa.integrations.storage import Storage, get_storage
from kpa.settings import Settings

router = APIRouter(prefix="/v1/applicants/{applicant_id}", tags=["resumes"])


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


async def _load_live_applicant(session: AsyncSession, applicant_id: UUID) -> Applicant:
    row = (
        await session.execute(
            select(Applicant).where(
                Applicant.id == applicant_id,
                Applicant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant not found")
    return row


@router.post(
    "/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    applicant_id: UUID,
    request: Request,
    file: UploadFile,
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

    applicant = await _load_live_applicant(session, applicant_id)

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
    await session.refresh(resume)
    return resume


@router.get(
    "/resumes/{resume_id}",
    response_model=ResumeRead,
)
async def get_resume(
    applicant_id: UUID,
    resume_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Resume:
    # Apply the same live-applicant check as POST so we don't leak the
    # resume's existence to callers using an unknown applicant id.
    await _load_live_applicant(session, applicant_id)

    row = (
        await session.execute(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.applicant_id == applicant_id,
                Resume.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resume not found")
    return row
