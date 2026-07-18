"""DSR routes — DPDP right-of-access (POST /v1/me/dsr/export) and
right-of-erasure (DELETE /v1/me/dsr)."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import User
from jobify_api.auth.dependencies import current_user
from jobify_api.dependencies import get_session
from jobify_api.dsr import build_user_export
from jobify_api.dsr.deleter import DeleteReport, delete_user_data

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
    await session.commit()

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
    await session.commit()

    _log.info(
        "dsr.export-completed",
        user_id=str(user.id),
        section_counts=section_counts,
    )

    body = export.model_dump_json()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"jobify-data-export-{user.id}-{timestamp}.json"

    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


_CONFIRMATION_TOKEN = "DELETE_MY_ACCOUNT"  # noqa: S105


class DsrDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: str


@router.delete("/dsr", response_model=DeleteReport)
async def delete_user_data_endpoint(
    body: DsrDeleteRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DeleteReport:
    """DPDP § 12 right-of-erasure. Soft-delete-and-scrub User + Applicant
    tombstones; hard-delete around them. Atomic — partial deletion is worse
    than no deletion."""

    if body.confirmation != _CONFIRMATION_TOKEN:
        raise HTTPException(status_code=400, detail="confirmation_mismatch")

    request_id = request.state.request_id

    # Audit BEFORE the destructive work. Same txn — atomic with the deletion.
    await audit_log(
        session,
        action="user.dsr_delete_requested",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={"request_id": request_id},
    )

    report = await delete_user_data(session, user=user)

    await audit_log(
        session,
        action="user.dsr_deleted",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={
            "request_id": request_id,
            "section_counts": report.section_counts,
            "warnings": [w.model_dump(mode="json") for w in report.warnings],
        },
    )

    await session.commit()

    _log.info(
        "dsr.delete-completed",
        user_id=str(user.id),
        section_counts=report.section_counts,
        warning_count=len(report.warnings),
    )

    return report
