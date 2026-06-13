# `/v1/applicants/me/resumes` alias — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the path-param resume routes (`POST/GET /v1/applicants/{applicant_id}/resumes…`) with the spec-mandated authenticated alias `/v1/applicants/me/resumes`, resolving the applicant from the Bearer access JWT instead of the URL.

**Architecture:** Single route module changes (`api/src/kpa/routes/resumes.py`). A new private helper `_require_applicant(user, session)` resolves `current_user` to a live `Applicant` row, returning 403 `not_an_applicant` for recruiter/admin tokens and 500 `applicant_missing` if a role=applicant user has no applicants row (defense in depth — `AuthService._upsert_identity` always creates one on first sign-in). All integration tests that exercise resume endpoints are rewritten to attach a Bearer token. Three new tests cover the 401/403 surface that didn't exist pre-auth.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, PyJWT (HS256), pytest + httpx.AsyncClient, the existing `FakeGoogleIdTokenVerifier` test double from `tests/integration/conftest.py`.

**Source-of-truth spec:** `docs/superpowers/specs/2026-05-19-applicants-me-resumes-alias-design.md`.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `api/src/kpa/routes/resumes.py` | Modify | Drop path-param prefix; both handlers depend on `current_user`; new `_require_applicant` helper; delete unused `_load_live_applicant`. |
| `api/tests/integration/test_resumes_upload.py` | Rewrite | Existing 8 tests retargeted at `/me/resumes`. Adds a local `_signin_as_applicant` helper that returns `(applicant_id, access_token)`. |
| `api/tests/integration/test_dispatch_resilient.py` | Modify | One test retargeted at `/me/resumes`; manual user + token (no sign-in needed). |
| `api/tests/integration/test_parse_pipeline.py` | Modify | Two tests retargeted; the `pipeline_client` fixture must now set `KPA_JWT_SECRET`; helper `_make_applicant_direct` extended to return `(applicant_id, access_token)`. |
| `api/tests/integration/test_resumes_auth.py` | **Create** | Three new auth-surface tests: 401 missing-bearer (POST + GET), 403 recruiter (POST). |

No new source modules, no model changes, no migration.

---

## Background the engineer needs

- `current_user` (`api/src/kpa/auth/dependencies.py:33`) reads `Authorization: Bearer <jwt>`, decodes the HS256 token (issuer `kpa-api`), re-fetches the `User` row (so soft-deleted users get locked out within the access-TTL window), and returns it. On any failure it raises HTTPException(401, "missing_bearer_token" | "invalid_access_token" | "user_not_found").
- `mint_access_token(*, user_id, role, secret, ttl_seconds)` (`api/src/kpa/auth/tokens.py:35`) is the pure helper for tests that need to issue a JWT without going through the sign-in flow (used for the recruiter case — `AuthService._upsert_identity` hard-codes `role=APPLICANT`).
- The integration conftest already wires the `FakeGoogleIdTokenVerifier` into the app via `app.dependency_overrides[get_google_verifier]`. Calling `POST /v1/auth/oauth/google` with a token string that the fake's `.canned` dict knows returns a real access JWT minted by the real `AuthService`.
- `async_client` (the test fixture) shares the `session` fixture's DB connection via `app.dependency_overrides[get_session]`. Use it for any test that reads DB state with `session.execute(...)` AND hits the HTTP surface.
- The error middleware (`api/src/kpa/middleware/error_handler.py`) emits `application/problem+json` and copies `HTTPException.detail` into the JSON `detail` field. Tests can assert on `response.json()["detail"]`.

---

## Tasks

### Task 1: Create the feature branch

- [ ] **Step 1: Verify `main` is current and clean**

Run:
```bash
git status
git rev-parse --abbrev-ref HEAD
git log -1 --oneline
```
Expected: branch `main`, working tree clean (the only untracked items are `CLAUDE.md`, `docs/prd/`, and `docs/superpowers/specs/2026-05-19-applicants-me-resumes-alias-design.md`), HEAD at the post-PR-#6 merge commit (`1a13e37` or later).

- [ ] **Step 2: Create and check out the feature branch**

Run:
```bash
git checkout -b feat/p1.2-applicants-me-resumes-alias
```
Expected: `Switched to a new branch 'feat/p1.2-applicants-me-resumes-alias'`.

---

### Task 2: Refactor `routes/resumes.py` to use `current_user`

**Files:**
- Modify: `api/src/kpa/routes/resumes.py`

