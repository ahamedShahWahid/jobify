"""Integration test: with a fake explainer injected, the score worker routes
the explanation through the factory and stores the fake's marker generator.

Confirms the wiring established in Tasks 5-6 (score_applicant.py and
score_job.py both call get_match_explainer().explain(ctx) instead of the
inline templated function)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from jobify.workers.tasks.score_applicant import _score_applicant_async


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


@pytest.mark.integration
async def test_score_applicant_routes_through_match_explainer_factory(
    session: AsyncSession,
    patched_match_explainer,  # fixture has side effect of patching
) -> None:
    """A scored applicant with a job that crosses threshold should produce a
    matches.explanation whose generator == 'fake-llm' (the fake's marker)."""
    user = User(email="wiring@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(
        user_id=user.id,
        full_name="Wiring Test",
        locations=["Bangalore"],
        years_experience=4,
    )
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
    employer = Employer(name="Acme", name_norm="acme")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Engineer",
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
            embedding=[1.0] * 1536,  # parallel to applicant → vector score 1.0 → surfaces
            model_name="test-model",
            canonicalized_text_hash="b" * 64,
            input_tokens=10,
        )
    )
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    row = (
        await session.execute(
            select(Match).where(Match.applicant_id == applicant.id, Match.job_id == job.id)
        )
    ).scalar_one()
    assert row.explanation is not None
    assert row.explanation["generator"] == "fake-llm"
    assert row.explanation["fit"] == "fake-llm fit string"
    assert row.explanation["generator_version"] == "test"
