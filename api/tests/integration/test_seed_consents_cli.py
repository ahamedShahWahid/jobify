"""Integration test for the kpa-seed-consents CLI's _apply_in_session
test seam. Mirrors test_seed_jobs_idempotent pattern.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.consent import seed_default_consents
from kpa.db.models import DEFAULT_CONSENTS, User, UserConsent, UserRole
from kpa.scripts.seed_consents import SeedReport, _apply_in_session

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_backfills_users_missing_consents(session: AsyncSession) -> None:
    pre_existing = User(email=f"pre-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(pre_existing)
    await session.flush()
    # NO seed call — this is the legacy user.

    already_seeded = User(email=f"seeded-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(already_seeded)
    await session.flush()
    await seed_default_consents(session, user=already_seeded)

    report = SeedReport()
    await _apply_in_session(session, report)

    assert report.scanned >= 2
    assert str(pre_existing.id) in report.user_ids_seeded
    assert str(already_seeded.id) not in report.user_ids_seeded

    pre_rows = (
        (await session.execute(select(UserConsent).where(UserConsent.user_id == pre_existing.id)))
        .scalars()
        .all()
    )
    assert len(pre_rows) == len(DEFAULT_CONSENTS)


@pytest.mark.asyncio
async def test_idempotent_rerun(session: AsyncSession) -> None:
    user = User(email=f"i-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()

    r1 = SeedReport()
    await _apply_in_session(session, r1)
    inserted_first = r1.rows_inserted

    r2 = SeedReport()
    await _apply_in_session(session, r2)
    assert r2.rows_inserted == 0
    assert str(user.id) not in r2.user_ids_seeded
    assert inserted_first >= len(DEFAULT_CONSENTS)
