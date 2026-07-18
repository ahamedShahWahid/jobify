"""Admin moderation endpoints — /v1/admin/*.

Split by concern into two sibling routers, combined here into one ``router`` so
``app_factory`` registration is unchanged:

- ``users``     — user suspend/unsuspend + the audit-log viewer.
- ``employers`` — employer verification review (verify / reject / list).

All routes require ADMIN role (``_require_admin`` after ``current_user``); see the
per-module docstrings and ``api/CLAUDE.md`` for the error-ladder + tri-state rules.
"""

from __future__ import annotations

from fastapi import APIRouter

from jobify_api.routes.admin import analytics, employers, users

router = APIRouter()
router.include_router(analytics.router)
router.include_router(users.router)
router.include_router(employers.router)
