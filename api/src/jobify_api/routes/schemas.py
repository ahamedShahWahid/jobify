"""Shared Pydantic response shapes for the job/feed family of routes.

These previously lived at the top of ``routes/feed.py`` (before its imports,
with ``noqa: E402``) purely to dodge an import cycle — feed, jobs,
applications and saved_jobs all need ``JobRead``/``EmployerRead``. Hosting
them in a leaf module removes the cycle and the split-import hack.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from jobify.db.models import Employer, Job


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    total_score: float
    vector_score: float
    structured_score: float
    # DB column is score_components; wire shape is components (per spec §P2.3).
    components: dict[str, float] = Field(validation_alias="score_components")
    surfaced_at: datetime | None
    explanation: dict[str, str] | None
    # The CURRENT applicant's rating on this match; None = unrated. Populated
    # by /v1/feed (only "up"/None survive there — "down" is excluded) and
    # /v1/jobs/{id} (any value). Absent from any recruiter/admin reuse.
    my_feedback: Literal["up", "down"] | None = None


class EmployerRead(BaseModel):
    """Wire shape: a verified bool, not the underlying verified_at timestamp."""

    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    name: str
    verified: bool


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    locations: list[str]
    min_exp_years: int
    max_exp_years: int
    ctc_min: float | None
    ctc_max: float | None
    # StrEnum → serializes as its string value ("open"/"closed"). The web/mobile
    # client uses this to render closed-role state on the saved list.
    status: str
    posted_at: datetime
    employer_verified: bool

    @classmethod
    def from_job_and_employer(
        cls,
        job: Job,
        employer: Employer,
    ) -> JobRead:
        """Build a JobRead from a Job ORM row and its associated Employer row.

        Single construction point so every caller sets employer_verified
        consistently. The field is required (no default) to force all future
        callers through here.
        """
        return cls.model_validate(
            {
                "id": job.id,
                "title": job.title,
                "description": job.description,
                "locations": job.locations,
                "min_exp_years": job.min_exp_years,
                "max_exp_years": job.max_exp_years,
                "ctc_min": float(job.ctc_min) if job.ctc_min is not None else None,
                "ctc_max": float(job.ctc_max) if job.ctc_max is not None else None,
                "status": job.status.value,
                "posted_at": job.posted_at,
                "employer_verified": employer.verified_at is not None,
            }
        )


class FeedItemRead(BaseModel):
    match: MatchRead
    job: JobRead
    employer: EmployerRead


class FeedResponse(BaseModel):
    items: list[FeedItemRead]
    next_cursor: str | None


class JobDetailApplicationRead(BaseModel):
    """Slim Application shape for the JobDetailResponse.

    Mirrors the fields of ``routes/applications.py::ApplicationRead`` but
    lives here so jobs.py doesn't import from applications.py.
    """

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    status: str  # "applied" | "withdrawn"
    stage: str  # recruiter pipeline: applied|shortlisted|interview|offer|hired|rejected
    source: str
    created_at: datetime
    updated_at: datetime


class JobDetailSavedJobRead(BaseModel):
    """Slim SavedJob shape for the JobDetailResponse.

    Mirrors ``routes/saved_jobs.py::SavedJobRead`` — same field set the
    Flutter ``SavedJobDto`` reads (it ignores ``updated_at`` but the
    canonical Read includes it, so we match for consistency).
    """

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class JobDetailResponse(BaseModel):
    job: JobRead
    employer: EmployerRead
    match: MatchRead | None
    application: JobDetailApplicationRead | None
    saved_job: JobDetailSavedJobRead | None
