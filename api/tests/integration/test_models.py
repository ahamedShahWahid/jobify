"""CRUD + invariants on User and Applicant models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import Applicant, Employer, Job, JobStatus, User, UserRole


@pytest.mark.integration
async def test_create_user_and_applicant(session: AsyncSession) -> None:
    user = User(email="a@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="A. Test", locations=["Bengaluru", "Pune"])
    session.add(applicant)
    await session.commit()

    loaded = (
        await session.execute(select(Applicant).where(Applicant.user_id == user.id))
    ).scalar_one()
    assert loaded.full_name == "A. Test"
    assert loaded.locations == ["Bengaluru", "Pune"]


@pytest.mark.integration
async def test_cascade_delete_user_deletes_applicant(session: AsyncSession) -> None:
    user = User(email="b@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    session.add(Applicant(user_id=user.id, full_name="B. Test"))
    await session.commit()

    await session.delete(user)
    await session.commit()

    remaining = (await session.execute(select(Applicant).where(Applicant.user_id == user.id))).all()
    assert remaining == []


@pytest.mark.integration
async def test_soft_delete_via_deleted_at(session: AsyncSession) -> None:
    user = User(email="c@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.commit()

    user.deleted_at = datetime.now(UTC)
    await session.commit()

    # Row still exists; only the column is set.
    refreshed = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.deleted_at is not None


@pytest.mark.integration
async def test_unique_email_constraint(session: AsyncSession) -> None:
    session.add(User(email="dup@example.com", role=UserRole.APPLICANT))
    await session.commit()
    session.add(User(email="dup@example.com", role=UserRole.APPLICANT))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_create_employer_and_job(session: AsyncSession) -> None:
    employer = Employer(name="Acme Corp", name_norm="acme corp")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Backend Engineer",
        description="Build APIs.",
        locations=["Bangalore", "Remote"],
        min_exp_years=3,
        max_exp_years=6,
    )
    session.add(job)
    await session.commit()

    loaded = (await session.execute(select(Job).where(Job.employer_id == employer.id))).scalar_one()
    assert loaded.title == "Backend Engineer"
    assert loaded.status == JobStatus.OPEN
    assert loaded.locations == ["Bangalore", "Remote"]


@pytest.mark.integration
async def test_exp_years_check_constraint(session: AsyncSession) -> None:
    employer = Employer(name="X", name_norm="x")
    session.add(employer)
    await session.flush()
    session.add(
        Job(
            employer_id=employer.id,
            title="Bad",
            description="...",
            min_exp_years=8,
            max_exp_years=3,  # < min
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_ctc_check_constraint(session: AsyncSession) -> None:
    employer = Employer(name="Y", name_norm="y")
    session.add(employer)
    await session.flush()
    session.add(
        Job(
            employer_id=employer.id,
            title="Bad CTC",
            description="...",
            min_exp_years=1,
            max_exp_years=2,
            ctc_min=2000000,
            ctc_max=1000000,  # < min
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_employer_name_norm_partial_unique(session: AsyncSession) -> None:
    session.add(Employer(name="Dup", name_norm="dup"))
    await session.commit()
    session.add(Employer(name="Dup Two", name_norm="dup"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_employer_name_norm_unique_ignores_soft_deleted(session: AsyncSession) -> None:
    e1 = Employer(name="Original", name_norm="original")
    session.add(e1)
    await session.commit()
    e1.deleted_at = datetime.now(UTC)
    await session.commit()

    # New row with the same name_norm should now succeed.
    session.add(Employer(name="Replacement", name_norm="original"))
    await session.commit()
