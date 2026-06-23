"""Integration tests for the jobify-grant-admin CLI's _apply_in_session seam."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import AuditLog, User, UserRole
from jobify_api.scripts.grant_admin import _apply_in_session

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_grants_admin_to_existing_user(session: AsyncSession) -> None:
    email = f"a-{uuid4().hex[:8]}@example.com"
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()

    report = await _apply_in_session(session, email=email)

    assert report.matched
    assert not report.already_admin
    assert report.from_role == "applicant"

    refreshed = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.role == UserRole.ADMIN

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.resource_id == user.id,
                    AuditLog.action == "auth.role.granted",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].actor_user_id is None  # system actor
    assert audits[0].actor_role == "system"
    assert audits[0].context["from_role"] == "applicant"


@pytest.mark.asyncio
async def test_idempotent_on_already_admin(session: AsyncSession) -> None:
    email = f"a-{uuid4().hex[:8]}@example.com"
    user = User(email=email, role=UserRole.ADMIN)
    session.add(user)
    await session.flush()

    report = await _apply_in_session(session, email=email)
    assert report.matched
    assert report.already_admin

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.resource_id == user.id,
                    AuditLog.action == "auth.role.granted",
                )
            )
        )
        .scalars()
        .all()
    )
    assert audits == []  # No-op writes no audit row.


@pytest.mark.asyncio
async def test_unknown_email_reports_unmatched(session: AsyncSession) -> None:
    report = await _apply_in_session(session, email="ghost@example.com")
    assert not report.matched
    assert report.user_id is None
