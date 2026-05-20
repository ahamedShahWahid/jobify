"""CRUD + invariants on User and Applicant models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import Applicant, Employer, Job, JobEmbedding, JobStatus, Match, User, UserRole


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


@pytest.mark.integration
async def test_create_job_embedding(session: AsyncSession) -> None:
    employer = Employer(name="Test Co", name_norm="test co")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Engineer",
        description="x",
        min_exp_years=1,
        max_exp_years=3,
    )
    session.add(job)
    await session.flush()

    je = JobEmbedding(
        job_id=job.id,
        embedding=[0.1] * 1536,
        model_name="test-model",
        canonicalized_text_hash="a" * 64,
        input_tokens=42,
    )
    session.add(je)
    await session.commit()

    loaded = (
        await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))
    ).scalar_one()
    assert len(loaded.embedding) == 1536
    assert loaded.model_name == "test-model"
    assert loaded.canonicalized_text_hash == "a" * 64


@pytest.mark.integration
async def test_job_embedding_job_id_is_unique(session: AsyncSession) -> None:
    employer = Employer(name="Test Co2", name_norm="test co2")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Engineer",
        description="x",
        min_exp_years=1,
        max_exp_years=3,
    )
    session.add(job)
    await session.flush()

    session.add(
        JobEmbedding(
            job_id=job.id,
            embedding=[0.1] * 1536,
            model_name="test-model",
            canonicalized_text_hash="a" * 64,
            input_tokens=1,
        )
    )
    await session.commit()
    session.add(
        JobEmbedding(
            job_id=job.id,  # same job_id
            embedding=[0.2] * 1536,
            model_name="test-model",
            canonicalized_text_hash="b" * 64,
            input_tokens=2,
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_job_embedding_cascades_on_job_hard_delete(session: AsyncSession) -> None:
    employer = Employer(name="Test Co3", name_norm="test co3")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Engineer",
        description="x",
        min_exp_years=1,
        max_exp_years=3,
    )
    session.add(job)
    await session.flush()
    session.add(
        JobEmbedding(
            job_id=job.id,
            embedding=[0.1] * 1536,
            model_name="test-model",
            canonicalized_text_hash="a" * 64,
            input_tokens=1,
        )
    )
    await session.commit()

    await session.delete(job)
    await session.commit()

    remaining = (
        await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))
    ).all()
    assert remaining == []


@pytest.mark.integration
async def test_create_match(session: AsyncSession) -> None:
    user = User(email="m@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="M Test")
    session.add(applicant)
    await session.flush()
    employer = Employer(name="MatchCo", name_norm="matchco")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="T",
        description="x",
        min_exp_years=1,
        max_exp_years=3,
    )
    session.add(job)
    await session.flush()

    m = Match(
        applicant_id=applicant.id,
        job_id=job.id,
        vector_score=0.8,
        structured_score=0.6,
        total_score=0.72,
        score_components={"location": 1.0, "exp": 0.5, "ctc": 0.3},
        model_versions={"applicant_model": "gemini-embedding-2", "vector_weight": 0.6},
    )
    session.add(m)
    await session.commit()

    loaded = (
        await session.execute(select(Match).where(Match.applicant_id == applicant.id))
    ).scalar_one()
    assert float(loaded.total_score) == pytest.approx(0.72)
    assert loaded.score_components["location"] == 1.0
    assert loaded.surfaced_at is None


@pytest.mark.integration
async def test_match_total_score_check_constraint(session: AsyncSession) -> None:
    user = User(email="m2@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="M2 Test")
    session.add(applicant)
    await session.flush()
    employer = Employer(name="MatchCo2", name_norm="matchco2")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="T",
        description="x",
        min_exp_years=1,
        max_exp_years=3,
    )
    session.add(job)
    await session.flush()

    session.add(
        Match(
            applicant_id=applicant.id,
            job_id=job.id,
            vector_score=0.5,
            structured_score=0.5,
            total_score=1.5,  # > 1, should violate CHECK
            score_components={},
            model_versions={},
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_match_applicant_job_partial_unique(session: AsyncSession) -> None:
    user = User(email="m3@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="M3 Test")
    session.add(applicant)
    await session.flush()
    employer = Employer(name="MatchCo3", name_norm="matchco3")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="T",
        description="x",
        min_exp_years=1,
        max_exp_years=3,
    )
    session.add(job)
    await session.flush()

    session.add(
        Match(
            applicant_id=applicant.id,
            job_id=job.id,
            vector_score=0.5,
            structured_score=0.5,
            total_score=0.5,
            score_components={},
            model_versions={},
        )
    )
    await session.commit()
    session.add(
        Match(
            applicant_id=applicant.id,
            job_id=job.id,  # same pair
            vector_score=0.6,
            structured_score=0.6,
            total_score=0.6,
            score_components={},
            model_versions={},
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
