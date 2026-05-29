"""Integration tests for consent helpers against real Postgres.

Covers happy paths + the load-bearing invariants:
- seed_default_consents inserts 7 rows + 7 audit rows on a fresh user.
- seed is idempotent (re-run inserts nothing).
- set_consent writes one audit row on a state change.
- set_consent is a no-op when state matches (no audit row).
- get_consent raises LookupError when no row exists.
- Soft-deleted rows are invisible to get_consent.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.consent import get_consent, seed_default_consents, set_consent
from kpa.db.models import (
    DEFAULT_CONSENTS,
    AuditLog,
    ConsentScope,
    User,
    UserConsent,
    UserRole,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_seed_inserts_all_scopes_and_audit_rows(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()

    created = await seed_default_consents(session, user=user, request_id="req-seed")

    assert len(created) == len(DEFAULT_CONSENTS)
    rows = (
        (await session.execute(select(UserConsent).where(UserConsent.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(rows) == len(DEFAULT_CONSENTS)
    by_scope = {r.scope: r.granted for r in rows}
    for scope, default in DEFAULT_CONSENTS.items():
        assert by_scope[scope.value] is default

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,
                    AuditLog.action == "consent.seeded",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == len(DEFAULT_CONSENTS)
    assert all(a.context["request_id"] == "req-seed" for a in audits)


@pytest.mark.asyncio
async def test_seed_is_idempotent(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()

    first = await seed_default_consents(session, user=user)
    assert len(first) == len(DEFAULT_CONSENTS)
    second = await seed_default_consents(session, user=user)
    assert second == []


@pytest.mark.asyncio
async def test_set_consent_writes_audit_on_state_change(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    # email_marketing defaults to False — flip to True.
    updated = await set_consent(
        session,
        user=user,
        scope=ConsentScope.EMAIL_MARKETING,
        granted=True,
        request_id="req-flip",
    )
    assert updated.granted is True

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,
                    AuditLog.action == "consent.granted",
                    AuditLog.resource_id == updated.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].context["scope"] == "email_marketing"
    assert audits[0].context["request_id"] == "req-flip"


@pytest.mark.asyncio
async def test_set_consent_noop_writes_no_audit(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    # email_transactional defaults to True — set to True again (noop).
    await set_consent(
        session,
        user=user,
        scope=ConsentScope.EMAIL_TRANSACTIONAL,
        granted=True,
    )

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,
                    AuditLog.action.in_(["consent.granted", "consent.revoked"]),
                )
            )
        )
        .scalars()
        .all()
    )
    assert audits == []  # No grant/revoke audit, only the seed rows above.


@pytest.mark.asyncio
async def test_get_consent_raises_when_no_row(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    # No seeding — user has zero consent rows.

    with pytest.raises(LookupError, match="no live consent row"):
        await get_consent(session, user=user, scope=ConsentScope.EMAIL_TRANSACTIONAL)


@pytest.mark.asyncio
async def test_get_consent_ignores_soft_deleted(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    row = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == ConsentScope.EMAIL_TRANSACTIONAL.value,
            )
        )
    ).scalar_one()

    from datetime import UTC, datetime

    row.deleted_at = datetime.now(UTC)
    await session.flush()

    with pytest.raises(LookupError):
        await get_consent(session, user=user, scope=ConsentScope.EMAIL_TRANSACTIONAL)