This is the only source change in the plan. We do it before touching tests so the integration suite goes red in a single, well-understood way (404s on `/v1/applicants/{uuid}/resumes`) that the test-rewrite tasks then fix.

- [ ] **Step 1: Replace the entire file contents**

Replace `api/src/kpa/routes/resumes.py` with:

```python
"""Resume upload + retrieval endpoints.

Both routes are nested under `/v1/applicants/me` and resolve the
authenticated applicant from the access JWT — never from the URL.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import current_user
from kpa.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole
from kpa.db.session import get_session
from kpa.integrations.storage import Storage, get_storage
from kpa.settings import Settings

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/applicants/me", tags=["resumes"])


# Content-Type → file extension. The original filename's extension is not
# trusted; we derive a safe one from the validated content-type.
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


class ResumeRead(BaseModel):
    """Response shape for resume metadata. Bytes are never returned here."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    applicant_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    parse_status: ResumeParseStatus
    created_at: datetime


async def _require_applicant(user: User, session: AsyncSession) -> Applicant:
    """Resolve the authenticated user to a live applicants row.

    Raises 403 not_an_applicant if user.role is not APPLICANT.
    Raises 500 applicant_missing if role=applicant but no row exists
    (theoretically unreachable; defense in depth against an auth
    auto-provisioning regression).
    """
    if user.role != UserRole.APPLICANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not_an_applicant",
        )
    applicant = (
        await session.execute(
            select(Applicant).where(
                Applicant.user_id == user.id,
                Applicant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if applicant is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="applicant_missing",
        )
    return applicant


@router.post(
    "/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    request: Request,
    file: UploadFile,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> Resume:
    settings: Settings = request.app.state.settings

    allowed = settings.allowed_resume_content_types
    if isinstance(allowed, str):  # defensive — should never happen after validation
        allowed = [allowed]

    if file.content_type is None or file.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"content_type {file.content_type!r} is not in the resume whitelist",
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds max_upload_bytes ({settings.max_upload_bytes})",
        )

    applicant = await _require_applicant(user, session)

    resume = Resume(
        applicant_id=applicant.id,
        original_filename=file.filename or "(unnamed)",
        content_type=file.content_type,
        size_bytes=len(content),
        storage_key="",  # set below once we know the resume id
        parse_status=ResumeParseStatus.PENDING,
    )
    session.add(resume)
    await session.flush()  # populates resume.id

    ext = _CONTENT_TYPE_TO_EXT[file.content_type]
    resume.storage_key = f"resumes/{resume.id}{ext}"

    await storage.save(key=resume.storage_key, content=content, content_type=file.content_type)
    await session.commit()

    # Dispatch async parse — broker outages MUST NOT fail the upload because
    # the resume row + file are already durable. Admin tooling can replay
    # pending rows after the broker recovers.
    #
    # Lazy import: kpa.workers.celery_app instantiates Settings() at module
    # level (needs KPA_REDIS_URL). Deferring the import to request time avoids
    # import-time failures in test collection where env vars aren't yet set.
    try:
        from kpa.workers.tasks.parse import parse_resume

        parse_resume.delay(str(resume.id))
    except Exception as exc:
        _log.warning(
            "dispatch.broker-unavailable",
            resume_id=str(resume.id),
            error=type(exc).__name__,
        )

    await session.refresh(resume)
    return resume


@router.get(
    "/resumes/{resume_id}",
    response_model=ResumeRead,
)
async def get_resume(
    resume_id: UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Resume:
    applicant = await _require_applicant(user, session)
    # Single JOIN'd query so all 404 cases (unknown resume id, resume
    # belongs to a different applicant) collapse to the same detail
    # message — see the commit that introduced uniform 404s for why.
    row = (
        await session.execute(
            select(Resume)
            .join(Applicant, Resume.applicant_id == Applicant.id)
            .where(
                Resume.id == resume_id,
                Resume.applicant_id == applicant.id,
                Resume.deleted_at.is_(None),
                Applicant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resume not found")
    return row
```

Notes for the engineer:
- Imports change: add `current_user` from `kpa.auth.dependencies`, add `User` and `UserRole` to the existing `kpa.db.models` import.
- Router prefix changes from `"/v1/applicants/{applicant_id}"` to `"/v1/applicants/me"`.
- Both handlers drop the `applicant_id: UUID` parameter and gain `user: User = Depends(current_user)`.
- `_load_live_applicant` is removed entirely (no remaining callers).
- The 401 path is **not** implemented here — `current_user` raises that directly.
- The 403 / 500 paths are implemented in `_require_applicant`.

