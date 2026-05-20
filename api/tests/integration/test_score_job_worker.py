"""Integration tests for score_job — mirror of score_applicant tests, axes swapped."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kpa.db.models import (
    Applicant,
    ApplicantEmbedding,
    Employer,
    Job,
    JobEmbedding,
    Match,
    User,
    UserRole,
)
from kpa.workers.tasks.score_job import _score_job_async


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


async def _seed_applicant_with_emb(session: AsyncSession, *, email: str) -> Applicant:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="A", locations=["Bangalore"])
    session.add(applicant)
    await session.flush()
    session.add(
        ApplicantEmbedding(
            applicant_id=applicant.id,
            embedding=[1.0] * 1536,
            model_name="test-model",
            canonicalized_text_hash="a" * 64,
            input_tokens=10,
        )
    )
    await session.flush()
    return applicant


async def _seed_job_with_emb(session: AsyncSession, *, employer_name: str = "JobCo") -> Job:
    employer = Employer(name=employer_name, name_norm=employer_name.lower())
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="JobT",
        description="x",
        locations=["Bangalore"],
        min_exp_years=1,
        max_exp_years=5,
    )
    session.add(job)
    await session.flush()
    session.add(
        JobEmbedding(
            job_id=job.id,
            embedding=[1.0] * 1536,
            model_name="test-model",
            canonicalized_text_hash="b" * 64,
            input_tokens=10,
        )
    )
    await session.flush()
    return job


@pytest.mark.integration
async def test_score_job_writes_rows_for_all_applicants_with_embeddings(
    session: AsyncSession,
) -> None:
    a1 = await _seed_applicant_with_emb(session, email="a1@example.com")
    a2 = await _seed_applicant_with_emb(session, email="a2@example.com")
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))

    rows = (await session.execute(select(Match).where(Match.job_id == job.id))).scalars().all()
    applicant_ids = {r.applicant_id for r in rows}
    assert applicant_ids == {a1.id, a2.id}


@pytest.mark.integration
async def test_score_job_skips_applicants_without_embeddings(session: AsyncSession) -> None:
    a_with = await _seed_applicant_with_emb(session, email="aw@example.com")
    # applicant without embedding
    user = User(email="ano@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    a_no = Applicant(user_id=user.id, full_name="NoEmb", locations=["Bangalore"])
    session.add(a_no)
    await session.flush()
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))

    rows = (await session.execute(select(Match).where(Match.job_id == job.id))).scalars().all()
    applicant_ids = {r.applicant_id for r in rows}
    assert applicant_ids == {a_with.id}


@pytest.mark.integration
async def test_score_job_idempotent_upsert(session: AsyncSession) -> None:
    await _seed_applicant_with_emb(session, email="idem@example.com")
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))
    await _score_job_async(job.id, sm=_make_sm(session))

    rows = (await session.execute(select(func.count()).select_from(Match))).scalar_one()
    assert rows == 1


@pytest.mark.integration
async def test_score_job_skips_deleted_job(session: AsyncSession) -> None:
    await _seed_applicant_with_emb(session, email="del@example.com")
    job = await _seed_job_with_emb(session)
    job.deleted_at = datetime.now(UTC)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))

    rows = (await session.execute(select(func.count()).select_from(Match))).scalar_one()
    assert rows == 0


@pytest.mark.integration
async def test_score_job_skips_when_no_job_embedding(session: AsyncSession) -> None:
    await _seed_applicant_with_emb(session, email="noje@example.com")
    employer = Employer(name="NoEmbCo", name_norm="noembco")
    session.add(employer)
    await session.flush()
    job_without = Job(
        employer_id=employer.id,
        title="J",
        description="x",
        min_exp_years=1,
        max_exp_years=3,
    )
    session.add(job_without)
    await session.commit()

    await _score_job_async(job_without.id, sm=_make_sm(session))

    rows = (await session.execute(select(func.count()).select_from(Match))).scalar_one()
    assert rows == 0
