"""Auth-surface tests for /v1/applicants/me/resumes.

Covers 401 (missing/invalid Bearer) and 403 (wrong role) — the surface
that didn't exist when these routes took applicant_id from the URL.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.tokens import mint_access_token
from jobify.db.models import User, UserRole

pytestmark = pytest.mark.integration

_TINY_PDF = b"%PDF-1.4\n%minimal\n"
_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by the integration fixtures


async def test_upload_missing_bearer_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    response = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["detail"] == "missing_bearer_token"


async def test_get_resume_missing_bearer_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    bogus = uuid.uuid4()
    response = await async_client.get(f"/v1/applicants/me/resumes/{bogus}")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing_bearer_token"


async def test_upload_recruiter_role_returns_403(
    async_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    """Recruiters/admins must hit a 403 before any DB work for an applicant row."""
    recruiter = User(
        email=f"recruiter-{uuid.uuid4()}@example.com",
        role=UserRole.RECRUITER,
    )
    session.add(recruiter)
    await session.flush()  # populate recruiter.id

    # Mint a real access token directly — the sign-in flow always creates
    # role=APPLICANT users, so we bypass it for this case.
    access = mint_access_token(
        user_id=recruiter.id,
        role=recruiter.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )

    response = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "not_an_applicant"


async def test_get_resume_recruiter_role_returns_403(
    async_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    """GET also gates on role — catches a refactor that wraps POST and GET differently."""
    recruiter = User(
        email=f"recruiter-{uuid.uuid4()}@example.com",
        role=UserRole.RECRUITER,
    )
    session.add(recruiter)
    await session.flush()

    access = mint_access_token(
        user_id=recruiter.id,
        role=recruiter.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )

    response = await async_client.get(
        f"/v1/applicants/me/resumes/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "not_an_applicant"


async def test_upload_applicant_role_without_applicant_row_returns_500(
    async_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    """The 'theoretically unreachable' applicant_missing branch.

    Pins the spec-defined slug. If `AuthService._upsert_identity` ever
    regresses and creates an APPLICANT user without an applicants row,
    or if an admin tool soft-deletes the row, this test fails loudly.
    """
    orphan = User(
        email=f"orphan-{uuid.uuid4()}@example.com",
        role=UserRole.APPLICANT,
    )
    session.add(orphan)
    await session.flush()

    access = mint_access_token(
        user_id=orphan.id,
        role=orphan.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )

    response = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "applicant_missing"