- [ ] **Step 2: Run lint + mypy to catch obvious mistakes**

From `api/`:
```bash
uv run ruff check src/kpa/routes/resumes.py
uv run mypy
```
Expected: both clean. If mypy complains about an unused import (`UUID` is still used in `_CONTENT_TYPE_TO_EXT` typing and `ResumeRead`; double-check), fix.

- [ ] **Step 3: Commit the refactor**

```bash
git add api/src/kpa/routes/resumes.py
git commit -m "refactor(api): move resume routes to /v1/applicants/me + require auth

Spec: docs/superpowers/specs/2026-05-19-applicants-me-resumes-alias-design.md
The path-param routes were placeholders for the pre-auth era; this slice
makes the access JWT the only way to identify the uploading applicant.

- Router prefix: /v1/applicants/{applicant_id} -> /v1/applicants/me
- Both handlers depend on current_user; drop applicant_id path param
- New _require_applicant(user, session) helper: 403 not_an_applicant for
  recruiter/admin tokens, 500 applicant_missing as defense in depth
- _load_live_applicant deleted (no remaining callers)

Integration tests are intentionally red after this commit; the next two
commits retarget them at /me/resumes and add the new 401/403 coverage."
```

Existing integration tests are now red — that's expected; Tasks 3 and 4 fix them.

---

### Task 3: Add three new auth-surface tests

**Files:**
- Create: `api/tests/integration/test_resumes_auth.py`

These cover the surface that didn't exist before auth: 401 missing-bearer (POST + GET) and 403 recruiter (POST). Writing them in a dedicated file (rather than appending to `test_resumes_upload.py`) keeps the role-gate and Bearer-gate cases discoverable.

- [ ] **Step 1: Write the new test file**

```python
"""Auth-surface tests for /v1/applicants/me/resumes.

Covers 401 (missing/invalid Bearer) and 403 (wrong role) — the surface
that didn't exist when these routes took applicant_id from the URL.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import mint_access_token
from kpa.db.models import User, UserRole

pytestmark = pytest.mark.integration

_TINY_PDF = b"%PDF-1.4\n%minimal\n"
_JWT_SECRET = "x" * 32  # matches KPA_JWT_SECRET set by the integration fixtures


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
```

- [ ] **Step 2: Run the new tests**

From `api/`:
```bash
uv run pytest -v tests/integration/test_resumes_auth.py
```
Expected: 3 passed. If 401 tests fail, check that the route refactor in Task 2 was committed. If the recruiter test 500s, the most likely cause is `KPA_JWT_SECRET` mismatch — confirm `tests/integration/conftest.py` sets it to `"x" * 32` (line ~152 and ~195) and that `_JWT_SECRET` in this file matches.

- [ ] **Step 3: Commit the new tests**

```bash
git add api/tests/integration/test_resumes_auth.py
git commit -m "test(api): add 401/403 auth coverage for /me/resumes

- test_upload_missing_bearer_returns_401
- test_get_resume_missing_bearer_returns_401
- test_upload_recruiter_role_returns_403 (mints JWT directly because
  sign-in always provisions role=applicant)

Existing resume integration tests are still red against /me/resumes
and get retargeted in the next commit."
```

---

### Task 4: Rewrite `test_resumes_upload.py` for the `/me/resumes` path

**Files:**
- Rewrite: `api/tests/integration/test_resumes_upload.py`

All 8 existing tests get retargeted. The `_make_applicant` helper is replaced with `_signin_as_applicant` that returns `(applicant_id, access_token)` — going through the real sign-in flow keeps the auth boundary realistic. The two GET tests that previously varied the `applicant_id` in the URL are restructured: one queries a bogus resume id under the signed-in applicant, the other queries another applicant's resume id under user A's session.

- [ ] **Step 1: Replace the entire file with the rewritten suite**

