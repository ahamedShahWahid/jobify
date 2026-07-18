"""Transactional recruiter job commands independent of HTTP schemas."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Employer, EmployerUser, Job, JobStatus
from jobify.outbox import enqueue_task

_EMBED_TRIGGERING_FIELDS = frozenset(
    {
        "title",
        "description",
        "locations",
        "min_exp_years",
        "max_exp_years",
        "ctc_min",
        "ctc_max",
    }
)


class RecruiterJobError(Exception):
    def __init__(self, detail: str, *, status_code: int = 404) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


async def _employer_for_job(session: AsyncSession, job: Job) -> Employer:
    employer = await session.scalar(select(Employer).where(Employer.id == job.employer_id))
    if employer is None:  # pragma: no cover - protected by the FK
        raise RecruiterJobError("employer_missing", status_code=500)
    return employer


async def load_recruiter_job(
    session: AsyncSession, *, job_id: uuid.UUID, recruiter_user_id: uuid.UUID
) -> Job:
    job = (
        await session.execute(
            select(Job)
            .join(EmployerUser, EmployerUser.employer_id == Job.employer_id)
            .where(
                Job.id == job_id,
                Job.deleted_at.is_(None),
                EmployerUser.user_id == recruiter_user_id,
                EmployerUser.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise RecruiterJobError("not found")
    return job


async def create_recruiter_job(
    session: AsyncSession, *, employer_id: uuid.UUID, values: Mapping[str, Any]
) -> tuple[Job, Employer]:
    fields = dict(values)
    fields["status"] = JobStatus(fields.get("status", JobStatus.OPEN))
    job = Job(employer_id=employer_id, **fields)
    session.add(job)
    await session.flush()
    enqueue_task(session, "jobify.embed_job", str(job.id))
    await session.commit()
    await session.refresh(job)
    return job, await _employer_for_job(session, job)


async def patch_recruiter_job(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    recruiter_user_id: uuid.UUID,
    values: Mapping[str, Any],
) -> tuple[Job, Employer]:
    job = await load_recruiter_job(session, job_id=job_id, recruiter_user_id=recruiter_user_id)
    fields = dict(values)
    min_exp_years = fields.get("min_exp_years", job.min_exp_years)
    max_exp_years = fields.get("max_exp_years", job.max_exp_years)
    if max_exp_years < min_exp_years:
        raise RecruiterJobError("max_exp_years must be >= min_exp_years", status_code=422)
    ctc_min = fields.get("ctc_min", job.ctc_min)
    ctc_max = fields.get("ctc_max", job.ctc_max)
    if ctc_min is not None and ctc_max is not None and ctc_max < ctc_min:
        raise RecruiterJobError("ctc_max must be >= ctc_min", status_code=422)
    for key, value in fields.items():
        setattr(job, key, JobStatus(value) if key == "status" else value)
    if _EMBED_TRIGGERING_FIELDS & fields.keys():
        enqueue_task(session, "jobify.embed_job", str(job.id))
    await session.commit()
    await session.refresh(job)
    return job, await _employer_for_job(session, job)


async def delete_recruiter_job(
    session: AsyncSession, *, job_id: uuid.UUID, recruiter_user_id: uuid.UUID
) -> None:
    job = await load_recruiter_job(session, job_id=job_id, recruiter_user_id=recruiter_user_id)
    job.deleted_at = func.now()
    await session.commit()
