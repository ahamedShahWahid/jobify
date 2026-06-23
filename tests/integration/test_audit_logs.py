"""Integration tests for the audit_logs table + audit_log() helper.

Covers the four invariants from
docs/superpowers/specs/2026-05-28-audit-logs-substrate-design.md §9:

1. Happy path — row written, fields populated, queryable by resource via the
   (resource_type, resource_id, created_at desc) index.
2. system actor — actor=None + actor_role='system' writes successfully.
3. Txn rollback — savepoint-bound rollback removes the audit row (the
   caller-owns-the-txn contract from §5.1).
4. Helper signature — rejects (actor=None, actor_role=None) at the helper
   boundary, before any DB write.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import AuditLog, User, UserRole

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_happy_path_writes_row(session: AsyncSession) -> None:
    user = User(
        email=f"audit-{uuid4().hex[:8]}@example.com",
        role=UserRole.APPLICANT,
    )
    session.add(user)
    await session.flush()

    resource_id = uuid4()
    row = await audit_log(
        session,
        action="resume.accessed",
        actor=user,
        resource_type="resume",
        resource_id=resource_id,
        context={"request_id": "req-1"},
    )

    assert row.id is not None
    assert row.actor_user_id == user.id
    assert row.actor_role == "applicant"
    assert row.action == "resume.accessed"
    assert row.resource_type == "resume"
    assert row.resource_id == resource_id
    assert row.context == {"request_id": "req-1"}
    assert row.created_at is not None

    # Roundtrip by resource — the (resource_type, resource_id, created_at desc)
    # index is the seek path future DSR-export will use.
    result = await session.execute(
        select(AuditLog).where(
            AuditLog.resource_type == "resume",
            AuditLog.resource_id == resource_id,
        )
    )
    fetched = result.scalar_one()
    assert fetched.id == row.id


@pytest.mark.asyncio
async def test_system_actor_writes_row(session: AsyncSession) -> None:
    row = await audit_log(
        session,
        action="job.embeddings.swept",
        actor=None,
        actor_role="system",
        context={"swept_count": 42},
    )
    assert row.actor_user_id is None
    assert row.actor_role == "system"
    assert row.action == "job.embeddings.swept"
    assert row.context == {"swept_count": 42}


@pytest.mark.asyncio
async def test_rollback_removes_audit_row(session: AsyncSession) -> None:
    user = User(
        email=f"audit-rb-{uuid4().hex[:8]}@example.com",
        role=UserRole.APPLICANT,
    )
    session.add(user)
    await session.flush()

    sp = await session.begin_nested()
    row = await audit_log(
        session,
        action="resume.accessed",
        actor=user,
        resource_type="resume",
        resource_id=uuid4(),
        context={"request_id": "req-rb"},
    )
    row_id = row.id
    await sp.rollback()

    # Row must be gone — audit lives or dies with the business txn.
    result = await session.execute(select(AuditLog).where(AuditLog.id == row_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_helper_rejects_actor_none_and_role_none(
    session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="actor_role"):
        await audit_log(session, action="x.y", actor=None, actor_role=None)
