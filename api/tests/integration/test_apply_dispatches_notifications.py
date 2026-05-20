"""Integration tests — apply trigger inserts email + in-app notification rows.

Per spec Decision #8:
- 201 new application → 2 notification rows (EMAIL + IN_APP).
- 200 idempotent re-apply (already applied) → no new rows.
- 200 re-apply after withdraw → no new rows (same logical application).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import mint_access_token
from kpa.db.models import (
    Applicant,
    Employer,
    Job,
    JobStatus,
    Notification,
    NotificationChannel,
    User,
    UserRole,
)

_JWT_SECRET = "x" * 32  # matches KPA_JWT_SECRET set by the integration fixtures


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_apply.py)
# ---------------------------------------------------------------------------


async def _make_applicant(
    session: AsyncSession, email: str = "notif-apply@example.com"
) -> tuple[User, Applicant]:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Notif Apply Test", locations=["Bangalore"])
    session.add(applicant)
    await session.flush()
    return user, applicant


async def _make_job_and_employer(
    session: AsyncSession,
    *,
    title: str = "Engineer",
    employer_name: str = "Acme",
) -> tuple[Job, Employer]:
    employer = Employer(name=employer_name, name_norm=employer_name.lower())
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title=title,
        description="x",
        locations=["Bangalore"],
        min_exp_years=1,
        max_exp_years=5,
        status=JobStatus.OPEN,
    )
    session.add(job)
    await session.flush()
    return job, employer


def _token_headers(user: User) -> dict[str, str]:
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    return {"Authorization": f"Bearer {token}"}


async def _count_notifications(session: AsyncSession, user_id: object) -> int:
    result = await session.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_201_inserts_email_and_in_app_rows(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """A fresh 201 apply inserts exactly 2 notification rows: one EMAIL, one IN_APP."""
    user, applicant = await _make_applicant(session, email="notif-apply-201@example.com")
    job, employer = await _make_job_and_employer(session, employer_name="NotifApply201Co")
    await session.commit()

    resp = await async_client.post(
        f"/v1/jobs/{job.id}/apply",
        headers=_token_headers(user),
    )
    assert resp.status_code == 201

    # Exactly 2 notification rows — one per channel.
    rows = (
        (
            await session.execute(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.channel)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2

    channels = {n.channel for n in rows}
    assert channels == {NotificationChannel.EMAIL, NotificationChannel.IN_APP}

    for n in rows:
        assert n.kind == "application_received"
        assert n.payload["job_title"] == job.title
        assert n.payload["employer_name"] == employer.name
        assert n.payload["job_id"] == str(job.id)


@pytest.mark.integration
async def test_apply_200_idempotent_does_not_insert(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """A second apply on an already-applied job returns 200 and inserts no new notifications."""
    user, applicant = await _make_applicant(session, email="notif-apply-idem@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="NotifApplyIdemCo")
    await session.commit()

    headers = _token_headers(user)

    # First apply — 201, creates 2 notifications.
    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201

    count_after_first = await _count_notifications(session, user.id)
    assert count_after_first == 2

    # Second apply — 200 idempotent, must NOT create new rows.
    r2 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r2.status_code == 200

    count_after_second = await _count_notifications(session, user.id)
    assert count_after_second == 2  # still only 2


@pytest.mark.integration
async def test_re_apply_after_withdraw_does_not_insert(
    session: AsyncSession, async_client: AsyncClient
) -> None:
    """Apply → withdraw → re-apply: 2 notification rows total (no new rows on re-apply)."""
    user, applicant = await _make_applicant(session, email="notif-reapply@example.com")
    job, _ = await _make_job_and_employer(session, employer_name="NotifReapplyCo")
    await session.commit()

    headers = _token_headers(user)

    # First apply — 201.
    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r1.status_code == 201
    application_id = r1.json()["id"]

    count_after_apply = await _count_notifications(session, user.id)
    assert count_after_apply == 2

    # Withdraw — 200.
    r2 = await async_client.patch(
        f"/v1/applications/{application_id}",
        json={"status": "withdrawn"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "withdrawn"

    # Re-apply — 200 (updates the withdrawn row back to applied). No new notifications.
    r3 = await async_client.post(f"/v1/jobs/{job.id}/apply", headers=headers)
    assert r3.status_code == 200
    assert r3.json()["id"] == application_id
    assert r3.json()["status"] == "applied"

    count_after_reapply = await _count_notifications(session, user.id)
    assert count_after_reapply == 2  # still only 2
