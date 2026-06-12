"""Integration tests for score_applicant — real Postgres, fake-vector setup."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import jobify.workers.tasks.score_applicant as score_applicant_task
from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    Employer,
    Job,
    JobEmbedding,
    Match,
    User,
    UserRole,
)
from jobify.scoring.match import TransientScoringError
from jobify.workers.tasks.score_applicant import _score_applicant_async


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """Wrap the test's savepoint-bound session into a sessionmaker so the
    worker's _score_applicant_async sees the test's data."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


async def _seed_applicant(session: AsyncSession, *, email: str = "s@example.com") -> Applicant:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="S Test", locations=["Bangalore"])
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


async def _seed_job(
    session: AsyncSession,
    *,
    title: str = "Engineer",
    employer_name: str = "Acme",
    locations: list[str] | None = None,
    embedding: list[float] | None = None,
) -> Job:
    employer = Employer(name=employer_name, name_norm=employer_name.lower())
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title=title,
        description="x",
        locations=locations or ["Bangalore"],
        min_exp_years=1,
        max_exp_years=5,
    )
    session.add(job)
    await session.flush()
    if embedding is not None:
        session.add(
            JobEmbedding(
                job_id=job.id,
                embedding=embedding,
                model_name="test-model",
                canonicalized_text_hash="b" * 64,
                input_tokens=10,
            )
        )
    await session.flush()
    return job


@pytest.mark.integration
async def test_score_applicant_writes_rows_for_all_open_jobs(session: AsyncSession) -> None:
    applicant = await _seed_applicant(session)
    j1 = await _seed_job(session, title="A", embedding=[1.0] * 1536)
    j2 = await _seed_job(session, title="B", employer_name="Beta", embedding=[1.0] * 1536)
    j3 = await _seed_job(session, title="C", employer_name="Gamma", embedding=[1.0] * 1536)
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    rows = (
        (await session.execute(select(Match).where(Match.applicant_id == applicant.id)))
        .scalars()
        .all()
    )
    job_ids = {r.job_id for r in rows}
    assert job_ids == {j1.id, j2.id, j3.id}

    # Each row has a templated explanation populated.
    for row in rows:
        assert row.explanation is not None
        assert "fit" in row.explanation
        assert row.explanation["generator"] == "templated"
        assert row.explanation["generator_version"] == "1"


