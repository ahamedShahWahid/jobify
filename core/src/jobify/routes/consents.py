"""Self-service consent endpoints. Any authenticated user reads/edits their
own consents — applicants, recruiters, and admins all have the same surface.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.dependencies import current_user
from jobify.consent import set_consent
from jobify.db.models import ConsentScope, User, UserConsent
from jobify.db.session import get_session

router = APIRouter(prefix="/v1/me", tags=["consents"])
_log = structlog.get_logger(__name__)


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope: str
    granted: bool
    updated_at: datetime


class ConsentListResponse(BaseModel):
    items: list[ConsentRead]


class ConsentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted: bool


@router.get("/consents", response_model=ConsentListResponse)
async def list_consents(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ConsentListResponse:
    rows = (
        (
            await session.execute(
                select(UserConsent)
                .where(
                    UserConsent.user_id == user.id,
                    UserConsent.deleted_at.is_(None),
                )
                .order_by(UserConsent.scope.asc())
            )
        )
        .scalars()
        .all()
    )
    return ConsentListResponse(items=[ConsentRead.model_validate(r) for r in rows])


@router.patch("/consents/{scope}", response_model=ConsentRead)
async def patch_consent(
    scope: ConsentScope,
    body: ConsentPatchRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ConsentRead:
    # Defensive: a soft-deleted row shouldn't normally appear here (admins
    # don't touch consents in this slice), but if one does, set_consent
    # would INSERT a fresh row and the partial-UNIQUE would still hold.
    # We surface a 404 instead — admin DSR action, user must re-grant via
    # support.
    existing = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == scope.value,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="consent_not_found")

    row = await set_consent(
        session,
        user=user,
        scope=scope,
        granted=body.granted,
        request_id=request.state.request_id,
    )
    await session.commit()
    await session.refresh(row)
    return ConsentRead.model_validate(row)
