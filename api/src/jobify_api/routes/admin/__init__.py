"""Admin moderation endpoints — /v1/admin/*.

Split by concern into sibling routers, combined here into one ``router`` so
``app_factory`` registration is unchanged:

- ``users``          — user suspend/unsuspend + the audit-log viewer.
- ``employers``      — employer verification review (verify / reject / list).
- ``match_feedback`` — Match QA: rated-matches list + relevance summary.

All routes require ADMIN role (``_require_admin`` after ``current_user``); see the
per-module docstrings and ``api/CLAUDE.md`` for the error-ladder + tri-state rules.
"""

from __future__ import annotations

from fastapi import APIRouter

from jobify_api.routes.admin import analytics, employers, match_feedback, users

router = APIRouter()
router.include_router(analytics.router)
router.include_router(users.router)
router.include_router(employers.router)
router.include_router(match_feedback.router)
