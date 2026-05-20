"""End-to-end tests for the embed_job worker against a real Postgres + fake provider."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kpa.db.models import Employer, Job, JobEmbedding
from kpa.integrations.embeddings.base import (
    EmbeddingProviderError,
    TransientEmbeddingError,
)
from kpa.workers.tasks.embed_job import _embed_job_async, embed_job


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """Build a sessionmaker that shares the test's DB connection.

    The ``session`` fixture holds an outer transaction; ``session.bind``
    is the ``AsyncConnection`` the sessionmaker was created with.  Binding
    the worker's sessionmaker to the same connection lets ``_embed_job_async``
    see rows committed inside the test's savepoints without requiring a real
    COMMIT to the database.
    """
    return async_sessionmaker(
        bind=session.bind,  # AsyncConnection from the session fixture
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


async def _make_job(session: AsyncSession, *, title: str = "Engineer") -> Job:
    employer = Employer(name="Acme", name_norm="acme")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title=title,
        description="Build APIs.",
        locations=["Bangalore"],
        min_exp_years=3,
        max_exp_years=6,
    )
    session.add(job)
    await session.flush()
    await session.commit()
    return job


@pytest.mark.integration
async def test_embed_job_happy_path(session: AsyncSession, patched_embedding_provider) -> None:
    job = await _make_job(session)
    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    row = (
        await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))
    ).scalar_one()
    assert len(row.embedding) == 1536
    assert row.model_name == patched_embedding_provider.model_name
    assert len(row.canonicalized_text_hash) == 64


@pytest.mark.integration
async def test_embed_job_idempotent_on_unchanged_hash(
    session: AsyncSession, patched_embedding_provider
) -> None:
    job = await _make_job(session)
    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    first_calls = len(patched_embedding_provider.calls)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    second_calls = len(patched_embedding_provider.calls)
    # Second call should hit the Txn 1 gate and short-circuit.
    assert second_calls == first_calls


@pytest.mark.integration
async def test_embed_job_aborts_on_hash_drift_in_txn3(
    session: AsyncSession, patched_embedding_provider, monkeypatch
) -> None:
    job = await _make_job(session)

    # Force canonicalize_job to return one hash on call 1 (Txn 1) and a
    # different hash on call 2 (Txn 3) so the Txn 3 verify fails.
    real_canon = __import__(
        "kpa.workers.tasks.embed_job", fromlist=["canonicalize_job"]
    ).canonicalize_job
    call_count = {"n": 0}

    def _drifty(job_arg, *, employer_name):
        call_count["n"] += 1
        text, hash_hex = real_canon(job_arg, employer_name=employer_name)
        if call_count["n"] >= 2:
            return text, "f" * 64  # different hash on the verify
        return text, hash_hex

    monkeypatch.setattr("kpa.workers.tasks.embed_job.canonicalize_job", _drifty)
    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    rows = (await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))).all()
    assert rows == []


@pytest.mark.integration
async def test_embed_job_skips_deleted_job(
    session: AsyncSession, patched_embedding_provider
) -> None:
    job = await _make_job(session)
    job.deleted_at = datetime.now(UTC)
    await session.commit()
    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    rows = (await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))).all()
    assert rows == []


@pytest.mark.integration
async def test_embed_job_skips_deleted_employer(
    session: AsyncSession, patched_embedding_provider
) -> None:
    job = await _make_job(session)
    # Soft-delete the employer (not the job)
    employer = (
        await session.execute(select(Employer).where(Employer.id == job.employer_id))
    ).scalar_one()
    employer.deleted_at = datetime.now(UTC)
    await session.commit()
    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    rows = (await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))).all()
    assert rows == []


@pytest.mark.integration
async def test_embed_job_handles_update(session: AsyncSession, patched_embedding_provider) -> None:
    job = await _make_job(session)
    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    original = (
        await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))
    ).scalar_one()
    original_id = original.id
    original_hash = original.canonicalized_text_hash

    # Mutate the description and re-embed
    await session.refresh(job)
    job.description = "Updated description with different content."
    await session.commit()

    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    # Use populate_existing=True so the identity map re-reads from the DB rather
    # than returning the stale cached object after the worker's UPSERT.
    updated = (
        await session.execute(
            select(JobEmbedding)
            .where(JobEmbedding.job_id == job.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert updated.id == original_id  # UPSERT preserved row id
    assert updated.canonicalized_text_hash != original_hash


@pytest.mark.integration
@pytest.mark.xfail(
    reason=(
        "eager-mode autoretry: task_eager_propagates=True causes TransientEmbeddingError"
        " to propagate rather than retry inline in eager mode"
    )
)
async def test_embed_job_transient_error_retries(
    session: AsyncSession, embedding_provider, monkeypatch
) -> None:
    """Fake provider raises Transient once, then succeeds. Eager-mode autoretry replays inline."""
    job = await _make_job(session)
    original_encode = embedding_provider.encode
    calls = {"n": 0}

    async def _flaky(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TransientEmbeddingError("simulated flake")
        return await original_encode(**kw)

    monkeypatch.setattr(embedding_provider, "encode", _flaky)
    # Re-apply the patches because we changed the provider object
    import kpa.workers.celery_app as cel
    import kpa.workers.tasks.embed as embed_mod
    import kpa.workers.tasks.embed_job as embed_job_mod

    monkeypatch.setattr(cel, "get_embedding_provider", lambda: embedding_provider)
    monkeypatch.setattr(embed_mod, "get_embedding_provider", lambda: embedding_provider)
    monkeypatch.setattr(embed_job_mod, "get_embedding_provider", lambda: embedding_provider)
    monkeypatch.setattr(cel, "_embedding_provider", embedding_provider)

    embed_job.delay(str(job.id))  # eager mode — runs inline with autoretry
    row = (
        await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))
    ).scalar_one_or_none()
    assert row is not None  # eventually succeeded
    assert calls["n"] >= 2  # retried at least once


@pytest.mark.integration
async def test_embed_job_permanent_error_does_not_retry(
    session: AsyncSession, embedding_provider, monkeypatch
) -> None:
    job = await _make_job(session)

    async def _broken(**kw):
        raise EmbeddingProviderError("simulated permanent error")

    monkeypatch.setattr(embedding_provider, "encode", _broken)
    import kpa.workers.celery_app as cel
    import kpa.workers.tasks.embed as embed_mod
    import kpa.workers.tasks.embed_job as embed_job_mod

    monkeypatch.setattr(cel, "get_embedding_provider", lambda: embedding_provider)
    monkeypatch.setattr(embed_mod, "get_embedding_provider", lambda: embedding_provider)
    monkeypatch.setattr(embed_job_mod, "get_embedding_provider", lambda: embedding_provider)
    monkeypatch.setattr(cel, "_embedding_provider", embedding_provider)

    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=embedding_provider)
    rows = (await session.execute(select(JobEmbedding).where(JobEmbedding.job_id == job.id))).all()
    assert rows == []  # permanent error → no row, no retry, no exception surfaced


@pytest.mark.integration
async def test_embed_job_dispatches_score_job(
    session: AsyncSession,
    patched_embedding_provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After embed_job Txn 3 commits, score_job.delay is called."""
    calls: list[str] = []

    def _spy(job_id_str: str) -> None:
        calls.append(job_id_str)

    monkeypatch.setattr("kpa.workers.tasks.score_job.score_job.delay", _spy)

    job = await _make_job(session)
    sm = _make_sm(session)
    await _embed_job_async(job.id, sm=sm, provider=patched_embedding_provider)
    assert len(calls) == 1
    assert calls[0] == str(job.id)
