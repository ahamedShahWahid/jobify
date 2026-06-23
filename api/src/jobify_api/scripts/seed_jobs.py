"""Seed employers and jobs from a JSON fixture (idempotent).

Run via:
    uv run python -m jobify.scripts.seed_jobs [--from PATH] [--dry-run]
    uv run jobify-seed-jobs [--from PATH] [--dry-run]

Behavior:
1. Pydantic-validate the JSON. Any error → exit 2; nothing written.
2. Open one session against the engine in app_factory.
3. Upsert employers by ``name_norm``; then upsert jobs by
   ``(employer_id, lower(title))``. One COMMIT (or ROLLBACK on --dry-run).
4. Log row counts on completion.

Exit codes: 0 success, 2 validation, 3 DB error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import structlog
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Employer, Job, JobStatus
from jobify.db.session import create_engine_from_settings, make_sessionmaker
from jobify.settings import Settings

_log = structlog.get_logger(__name__)

_DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "sample_jobs.json"


# --- Pydantic input models ---------------------------------------------------

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
GST = Annotated[str, StringConstraints(strip_whitespace=True, min_length=15, max_length=15)]


class EmployerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    gst: GST | None = None
    verified: bool = False


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employer_name: Name
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: NonEmptyStr
    locations: list[Location] = Field(default_factory=list, max_length=10)
    min_exp_years: int = Field(ge=0, le=50)
    max_exp_years: int = Field(ge=0, le=50)
    ctc_min: float | None = Field(default=None, ge=0)
    ctc_max: float | None = Field(default=None, ge=0)
    status: str = "open"
    posted_days_ago: int = Field(ge=0, le=3650)

    @model_validator(mode="after")
    def _validate_ranges(self) -> JobInput:
        if self.max_exp_years < self.min_exp_years:
            raise ValueError("max_exp_years must be >= min_exp_years")
        if self.ctc_max is not None and self.ctc_min is not None and self.ctc_max < self.ctc_min:
            raise ValueError("ctc_max must be >= ctc_min")
        if self.status not in {"open", "closed"}:
            raise ValueError("status must be 'open' or 'closed'")
        return self


class SeedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    employers: list[EmployerInput]
    jobs: list[JobInput]

    @model_validator(mode="after")
    def _validate_payload(self) -> SeedPayload:
        if self.version != 1:
            raise ValueError(f"unsupported version: {self.version}")
        employer_names = {e.name for e in self.employers}
        for job in self.jobs:
            if job.employer_name not in employer_names:
                raise ValueError(f"job references unknown employer: {job.employer_name!r}")
        return self


# --- Helpers -----------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase + collapse internal whitespace + strip — the idempotency key
    for the partial-UNIQUE index on ``employers.name_norm``."""
    return _WHITESPACE_RE.sub(" ", name.strip()).lower()


@dataclass
class SeedReport:
    employers_inserted: int = 0
    employers_updated: int = 0
    jobs_inserted: int = 0
    jobs_updated: int = 0
    inserted_job_ids: list[uuid.UUID] = field(default_factory=list)
    updated_job_ids: list[uuid.UUID] = field(default_factory=list)
    dry_run: bool = False

    def as_log_kwargs(self) -> dict[str, int | bool]:
        return {
            "employers_inserted": self.employers_inserted,
            "employers_updated": self.employers_updated,
            "jobs_inserted": self.jobs_inserted,
            "jobs_updated": self.jobs_updated,
            "dry_run": self.dry_run,
        }


# --- IO + entry --------------------------------------------------------------


def _load_and_validate(path: Path) -> SeedPayload:
    raw = json.loads(path.read_text())
    return SeedPayload.model_validate(raw)


async def _apply(payload: SeedPayload, *, dry_run: bool) -> SeedReport:
    settings = Settings()
    engine = create_engine_from_settings(settings)
    sessionmaker = make_sessionmaker(engine)
    report = SeedReport(dry_run=dry_run)
    try:
        async with sessionmaker() as session:
            await _apply_in_session(session, payload, report)
            if dry_run:
                await session.rollback()
            else:
                await session.commit()
    finally:
        await engine.dispose()
    if not dry_run:
        _dispatch_embeds(report.inserted_job_ids + report.updated_job_ids)
    return report


async def _apply_in_session(
    session: AsyncSession, payload: SeedPayload, report: SeedReport
) -> None:
    """Body of the loader. Separated so integration tests can run it inside
    the savepoint-bound session without going through engine construction."""
    name_to_employer_id: dict[str, uuid.UUID] = {}
    for emp_raw in payload.employers:
        employer_id = await _upsert_employer(session, emp_raw, report)
        name_to_employer_id[emp_raw.name] = employer_id
    await session.flush()
    for job_raw in payload.jobs:
        await _upsert_job(session, job_raw, name_to_employer_id[job_raw.employer_name], report)
    await session.flush()