@pytest.mark.integration
async def test_score_applicant_batches_and_dispatches_cursor(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    applicant = await _seed_applicant(session)
    j1 = await _seed_job(session, title="A", embedding=[1.0] * 1536)
    j2 = await _seed_job(session, title="B", employer_name="Beta", embedding=[1.0] * 1536)
    await session.commit()

    dispatched: list[tuple[object, object]] = []
    monkeypatch.setattr(
        score_applicant_task,
        "_dispatch_next_batch",
        lambda applicant_id, after_job_id: dispatched.append((applicant_id, after_job_id)),
    )

    await _score_applicant_async(applicant.id, sm=_make_sm(session), batch_size=1)

    ordered_job_ids = (
        (await session.execute(select(Job.id).where(Job.id.in_([j1.id, j2.id])).order_by(Job.id)))
        .scalars()
        .all()
    )
    rows = (
        (await session.execute(select(Match).where(Match.applicant_id == applicant.id)))
        .scalars()
        .all()
    )
    assert [row.job_id for row in rows] == [ordered_job_ids[0]]
    assert dispatched == [(applicant.id, ordered_job_ids[0])]


def test_score_applicant_next_batch_dispatch_failure_is_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_delay(*_args: object) -> None:
        raise RuntimeError("broker down")

    monkeypatch.setattr(score_applicant_task.score_applicant, "delay", fail_delay)

    with pytest.raises(TransientScoringError):
        score_applicant_task._dispatch_next_batch(uuid4(), uuid4())


@pytest.mark.integration
async def test_score_applicant_skips_jobs_without_embeddings(session: AsyncSession) -> None:
    applicant = await _seed_applicant(session)
    j_with = await _seed_job(session, title="WithEmb", embedding=[1.0] * 1536)
    j_without = await _seed_job(session, title="NoEmb", employer_name="Beta")  # no embedding
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    rows = (
        (await session.execute(select(Match).where(Match.applicant_id == applicant.id)))
        .scalars()
        .all()
    )
    job_ids = {r.job_id for r in rows}
    assert job_ids == {j_with.id}
    assert j_without.id not in job_ids


@pytest.mark.integration
async def test_score_applicant_surfaces_above_threshold(session: AsyncSession) -> None:
    """Same-vector applicant + job → vector_score=1.0 → total above default threshold."""
    applicant = await _seed_applicant(session)
    j = await _seed_job(session, title="High", embedding=[1.0] * 1536)
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    row = (await session.execute(select(Match).where(Match.job_id == j.id))).scalar_one()
    assert row.surfaced_at is not None
    assert float(row.total_score) >= 0.55


@pytest.mark.integration
async def test_score_applicant_does_not_surface_below_threshold(
    session: AsyncSession,
) -> None:
    """Orthogonal vectors + Mumbai-Bangalore mismatch → low total."""
    user = User(email="s2@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="S2", locations=["Mumbai"])
    session.add(applicant)
    await session.flush()
    emb = [0.0] * 1536
    emb[0] = 1.0  # applicant unit vector along axis 0
    session.add(
        ApplicantEmbedding(
            applicant_id=applicant.id,
            embedding=emb,
            model_name="test-model",
            canonicalized_text_hash="a" * 64,
            input_tokens=10,
        )
    )
    job_emb = [0.0] * 1536
    job_emb[1] = 1.0  # orthogonal
    j = await _seed_job(session, title="Far", locations=["Bangalore"], embedding=job_emb)
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    row = (await session.execute(select(Match).where(Match.job_id == j.id))).scalar_one()
    assert row.surfaced_at is None
    assert float(row.total_score) < 0.55


@pytest.mark.integration
async def test_score_applicant_idempotent_upsert(session: AsyncSession) -> None:
    applicant = await _seed_applicant(session)
    j = await _seed_job(session, title="Idem", embedding=[1.0] * 1536)
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))
    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    rows = (
        (await session.execute(select(Match).where(Match.applicant_id == applicant.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].job_id == j.id


@pytest.mark.integration
async def test_score_applicant_preserves_surfaced_at_on_rescore(
    session: AsyncSession,
) -> None:
    """First run surfaces; second run is forced to drop below threshold; surfaced_at stays."""
    applicant = await _seed_applicant(session)
    j = await _seed_job(session, title="Pres", embedding=[1.0] * 1536)
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))
    row = (
        await session.execute(
            select(Match).where(Match.job_id == j.id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    first_surfaced = row.surfaced_at
    assert first_surfaced is not None

    # Replace the job_embedding with an orthogonal one so the rescore drops.
    bad_emb = [0.0] * 1536
    bad_emb[0] = 1.0
    job_emb_row = (
        await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == j.id))
    ).scalar_one()
    job_emb_row.embedding = [0.0] * 1536
    job_emb_row.embedding[1] = 1.0  # orthogonal to applicant
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))
    row2 = (
        await session.execute(
            select(Match).where(Match.job_id == j.id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert row2.surfaced_at == first_surfaced  # preserved


@pytest.mark.integration
async def test_score_applicant_skips_deleted_applicant(session: AsyncSession) -> None:
    applicant = await _seed_applicant(session)
    await _seed_job(session, title="Z", embedding=[1.0] * 1536)
    applicant.deleted_at = datetime.now(UTC)
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    rows = (await session.execute(select(func.count()).select_from(Match))).scalar_one()
    assert rows == 0


@pytest.mark.integration
async def test_score_applicant_skips_when_no_applicant_embedding(
    session: AsyncSession,
) -> None:
    user = User(email="noemb@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="NoEmb", locations=["Bangalore"])
    session.add(applicant)
    await session.flush()
    await _seed_job(session, title="W", embedding=[1.0] * 1536)
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    rows = (await session.execute(select(func.count()).select_from(Match))).scalar_one()
    assert rows == 0