```python
"""POST + GET /v1/applicants/me/resumes — upload + persistence (auth-required)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.google_verifier import GoogleClaims
from kpa.db.models import Resume, ResumeParseStatus

_TINY_PDF = b"%PDF-1.4\n%minimal\n"


def _claims(sub: str, email: str) -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=True,
        name=email.split("@", 1)[0].title(),
    )


async def _signin_as_applicant(
    client: httpx.AsyncClient,
    google_verifier,  # FakeGoogleIdTokenVerifier
    *,
    sub: str | None = None,
    email: str | None = None,
) -> tuple[str, str]:
    """Sign in via the fake Google verifier; return (applicant_id, access_token).

    Each call uses a unique sub/email by default so multiple applicants in
    one test don't collide on the partial-unique email index.
    """
    sub = sub or f"google-sub-{uuid.uuid4()}"
    email = email or f"applicant-{uuid.uuid4()}@example.com"
    token = f"tok-{uuid.uuid4()}"

    google_verifier.canned[token] = _claims(sub=sub, email=email)
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["user"]["applicant_id"], body["access_token"]


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.integration
async def test_upload_resume_happy_path(
    async_client: httpx.AsyncClient,
    google_verifier,
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    applicant_id, access = await _signin_as_applicant(async_client, google_verifier)

    response = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(access),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["applicant_id"] == applicant_id
    assert body["original_filename"] == "cv.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(_TINY_PDF)
    assert body["parse_status"] == "pending"

    resume_id = uuid.UUID(body["id"])
    row = (await session.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
    assert row.parse_status is ResumeParseStatus.PENDING

    on_disk = tmp_path / row.storage_key
    assert on_disk.is_file()
    assert on_disk.read_bytes() == _TINY_PDF


@pytest.mark.integration
async def test_upload_resume_rejects_disallowed_content_type(
    async_client: httpx.AsyncClient,
    google_verifier,
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    _applicant_id, access = await _signin_as_applicant(async_client, google_verifier)

    response = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=_auth(access),
    )

    assert response.status_code == 415
    # No row persisted, no file written.
    rows = (await session.execute(select(Resume))).all()
    assert rows == []
    assert not any(tmp_path.rglob("*"))


@pytest.mark.integration
async def test_upload_resume_rejects_oversized_payload(
    async_client: httpx.AsyncClient,
    google_verifier,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
    tmp_path: Path,
) -> None:
    """Use a low cap so we don't allocate real 10 MB blobs in tests."""
    # Sign in against the suite's default app first to get a token bound to a
    # real applicant row in `session`.
    _applicant_id, access = await _signin_as_applicant(async_client, google_verifier)

    # Re-create the app with a stricter KPA_MAX_UPLOAD_BYTES, sharing `session`
    # so the user we just signed in as is visible.
    monkeypatch.setenv("KPA_MAX_UPLOAD_BYTES", "16")  # 16 bytes
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:  # type: ignore[return]
        yield session

    app.dependency_overrides[get_session] = _shared_session

    payload = b"x" * 32  # over 16 bytes

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        response = await c.post(
            "/v1/applicants/me/resumes",
            files={"file": ("cv.pdf", payload, "application/pdf")},
            headers=_auth(access),
        )

    assert response.status_code == 413
    rows = (await session.execute(select(Resume))).all()
    assert rows == []


@pytest.mark.integration
async def test_get_resume_returns_metadata(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    _applicant_id, access = await _signin_as_applicant(async_client, google_verifier)
    post = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(access),
    )
    assert post.status_code == 201, post.text
    posted = post.json()

    response = await async_client.get(
        f"/v1/applicants/me/resumes/{posted['id']}",
        headers=_auth(access),
    )

    assert response.status_code == 200
    assert response.json() == posted


@pytest.mark.integration
async def test_get_resume_unknown_id_returns_404(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    _applicant_id, access = await _signin_as_applicant(async_client, google_verifier)
    bogus = uuid.uuid4()

    response = await async_client.get(
        f"/v1/applicants/me/resumes/{bogus}",
        headers=_auth(access),
    )

    assert response.status_code == 404


@pytest.mark.integration
async def test_get_resume_belonging_to_other_user_returns_404(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    """A resume id owned by user B must 404 when user A asks for it.

    Returning 403 would leak the existence of the resume to an unauthorized
    caller; 404 keeps the surface flat.
    """
    _owner_id, owner_access = await _signin_as_applicant(async_client, google_verifier)
    _intruder_id, intruder_access = await _signin_as_applicant(async_client, google_verifier)

    post = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(owner_access),
    )
    posted = post.json()

    response = await async_client.get(
        f"/v1/applicants/me/resumes/{posted['id']}",
        headers=_auth(intruder_access),
    )

    assert response.status_code == 404


@pytest.mark.integration
async def test_get_resume_404_detail_is_uniform(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    """Both 404 cases (unknown id; another user's id) return the same detail.

    Distinguishing them would leak which case the caller hit — i.e., whether
    a resume id exists at all.
    """
    _user_a_id, access_a = await _signin_as_applicant(async_client, google_verifier)
    _user_b_id, access_b = await _signin_as_applicant(async_client, google_verifier)

    # User B uploads a resume; user A queries that real id and a bogus one.
    post = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(access_b),
    )
    real_resume_id = post.json()["id"]
    bogus = uuid.uuid4()

    cases = [
        f"/v1/applicants/me/resumes/{bogus}",
        f"/v1/applicants/me/resumes/{real_resume_id}",
    ]
    details = []
    for url in cases:
        response = await async_client.get(url, headers=_auth(access_a))
        assert response.status_code == 404, url
        details.append(response.json().get("detail"))

    assert len(set(details)) == 1, f"detail messages leak info: {details}"
```