async def _upsert_employer(
    session: AsyncSession, raw: EmployerInput, report: SeedReport
) -> uuid.UUID:
    norm = normalize_name(raw.name)
    existing = (
        await session.execute(
            select(Employer).where(
                Employer.name_norm == norm,
                Employer.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        verified_at = datetime.now(UTC) if raw.verified else None
        employer = Employer(
            name=raw.name,
            name_norm=norm,
            gst=raw.gst,
            verified_at=verified_at,
        )
        session.add(employer)
        await session.flush()
        report.employers_inserted += 1
        _log.info("seed.employer.inserted", name=raw.name, id=str(employer.id))
        return employer.id
    # Update: gst is overwritten if JSON has a value; verified_at is set only
    # if currently NULL and JSON says verified=true (preserve original time).
    changed = False
    if raw.gst is not None and existing.gst != raw.gst:
        existing.gst = raw.gst
        changed = True
    if raw.verified and existing.verified_at is None:
        existing.verified_at = datetime.now(UTC)
        changed = True
    if changed:
        report.employers_updated += 1
        _log.info("seed.employer.updated", name=raw.name, id=str(existing.id))
    return existing.id


async def _upsert_job(
    session: AsyncSession,
    raw: JobInput,
    employer_id: uuid.UUID,
    report: SeedReport,
) -> None:
    title_lc = raw.title.strip().lower()
    existing = (
        (
            await session.execute(
                select(Job).where(
                    Job.employer_id == employer_id,
                    Job.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    match = next((j for j in existing if j.title.lower() == title_lc), None)
    posted_at = datetime.now(UTC) - timedelta(days=raw.posted_days_ago)
    status = JobStatus(raw.status)
    if match is None:
        job = Job(
            employer_id=employer_id,
            title=raw.title.strip(),
            description=raw.description,
            locations=list(raw.locations),
            min_exp_years=raw.min_exp_years,
            max_exp_years=raw.max_exp_years,
            ctc_min=raw.ctc_min,
            ctc_max=raw.ctc_max,
            status=status,
            posted_at=posted_at,
        )
        session.add(job)
        await session.flush()
        report.jobs_inserted += 1
        report.inserted_job_ids.append(job.id)
        _log.info(
            "seed.job.inserted",
            employer_id=str(employer_id),
            title=job.title,
            id=str(job.id),
        )
        return
    match.description = raw.description
    match.locations = list(raw.locations)
    match.min_exp_years = raw.min_exp_years
    match.max_exp_years = raw.max_exp_years
    match.ctc_min = raw.ctc_min
    match.ctc_max = raw.ctc_max
    match.status = status
    match.posted_at = posted_at
    report.jobs_updated += 1
    report.updated_job_ids.append(match.id)
    _log.info(
        "seed.job.updated",
        employer_id=str(employer_id),
        title=match.title,
        id=str(match.id),
    )


def _dispatch_embeds(job_ids: list[uuid.UUID]) -> None:
    """Fire ``embed_job.delay(...)`` for each job_id, fire-and-forget.

    Broker outage MUST NOT fail the seed — the rows are durable. The broad
    except + warning log mirrors the upload-route → parse-resume dispatch
    pattern in ``routes/resumes.py``. Don't tighten the except.
    """
    # Lazy import to avoid celery_app import at module load (keeps the CLI
    # invocable without Celery configured for dry-run / unit-test paths).
    from jobify.workers.tasks.embed_job import embed_job

    for jid in job_ids:
        try:
            embed_job.delay(str(jid))
        except Exception:
            _log.warning("embed.dispatch-failed", job_id=str(jid), exc_info=True)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="seed_jobs",
        description="Seed employers and jobs from a JSON fixture (idempotent).",
    )
    parser.add_argument(
        "--from",
        dest="path",
        type=Path,
        default=_DEFAULT_FIXTURE_PATH,
        help=f"Path to seed JSON. Default: {_DEFAULT_FIXTURE_PATH}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + validate the JSON, log what would change, do not write.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _log.info("seed.start", path=str(args.path), dry_run=args.dry_run)
    try:
        payload = _load_and_validate(args.path)
    except Exception as exc:  # validation/IO failures
        _log.error("seed.validation-failed", error=str(exc))
        return 2
    try:
        report = asyncio.run(_apply(payload, dry_run=args.dry_run))
    except Exception as exc:
        _log.error("seed.db-failed", error=str(exc))
        return 3
    _log.info("seed.complete", **report.as_log_kwargs())
    return 0


if __name__ == "__main__":
    sys.exit(main())
