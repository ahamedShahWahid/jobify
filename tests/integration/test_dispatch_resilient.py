"""Integration test for upload-route resilience when the Celery broker is down."""

from __future__ import annotations

import io

import pytest
from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole
from jobify_api.auth.tokens import mint_access_token
from tests.integration.outbox_helpers import task_event_args

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET in the integration fixtures


def _tiny_pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="resume content")
    return bytes(pdf.output())


async def _make_applicant_with_token(session: AsyncSession) -> tuple[str, str]:
    """Return (applicant_id, access_token) for a fresh applicant."""
    user = User(email="dispatch@ex.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Dispatch Test")
    session.add(applicant)
    await session.commit()
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    return str(applicant.id), token


async def test_upload_returns_201_and_stages_dispatch_without_broker_access(
    async_client,
    session,
) -> None:
    """Upload commits its parse intent without contacting the broker."""

    applicant_id, access = await _make_applicant_with_token(session)
    pdf = _tiny_pdf()

    resp = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        headers={"Authorization": f"Bearer {access}"},
    )

    assert resp.status_code == 201
    row = (
        await session.execute(select(Resume).where(Resume.applicant_id.in_([applicant_id])))
    ).scalar_one()
    assert row.parse_status == ResumeParseStatus.PENDING
    assert [str(row.id)] in await task_event_args(session, "jobify.parse_resume")
