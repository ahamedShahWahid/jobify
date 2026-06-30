"""Recruiter identity + employer self-service routes (/v1/employers*).

Split by concern into two sibling routers, combined here into one ``router`` so
``app_factory`` registration is unchanged:

- ``core`` — POST /v1/employers (the sole role-elevation path) + GET /v1/employers/me.
- ``team`` — member + invite management under /v1/employers/{employer_id}/* (R4).

``EmployerCreate`` / ``_normalize_name`` are re-exported because they're imported
directly by ``tests/unit/test_employer_validators.py``.
"""

from __future__ import annotations

from fastapi import APIRouter

from jobify_api.routes.employers import core, team
from jobify_api.routes.employers.core import EmployerCreate, _normalize_name

router = APIRouter()
router.include_router(core.router)
router.include_router(team.router)

__all__ = ["EmployerCreate", "_normalize_name", "router"]
