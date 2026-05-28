"""POST /v1/me/dsr/export — DPDP § 11 right-of-access endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.auth.dependencies import current_user
from kpa.db.models import User
from kpa.db.session import get_session
from kpa.dsr import build_user_export

router = APIRouter(prefix="/v1/me", tags=["dsr"])
_log = structlog.get_logger(__name__)


@router.post("/dsr/export")
async def export_user_data(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Return a JSON dump of every row tied to the authenticated user.

    DPDP § 11 right-of-access. Sync at MVP scale; if/when audit history
    exceeds ~10K rows per user, switch to async + signed-URL.
    """
    request_id = request.state.request_id

    # 1. Audit the request BEFORE assembly. Durable even if assembly fails.
    await audit_log(
        session,
        action="user.dsr_export_requested",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={"request_id": request_id},
    )
    await session.flush()

    export = await build_user_export(session, user=user)

    # 2. Audit completion with section counts.
    section_counts = {
        "oauth_identities": len(export.oauth_identities),
        "resumes": len(export.resumes),
        "applicant_embedding": 1 if export.applicant_embedding else 0,
        "applications": len(export.applications),
        "saved_jobs": len(export.saved_jobs),
        "matches": len(export.matches),
        "notifications": len(export.notifications),
        "user_consents": len(export.user_consents),
        "audit_history": len(export.audit_history),
        "employer_memberships": len(export.employer_memberships),
        "owned_jobs": len(export.owned_jobs),
    }
    await audit_log(
        session,
        action="user.dsr_export_completed",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={"request_id": request_id, "section_counts": section_counts},
    )

    _log.info(
        "dsr.export-completed",
        user_id=str(user.id),
        section_counts=section_counts,
    )

    body = export.model_dump_json()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"kpa-data-export-{user.id}-{timestamp}.json"

    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
