"""End-to-end tests for the seed_jobs loader against a real Postgres.

Uses the per-test savepoint session. We don't go through the CLI's
``_apply()`` because that opens its own engine; the helper
``_apply_in_session`` is the seam that lets these tests share the test
session and stay inside the outer rollback.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Employer, Job
from jobify.scripts.seed_jobs import (
    SeedPayload,
    SeedReport,
    _apply_in_session,
)

SAMPLE_JOBS_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_jobs.json"


def _payload(employers: list[dict], jobs: list[dict]) -> SeedPayload:
    return SeedPayload.model_validate({"version": 1, "employers": employers, "jobs": jobs})


def _employer_dict(name: str = "Acme", **kw) -> dict:
    return {"name": name, "gst": kw.get("gst"), "verified": kw.get("verified", False)}


def _job_dict(employer_name: str = "Acme", title: str = "Engineer", **kw) -> dict:
    return {
        "employer_name": employer_name,
        "title": title,
        "description": kw.get("description", "x"),
        "locations": kw.get("locations", []),
        "min_exp_years": kw.get("min_exp_years", 0),
        "max_exp_years": kw.get("max_exp_years", 2),
        "ctc_min": kw.get("ctc_min"),
        "ctc_max": kw.get("ctc_max"),
        "status": kw.get("status", "open"),
        "posted_days_ago": kw.get("posted_days_ago", 0),
    }


@pytest.mark.integration
async def test_seed_creates_employers_and_jobs(session: AsyncSession) -> None:
    payload = _payload([_employer_dict()], [_job_dict()])
    report = SeedReport()
    await _apply_in_session(session, payload, report)
    assert report.employers_inserted == 1
    assert report.jobs_inserted == 1
    employer = (
        await session.execute(select(Employer).where(Employer.name_norm == "acme"))
    ).scalar_one()
    assert employer.name == "Acme"
    job = (await session.execute(select(Job).where(Job.employer_id == employer.id))).scalar_one()
    assert job.title == "Engineer"


@pytest.mark.integration
async def test_seed_is_idempotent(session: AsyncSession) -> None:
    payload = _payload([_employer_dict()], [_job_dict()])
    await _apply_in_session(session, payload, SeedReport())
    await _apply_in_session(session, payload, SeedReport())
    employers = (await session.execute(select(func.count()).select_from(Employer))).scalar_one()
    jobs = (await session.execute(select(func.count()).select_from(Job))).scalar_one()
    assert employers == 1
    assert jobs == 1


@pytest.mark.integration
async def test_seed_updates_existing_employer_fields(session: AsyncSession) -> None:
    session.add(Employer(name="Acme", name_norm="acme"))  # gst NULL, verified_at NULL
    await session.flush()
    payload = _payload(
        [_employer_dict(gst="27AABCU9603R1Z2", verified=True)],
        [_job_dict()],
    )
    report = SeedReport()
    await _apply_in_session(session, payload, report)
    assert report.employers_updated == 1
    employer = (
        await session.execute(select(Employer).where(Employer.name_norm == "acme"))
    ).scalar_one()
    assert employer.gst == "27AABCU9603R1Z2"
    assert employer.verified_at is not None


@pytest.mark.integration
async def test_seed_preserves_existing_employer_name(session: AsyncSession) -> None:
    session.add(Employer(name="Acme Co", name_norm="acme co"))
    await session.flush()
    payload = _payload(
        [_employer_dict(name="  ACME  CO  ", verified=True)],
        [_job_dict(employer_name="  ACME  CO  ")],
    )
    await _apply_in_session(session, payload, SeedReport())
    employer = (
        await session.execute(select(Employer).where(Employer.name_norm == "acme co"))
    ).scalar_one()
    assert employer.name == "Acme Co"  # not trampled


@pytest.mark.integration
async def test_seed_preserves_existing_verified_at(session: AsyncSession) -> None:
    pinned = datetime(2025, 1, 1, tzinfo=UTC)
    session.add(Employer(name="Acme", name_norm="acme", verified_at=pinned))
    await session.flush()
    payload = _payload(
        [_employer_dict(verified=True)],
        [_job_dict()],
    )
    await _apply_in_session(session, payload, SeedReport())
    employer = (
        await session.execute(select(Employer).where(Employer.name_norm == "acme"))
    ).scalar_one()
    assert employer.verified_at == pinned


@pytest.mark.integration
async def test_seed_updates_existing_job(session: AsyncSession) -> None:
    employer = Employer(name="Acme", name_norm="acme")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Engineer",
        description="old",
        min_exp_years=1,
        max_exp_years=2,
    )
    session.add(job)
    await session.flush()
    original_id = job.id

    payload = _payload(
        [_employer_dict()],
        [_job_dict(description="new", locations=["Bangalore"], min_exp_years=2, max_exp_years=4)],
    )
    report = SeedReport()
    await _apply_in_session(session, payload, report)
    assert report.jobs_updated == 1

    refreshed = (await session.execute(select(Job).where(Job.id == original_id))).scalar_one()
    assert refreshed.description == "new"
    assert refreshed.locations == ["Bangalore"]
    assert refreshed.min_exp_years == 2
    assert refreshed.max_exp_years == 4


@pytest.mark.integration
async def test_dry_run_in_session_does_not_persist(session: AsyncSession) -> None:
    """The CLI's ``_apply()`` handles rollback; the in-session helper does
    not. This test guards the helper's contract: it never commits, only
    flushes. The outer savepoint rollback wipes everything regardless,
    but the row count *during* the test should reflect inserts."""
    payload = _payload([_employer_dict()], [_job_dict()])
    await _apply_in_session(session, payload, SeedReport())
    employers = (await session.execute(select(func.count()).select_from(Employer))).scalar_one()
    assert employers == 1


@pytest.mark.integration
async def test_loader_against_sample_jobs_json(session: AsyncSession) -> None:
    """Drift guard for the checked-in canonical fixture."""
    raw = json.loads(SAMPLE_JOBS_PATH.read_text())
    payload = SeedPayload.model_validate(raw)
    report = SeedReport()
    await _apply_in_session(session, payload, report)
    assert report.employers_inserted == 10
    assert report.jobs_inserted == 27


@pytest.mark.integration
async def test_seed_dispatches_embed_per_upserted_job(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seed CLI fires embed_job.delay() for every inserted/updated job."""
    calls: list[str] = []

    def _spy(job_id_str: str) -> None:
        calls.append(job_id_str)

    monkeypatch.setattr("jobify.workers.tasks.embed_job.embed_job.delay", _spy)

    payload = _payload(
        [_employer_dict()],
        [_job_dict(), _job_dict(title="Other")],
    )
    report = SeedReport()
    await _apply_in_session(session, payload, report)
    from jobify.scripts.seed_jobs import _dispatch_embeds

    _dispatch_embeds(report.inserted_job_ids + report.updated_job_ids)
    assert len(calls) == 2
    assert set(calls) == {str(jid) for jid in report.inserted_job_ids}


@pytest.mark.integration
async def test_seed_swallows_broker_outage(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If embed_job.delay raises, the seed CLI logs and continues without raising."""

    def _broken(job_id_str: str) -> None:
        raise RuntimeError("broker down")

    monkeypatch.setattr("jobify.workers.tasks.embed_job.embed_job.delay", _broken)

    # Capture structlog warning calls via the _log bound in seed_jobs.
    warning_events: list[str] = []
    import jobify.scripts.seed_jobs as seed_jobs_mod

    original_log = seed_jobs_mod._log

    class _CapturingLog:
        def warning(self, event: str, **kw: object) -> None:
            warning_events.append(event)

        def __getattr__(self, name: str) -> object:
            return getattr(original_log, name)

    monkeypatch.setattr(seed_jobs_mod, "_log", _CapturingLog())

    payload = _payload([_employer_dict()], [_job_dict()])
    report = SeedReport()
    await _apply_in_session(session, payload, report)
    from jobify.scripts.seed_jobs import _dispatch_embeds

    # Should not raise.
    _dispatch_embeds(report.inserted_job_ids + report.updated_job_ids)

    # Should have logged a warning per failed dispatch.
    assert "embed.dispatch-failed" in warning_events
