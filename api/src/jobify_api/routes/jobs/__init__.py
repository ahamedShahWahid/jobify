"""Job routes (/v1/jobs*).

Split by audience into two sibling routers, combined here into one ``router`` so
``app_factory`` registration is unchanged:

- ``recruiter`` — list-my-jobs + job CRUD + the per-job applicant list.
- ``applicant`` — GET /v1/jobs/{job_id} (single job + match for the caller).

ORDER MATTERS: ``recruiter`` is included FIRST so its literal ``GET /v1/jobs/me``
is matched before ``applicant``'s ``GET /v1/jobs/{job_id}`` (FastAPI/Starlette
match in registration order; otherwise "me" is read as a failing UUID path-param).
"""

from __future__ import annotations

from fastapi import APIRouter

from jobify_api.routes.jobs import applicant, recruiter

router = APIRouter()
router.include_router(recruiter.router)
router.include_router(applicant.router)