Notes for the engineer:
- The original `test_upload_resume_unknown_applicant_returns_404` is **deleted** — there is no longer an applicant id in the URL to be "unknown." The 401 path (no token) and 403 path (wrong role) cover the equivalent "you can't upload as someone else" intent and live in `test_resumes_auth.py`.
- The original `test_get_resume_from_wrong_applicant_returns_404` becomes `test_get_resume_belonging_to_other_user_returns_404` — same invariant, different setup.
- `test_get_resume_404_detail_is_uniform` drops from 3 cases to 2 — the "wrong applicant in path" case no longer exists.
- Net test count for this file: 7 (was 8). The auth file adds 3, so the suite-wide net is +2 tests, not +3 as the spec estimated. That's fine — the spec said "estimated."

- [ ] **Step 2: Run the rewritten file**

From `api/`:
```bash
uv run pytest -v tests/integration/test_resumes_upload.py
```
Expected: 7 passed.

If `test_upload_resume_rejects_oversized_payload` fails with 401, check that the second `AsyncClient` in that test sends the Authorization header — it shares the same `access` variable but uses its own client instance.

- [ ] **Step 3: Hold the commit until Task 5 + Task 6**

Don't commit yet — the dispatch-resilient and parse-pipeline tests still target the old path. Commit them together.

---

### Task 5: Update `test_dispatch_resilient.py`

**Files:**
- Modify: `api/tests/integration/test_dispatch_resilient.py`

Single test, single URL change, plus the addition of an access token. The existing test creates a User + Applicant directly via `session` (no sign-in), so the simplest auth approach is to mint a token directly with `mint_access_token`.

- [ ] **Step 1: Replace the test file contents**

```python
"""Integration test for upload-route resilience when the Celery broker is down."""

from __future__ import annotations

import io

import pytest
from fpdf import FPDF
from sqlalchemy import select

from kpa.auth.tokens import mint_access_token
from kpa.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches KPA_JWT_SECRET in the integration fixtures


def _tiny_pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="resume content")
    return bytes(pdf.output())


async def _make_applicant_with_token(session) -> tuple[str, str]:
    """Return (applicant_id, access_token) for a fresh applicant."""
    user = User(email="dispatch@ex.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Dispatch Test")
    session.add(applicant)
    await session.commit()
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=_JWT_SECRET,
        ttl_seconds=600,
    )
    return str(applicant.id), token


async def test_upload_returns_201_even_if_broker_dispatch_raises(
    async_client,
    session,
    monkeypatch,
) -> None:
    """If parse_resume.delay() raises (broker down), upload still returns 201
    and the row exists with parse_status=pending."""
    from kpa.workers.tasks import parse as parse_module

    def _raise_broker_down(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(parse_module.parse_resume, "delay", _raise_broker_down)

    applicant_id, access = await _make_applicant_with_token(session)
    pdf = _tiny_pdf()

    resp = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        headers={"Authorization": f"Bearer {access}"},
    )

    assert resp.status_code == 201
    row = (
        await session.execute(select(Resume).where(Resume.applicant_id.in_([applicant_id])))
    ).scalar_one()
    assert row.parse_status == ResumeParseStatus.PENDING
```

- [ ] **Step 2: Run the test**

From `api/`:
```bash
uv run pytest -v tests/integration/test_dispatch_resilient.py
```
Expected: 1 passed.

---

### Task 6: Update `test_parse_pipeline.py`

