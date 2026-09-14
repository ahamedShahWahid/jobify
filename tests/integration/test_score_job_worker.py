"""Integration tests for score_job — mirror of score_applicant tests, axes swapped."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    ApplicantPreferences,
    Employer,
    Job,
    JobEmbedding,
    Match,
    User,
    UserRole,
)
from jobify.scoring.explainer import ExplainContext
from jobify_worker.tasks.score_job import _score_job_async
from tests.integration.outbox_helpers import task_event_args

pytestmark = pytest.mark.integration


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


async def _seed_applicant_with_emb(
    session: AsyncSession, *, email: str, language: str = "en"
) -> Applicant:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="A")
    session.add(applicant)
    await session.flush()
    session.add(
        ApplicantPreferences(applicant_id=applicant.id, locations=["Bangalore"], language=language)
    )
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

    # Each row has a templated explanation populated.
    for row in rows:
        assert row.explanation is not None
        assert "fit" in row.explanation
        assert row.explanation["generator"] == "templated"
        assert row.explanation["generator_version"] == "1"


@pytest.mark.integration
async def test_score_job_resolves_language_per_applicant(session: AsyncSession) -> None:
    """One job scores many applicants — language must resolve per applicant row,
    not be fixed once for the whole batch (see score_job.py language wiring)."""
    a_hi = await _seed_applicant_with_emb(session, email="hi@example.com", language="hi")
    a_en = await _seed_applicant_with_emb(session, email="en@example.com", language="en")
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))

    row_hi = (
        await session.execute(select(Match).where(Match.applicant_id == a_hi.id))
    ).scalar_one()
    row_en = (
        await session.execute(select(Match).where(Match.applicant_id == a_en.id))
    ).scalar_one()
    assert any("ऀ" <= ch <= "ॿ" for ch in row_hi.explanation["fit"])
    assert not any("ऀ" <= ch <= "ॿ" for ch in row_en.explanation["fit"])


@pytest.mark.integration
async def test_score_job_batches_and_dispatches_cursor(
    session: AsyncSession,
) -> None:
    a1 = await _seed_applicant_with_emb(session, email="a1@example.com")
    a2 = await _seed_applicant_with_emb(session, email="a2@example.com")
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session), batch_size=1)

    ordered_applicant_ids = (
        (
            await session.execute(
                select(Applicant.id).where(Applicant.id.in_([a1.id, a2.id])).order_by(Applicant.id)
            )
        )
        .scalars()
        .all()
    )
    rows = (await session.execute(select(Match).where(Match.job_id == job.id))).scalars().all()
    assert [row.applicant_id for row in rows] == [ordered_applicant_ids[0]]
    assert [str(job.id), str(ordered_applicant_ids[0])] in await task_event_args(
        session, "jobify.score_job"
    )


@pytest.mark.integration
async def test_score_job_skips_applicants_without_embeddings(session: AsyncSession) -> None:
    a_with = await _seed_applicant_with_emb(session, email="aw@example.com")
    # applicant without embedding
    user = User(email="ano@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    a_no = Applicant(user_id=user.id, full_name="NoEmb")
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
async def test_score_job_scores_applicant_without_preferences_row(
    session: AsyncSession,
) -> None:
    """Seeded/test applicant with an embedding but NO preferences row —
    the outer join degrades to empty preferences instead of dropping them."""
    user = User(email="noprefs-job@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="NoPrefs")
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
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))

    row = (
        await session.execute(select(Match).where(Match.applicant_id == applicant.id))
    ).scalar_one()
    assert row.job_id == job.id
    # Empty-preference degrade: no location signal (0.5), no ctc signal (0.5).
    assert row.score_components["location"] == 0.5
    assert row.score_components["ctc"] == 0.5


@pytest.mark.integration
async def test_score_job_soft_deleted_preferences_treated_as_missing(
    session: AsyncSession,
) -> None:
    """Pins the ON-clause fix — a soft-deleted preferences row degrades to
    "no prefs"; before the fix this applicant was silently dropped."""
    applicant = await _seed_applicant_with_emb(session, email="softdel-job@example.com")
    prefs = (
        await session.execute(
            select(ApplicantPreferences).where(ApplicantPreferences.applicant_id == applicant.id)
        )
    ).scalar_one()
    prefs.deleted_at = datetime.now(UTC)
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))

    row = (
        await session.execute(select(Match).where(Match.applicant_id == applicant.id))
    ).scalar_one()
    assert row.job_id == job.id
    # Treated as no prefs: seeded ["Bangalore"] is ignored → no-signal 0.5.
    assert row.score_components["location"] == 0.5
    assert row.score_components["ctc"] == 0.5


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


def _calls_for_seeded_applicant(explainer) -> list[ExplainContext]:
    """score_job walks EVERY applicant with an embedding, including whatever
    pre-existing rows the shared local dev DB happens to already have (this
    file's own tests already tolerate that noise by not asserting exact
    per-run scored-row counts against the whole table — see e.g.
    test_score_job_writes_rows_for_all_applicants_with_embeddings' known
    flakiness under a populated DB). Those rows have no ApplicantPreferences
    (score.preferences-missing), which _seed_applicant_with_emb's rows always
    have — locations=["Bangalore"] reliably isolates calls for the applicant
    THIS test actually seeded from that unrelated noise."""
    return [c for c in explainer.calls if c.applicant_locations == ["Bangalore"]]


@pytest.mark.integration
async def test_score_job_rescore_reuses_cached_explanation(
    session: AsyncSession,
    patched_match_explainer,
) -> None:
    """PERF-01: a rescore whose explanation-relevant inputs are unchanged
    must not call the explainer a second time."""
    applicant = await _seed_applicant_with_emb(session, email="cache-reuse@example.com")
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))
    assert len(_calls_for_seeded_applicant(patched_match_explainer)) == 1

    await _score_job_async(job.id, sm=_make_sm(session))

    # unchanged — the rerun hit the cache
    assert len(_calls_for_seeded_applicant(patched_match_explainer)) == 1

    row = (
        await session.execute(
            select(Match).where(Match.applicant_id == applicant.id, Match.job_id == job.id)
        )
    ).scalar_one()
    assert row.explanation_key is not None
    assert row.explanation["fit"] == "fake-llm fit string"


@pytest.mark.integration
async def test_score_job_rescore_after_title_change_calls_explainer_again(
    session: AsyncSession,
    patched_match_explainer,
) -> None:
    """A real content change (job title) must still regenerate."""
    applicant = await _seed_applicant_with_emb(session, email="cache-miss@example.com")
    job = await _seed_job_with_emb(session)
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))
    assert len(_calls_for_seeded_applicant(patched_match_explainer)) == 1

    job.title = "Renamed Role"
    await session.commit()

    await _score_job_async(job.id, sm=_make_sm(session))

    assert len(_calls_for_seeded_applicant(patched_match_explainer)) == 2

    row = (
        await session.execute(
            select(Match).where(Match.applicant_id == applicant.id, Match.job_id == job.id)
        )
    ).scalar_one()
    assert row.explanation_key is not None