**Files:**
- Modify: `api/tests/integration/test_parse_pipeline.py`

This file uses a separate `pipeline_client` fixture that deliberately does NOT override `get_session` (so the upload route's commit reaches the real DB and the Celery eager worker can read it). Auth cannot be bypassed via `dependency_overrides[current_user]` here — the test must mint a real JWT.

The fixture currently doesn't set `KPA_JWT_SECRET`, which means the app's `Settings` validation will fail on startup once auth is required. We add it.

- [ ] **Step 1: Edit `pipeline_client` to set the JWT secret**

In `api/tests/integration/test_parse_pipeline.py`, find the `pipeline_client` fixture (currently around lines 38–80) and add a `KPA_JWT_SECRET` `monkeypatch.setenv` call alongside the existing env-var setup.

Replace:
```python
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", migrated_db)
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))
```

With:
```python
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", migrated_db)
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
```

- [ ] **Step 2: Extend `_make_applicant_direct` to also return a token**

Find the existing `_make_applicant_direct` helper (currently around lines 83–99). Replace its body:

```python
async def _make_applicant_direct(db_url: str, *, email: str) -> tuple[str, str]:
    """Create user + applicant rows via a committed transaction.

    Returns (applicant_id, access_token). The token is minted directly using
    the same secret that pipeline_client sets via KPA_JWT_SECRET, so the
    app under test will accept it.
    """
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            user = User(email=email, role=UserRole.APPLICANT)
            s.add(user)
            await s.flush()
            applicant = Applicant(user_id=user.id, full_name="Pipeline Test")
            s.add(applicant)
            await s.commit()
            token = mint_access_token(
                user_id=user.id,
                role=user.role.value,
                secret="x" * 32,
                ttl_seconds=600,
            )
            return str(applicant.id), token
    finally:
        await engine.dispose()
```

And add the import at the top of the file (alongside the other `kpa.*` imports):

```python
from kpa.auth.tokens import mint_access_token
```

- [ ] **Step 3: Update `test_upload_then_parse_populates_parsed_json`**

In that test (currently around line 129), replace:

```python
    applicant_id = await _make_applicant_direct(migrated_db, email=email)
    pdf = _tiny_pdf_with(
        [
            "John Doe",
            "Email: john.doe@example.com",
            "Phone: +91-98765-43210",
            "Skills: Python, FastAPI, Postgres",
        ]
    )

    try:
        resp = await pipeline_client.post(
            f"/v1/applicants/{applicant_id}/resumes",
            files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        )
```

with:

```python
    applicant_id, access = await _make_applicant_direct(migrated_db, email=email)
    pdf = _tiny_pdf_with(
        [
            "John Doe",
            "Email: john.doe@example.com",
            "Phone: +91-98765-43210",
            "Skills: Python, FastAPI, Postgres",
        ]
    )

    try:
        resp = await pipeline_client.post(
            "/v1/applicants/me/resumes",
            files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
            headers={"Authorization": f"Bearer {access}"},
        )
```

The `applicant_id` local is kept because the test's `_cleanup` call (or assertions, if any) downstream may reference it. Don't delete it.

- [ ] **Step 4: Update `test_upload_of_unsupported_blob_marks_failed`**

In that test (currently around line 168), replace:

```python
    applicant_id = await _make_applicant_direct(migrated_db, email=email)
    junk = b"\x00" * 200

    try:
        resp = await pipeline_client.post(
            f"/v1/applicants/{applicant_id}/resumes",
            files={
                "file": (
                    "cv.docx",
                    io.BytesIO(junk),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
```

with:

```python
    applicant_id, access = await _make_applicant_direct(migrated_db, email=email)
    junk = b"\x00" * 200

    try:
        resp = await pipeline_client.post(
            "/v1/applicants/me/resumes",
            files={
                "file": (
                    "cv.docx",
                    io.BytesIO(junk),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"Authorization": f"Bearer {access}"},
        )
```

Same rule — keep `applicant_id` bound for downstream use.

- [ ] **Step 5: Run the parse-pipeline tests**

From `api/`:
```bash
uv run pytest -v tests/integration/test_parse_pipeline.py
```
Expected: 2 passed. Requires a running local Postgres + a running Redis (the pipeline test exercises eager Celery, which still touches the broker URL during init — verify `redis://localhost:6379/0` is up).

If only one test passes and the other times out: the second test sends junk bytes as a `.docx`, which the parser flags as failed. The 401 path is the most likely failure mode if the Authorization header is missing on one of the two calls — re-check both.

---

### Task 7: Run the full suite + lint + types

- [ ] **Step 1: Full pytest**

From `api/`:
```bash
uv run pytest -v
```
Expected: all integration + unit tests pass. The unit tests don't touch HTTP and shouldn't be affected by this change.

If a test outside the four files modified by this plan fails, stop and investigate — the refactor should not have leaked anywhere else (there are no other importers of `routes.resumes.router` outside `app_factory.py`).

- [ ] **Step 2: Ruff lint + format**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```
Expected: both clean. If `ruff format --check` complains, run `uv run ruff format src/ tests/` and re-stage the changes.

- [ ] **Step 3: Mypy**

```bash
uv run mypy
```
Expected: `Success: no issues found in N source files`.

- [ ] **Step 4: Commit the test changes**

```bash
git add api/tests/integration/test_resumes_upload.py \
        api/tests/integration/test_dispatch_resilient.py \
        api/tests/integration/test_parse_pipeline.py
git commit -m "test(api): retarget resume tests at /me/resumes auth path

- test_resumes_upload.py: 7 tests rewritten to sign in via the fake
  Google verifier and attach Bearer tokens; the unknown-applicant test
  is dropped (no applicant id in URL anymore); the wrong-applicant case
  becomes 'another user's resume id'
- test_dispatch_resilient.py: mints an access token directly via
  mint_access_token after creating the user manually
- test_parse_pipeline.py: pipeline_client fixture now sets KPA_JWT_SECRET;
  _make_applicant_direct returns (applicant_id, access_token); both tests
  attach the Bearer token"
```

---

### Task 8: Open the PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/p1.2-applicants-me-resumes-alias
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "P1.2: /v1/applicants/me/resumes alias + auth on resume routes" --body "$(cat <<'EOF'
## Summary
- Replace path-param resume routes (\`/v1/applicants/{applicant_id}/resumes…\`) with the spec-mandated authenticated alias \`/v1/applicants/me/resumes\`, resolving the applicant from the access JWT
- New \`_require_applicant(user, session)\` helper returns 403 \`not_an_applicant\` for recruiter/admin tokens and 500 \`applicant_missing\` as defense in depth
- Adds 401 (missing-bearer) and 403 (wrong-role) coverage that didn't exist pre-auth

Spec: \`docs/superpowers/specs/2026-05-19-applicants-me-resumes-alias-design.md\`

## Test plan
- [ ] \`uv run pytest -v tests/integration/test_resumes_auth.py\` — 3 passed
- [ ] \`uv run pytest -v tests/integration/test_resumes_upload.py\` — 7 passed
- [ ] \`uv run pytest -v tests/integration/test_dispatch_resilient.py\` — 1 passed
- [ ] \`uv run pytest -v tests/integration/test_parse_pipeline.py\` — 2 passed (requires local Redis)
- [ ] \`uv run pytest -v\` full suite — all passed
- [ ] \`uv run ruff check src/ tests/\` + \`uv run mypy\` — both clean

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: a PR URL on stdout. Paste it back to the user.

---

## Out of scope (intentional)

Carried over from the spec:

- **LIST endpoint** (`GET /me/resumes`) — separate plan once a UI needs it.
- **PATCH endpoint** (`PATCH /me/resumes/{id}`) — lands with the S3 / presigned-URL plan.
- **`require_role()` helper** — role check stays inlined in `_require_applicant` until a second role-gated endpoint exists.
- **Audit log entry** on resume upload — separate plan (spec §9.2 DPDP audit_logs).
- **Test for the 500 `applicant_missing` case** — the spec calls it defense in depth and "theoretically unreachable"; the guard is exercised by code review, not tests.

---

## Self-review notes (for the executor)

Three things to double-check before pushing:

1. **No stale references to `applicant_id` in URLs.** Run `grep -rn 'applicants/{applicant_id\|f\"/v1/applicants/[^m]' api/` — should return zero matches under `api/src/` and `api/tests/` when this plan is complete.
2. **`_load_live_applicant` is gone.** Run `grep -rn '_load_live_applicant' api/` — zero matches.
3. **The 401 `missing_bearer_token` slug matches `current_user`'s wording exactly.** It comes from `api/src/kpa/auth/dependencies.py:28`. If that ever changes, the tests in `test_resumes_auth.py` and any other file asserting on the slug will fail loudly — by design.
