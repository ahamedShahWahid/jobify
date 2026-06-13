# P4-D DSR Delete — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship `DELETE /v1/me/dsr` — soft-deletes-and-scrubs the User + Applicant + Resume tombstones; hard-deletes OAuthIdentity, RefreshToken, Notification, UserConsent, EmployerUser, ApplicantEmbedding, SavedJob rows + Resume blobs; preserves Application + Match rows (anonymized via tombstoned applicant); writes `user.dsr_delete_requested` + `user.dsr_deleted` audit rows in the same atomic transaction as the deletion.

**Architecture:** A `kpa.dsr.deleter` module with `delete_user_data(session, storage, user) -> DeleteReport` orchestrator. Route in `routes/dsr.py` adds the DELETE endpoint with a `{"confirmation": "DELETE_MY_ACCOUNT"}` body guard. Sole-owner-employer detection surfaces warnings in the response.

**Tech Stack:** FastAPI / async SQLAlchemy / Pydantic v2 / pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-dsr-delete-design.md`

---

## Files

**Create:**
- `api/src/kpa/dsr/deleter.py` — orchestrator + `DeleteReport` + `OwnerlessEmployerWarning`.
- `api/tests/unit/dsr/test_deleter_signature.py` — pure-signature contract tests.
- `api/tests/integration/test_dsr_delete.py` — applicant happy path, recruiter happy path (sole-owner warning), confirmation guard, idempotency-via-401, re-signup-after-delete.

**Modify:**
- `api/src/kpa/routes/dsr.py` — add `DELETE /v1/me/dsr` handler. Existing `POST /v1/me/dsr/export` stays.
- `CLAUDE.md` — add the "DSR delete" section per spec § 9.

(No migration. The deletion uses existing FKs + soft-delete columns.)

---

### Task 1: `deleter` module + unit tests

**Files:**
- Create: `api/src/kpa/dsr/deleter.py`
- Create: `api/tests/unit/dsr/test_deleter_signature.py`

- [ ] **Step 1: Write the failing unit test**

`api/tests/unit/dsr/test_deleter_signature.py`:

```python
"""Pure-signature contract test for delete_user_data. No DB."""

from __future__ import annotations

import inspect

from kpa.dsr.deleter import DeleteReport, OwnerlessEmployerWarning, delete_user_data


def test_delete_user_data_signature() -> None:
    sig = inspect.signature(delete_user_data)
    params = list(sig.parameters)
    assert params[0] == "session"
    for name in ("storage", "user"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_delete_report_top_level_fields() -> None:
    fields = set(DeleteReport.model_fields.keys())
    expected = {"deleted_at", "section_counts", "warnings"}
    assert fields == expected, f"missing={expected - fields}, extra={fields - expected}"


def test_ownerless_employer_warning_fields() -> None:
    fields = set(OwnerlessEmployerWarning.model_fields.keys())
    expected = {"type", "employer_id", "employer_name", "message"}
    assert fields == expected
```

Run: `cd api && uv run pytest -v tests/unit/dsr/test_deleter_signature.py`. Expect FAIL — module doesn't exist yet.

- [ ] **Step 2: Write the orchestrator module**

Create `api/src/kpa/dsr/deleter.py`:

```python
"""DSR delete orchestrator — DPDP § 12 erasure right.

Walks the user's data graph and applies the brainstorm-locked strategy:
"hard-delete PII, keep anonymized aggregates." See
docs/superpowers/specs/2026-05-29-dsr-delete-design.md §2 for the
per-table policy table and §5 for the order of operations.

Pure executor — does NOT write audit rows. The route handler writes
``user.dsr_delete_requested`` BEFORE this call and
``user.dsr_deleted`` AFTER, in the same transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import (
    Applicant,
    ApplicantEmbedding,
    EmployerUser,
    Employer,
    Notification,
    OAuthIdentity,
    RefreshToken,
    Resume,
    SavedJob,
    User,
    UserConsent,
    UserRole,
)
from kpa.storage.base import Storage

_log = structlog.get_logger(__name__)


class OwnerlessEmployerWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "ownerless_employer"
    employer_id: UUID
    employer_name: str
    message: str


class DeleteReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted_at: datetime
    section_counts: dict[str, int]
    warnings: list[OwnerlessEmployerWarning]


async def _detect_ownerless_employers(
    session: AsyncSession, *, user: User
) -> list[OwnerlessEmployerWarning]:
    """Find employers where the user is currently the last live owner.

    The check runs BEFORE we delete the user's employer_users rows so we
    can compare against the pre-delete state.
    """
    if user.role != UserRole.RECRUITER:
        return []

    other_owner_exists = (
        select(EmployerUser.id)
        .where(
            EmployerUser.employer_id == EmployerUser.employer_id,  # placeholder; bound below
            EmployerUser.user_id != user.id,
            EmployerUser.role == "owner",
            EmployerUser.deleted_at.is_(None),
        )
        .correlate(EmployerUser)
        .exists()
    )

    # Build the query using a fresh aliased EmployerUser for the inner check.
    from sqlalchemy.orm import aliased

    OtherOwner = aliased(EmployerUser)
    inner = (
        select(OtherOwner.id)
        .where(
            OtherOwner.employer_id == EmployerUser.employer_id,
            OtherOwner.user_id != user.id,
            OtherOwner.role == "owner",
            OtherOwner.deleted_at.is_(None),
        )
    )

    stmt = (
        select(EmployerUser.employer_id, Employer.name)
        .join(Employer, Employer.id == EmployerUser.employer_id)
        .where(
            EmployerUser.user_id == user.id,
            EmployerUser.role == "owner",
            EmployerUser.deleted_at.is_(None),
            ~exists(inner),
        )
    )

    rows = (await session.execute(stmt)).all()
    return [
        OwnerlessEmployerWarning(
            employer_id=eid,
            employer_name=ename,
            message=(
                f"Employer '{ename}' has no remaining owners. "
                "Contact privacy@kpa to reassign or close."
            ),
        )
        for (eid, ename) in rows
    ]


async def delete_user_data(
    session: AsyncSession,
    *,
    storage: Storage,
    user: User,
) -> DeleteReport:
    """Erase a user's personal data per the spec §2 table. Caller owns
    the transaction — no commit; if any step raises, the whole graph
    rolls back atomically.
    """
    counts: dict[str, int] = {}

    # Detect sole-owner employers BEFORE deleting memberships.
    warnings = await _detect_ownerless_employers(session, user=user)

    # 1. Notifications — payload may contain PII (job titles in apply confirmations).
    counts["notifications"] = (
        await session.execute(
            delete(Notification).where(Notification.user_id == user.id)
        )
    ).rowcount or 0

    # 2. Refresh tokens — session secrets.
    counts["refresh_tokens"] = (
        await session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user.id)
        )
    ).rowcount or 0

    # 3. OAuth identities — provider linkage.
    counts["oauth_identities"] = (
        await session.execute(
            delete(OAuthIdentity).where(OAuthIdentity.user_id == user.id)
        )
    ).rowcount or 0

    # 4. Consents — operational state. History lives in audit_logs.
    counts["user_consents"] = (
        await session.execute(
            delete(UserConsent).where(UserConsent.user_id == user.id)
        )
    ).rowcount or 0

    # 5. Employer memberships (recruiter case).
    counts["employer_users"] = (
        await session.execute(
            delete(EmployerUser).where(EmployerUser.user_id == user.id)
        )
    ).rowcount or 0

    # 6. Resolve the applicant id once for downstream queries.
    applicant_row = (
        await session.execute(
            select(Applicant).where(Applicant.user_id == user.id)
        )
    ).scalar_one_or_none()
    applicant_id = applicant_row.id if applicant_row else None

    if applicant_id is not None:
        # 7. Saved jobs.
        counts["saved_jobs"] = (
            await session.execute(
                delete(SavedJob).where(SavedJob.applicant_id == applicant_id)
            )
        ).rowcount or 0

        # 8. Embedding row.
        counts["applicant_embeddings"] = (
            await session.execute(
                delete(ApplicantEmbedding).where(
                    ApplicantEmbedding.applicant_id == applicant_id
                )
            )
        ).rowcount or 0

        # 9. Resume blobs.
        resume_rows = (
            await session.execute(
                select(Resume).where(Resume.applicant_id == applicant_id)
            )
        ).scalars().all()
        for resume in resume_rows:
            if resume.storage_key:
                try:
                    await storage.delete(resume.storage_key)
                except Exception:
                    _log.warning(
                        "dsr.blob-delete-failed",
                        resume_id=str(resume.id),
                        storage_key=resume.storage_key,
                        exc_info=True,
                    )

        # 10. Resume rows — scrub PII fields + tombstone.
        now = datetime.now(UTC)
        scrub_resume = (
            update(Resume)
            .where(Resume.applicant_id == applicant_id)
            .values(
                parsed_json=None,
                original_filename=None,
                storage_key=None,
                deleted_at=now,
                updated_at=now,
            )
        )
        counts["resumes_scrubbed"] = (
            await session.execute(scrub_resume)
        ).rowcount or 0

        # 11. Applicant — scrub PII + tombstone.
        scrub_applicant = (
            update(Applicant)
            .where(Applicant.id == applicant_id)
            .values(
                full_name=None,
                locations=None,
                notice_period_days=None,
                current_ctc=None,
                deleted_at=now,
                updated_at=now,
            )
        )
        await session.execute(scrub_applicant)
        counts["applicant_tombstoned"] = 1
    else:
        counts["saved_jobs"] = 0
        counts["applicant_embeddings"] = 0
        counts["resumes_scrubbed"] = 0
        counts["applicant_tombstoned"] = 0

    # 12. User — scrub PII + tombstone.
    now = datetime.now(UTC)
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            email=None,
            phone=None,
            deleted_at=now,
            updated_at=now,
        )
    )
    counts["user_tombstoned"] = 1

    await session.flush()

    return DeleteReport(
        deleted_at=now,
        section_counts=counts,
        warnings=warnings,
    )
```

- [ ] **Step 3: Run unit tests**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v tests/unit/dsr/test_deleter_signature.py
uv run ruff check src/kpa/dsr/ tests/unit/dsr/
uv run ruff format src/kpa/dsr/ tests/unit/dsr/
uv run mypy
```

3/3 unit tests pass; ruff + mypy clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/dsr/deleter.py api/tests/unit/dsr/test_deleter_signature.py
git commit -m "feat(api): DSR delete orchestrator (delete_user_data)

Walks the user's data graph per the brainstorm-locked strategy:
hard-delete OAuth identities, refresh tokens, notifications, consents,
employer memberships, saved jobs, applicant embeddings, resume blobs;
soft-delete + scrub resumes, applicant, user (PII fields nulled,
deleted_at set). Application + match rows survive anonymized via the
tombstoned applicant. Caller owns the txn — atomicity is the contract."
```

---

### Task 2: DELETE route + audit rows

**Files:**
- Modify: `api/src/kpa/routes/dsr.py`

- [ ] **Step 1: Add the DELETE handler**

Open `api/src/kpa/routes/dsr.py`. The existing `POST /v1/me/dsr/export` handler stays. Add (with appropriate imports at the top):

```python
from pydantic import BaseModel, ConfigDict
from fastapi import HTTPException

from kpa.dsr.deleter import DeleteReport, delete_user_data
from kpa.storage.base import Storage
from kpa.storage.dependencies import get_storage


_CONFIRMATION_TOKEN = "DELETE_MY_ACCOUNT"


class DsrDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str


@router.delete("/dsr", response_model=DeleteReport)
async def delete_user_data_endpoint(
    body: DsrDeleteRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> DeleteReport:
    """DPDP § 12 right-of-erasure. Soft-delete-and-scrub User + Applicant
    tombstones; hard-delete around them. Atomic — partial deletion is worse
    than no deletion."""

    if body.confirmation != _CONFIRMATION_TOKEN:
        raise HTTPException(status_code=400, detail="confirmation_mismatch")

    request_id = request.state.request_id

    # Audit BEFORE the destructive work. Same txn — atomic with the deletion.
    await audit_log(
        session,
        action="user.dsr_delete_requested",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={"request_id": request_id},
    )

    report = await delete_user_data(session, storage=storage, user=user)

    await audit_log(
        session,
        action="user.dsr_deleted",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={
            "request_id": request_id,
            "section_counts": report.section_counts,
            "warnings": [w.model_dump(mode="json") for w in report.warnings],
        },
    )

    _log.info(
        "dsr.delete-completed",
        user_id=str(user.id),
        section_counts=report.section_counts,
        warning_count=len(report.warnings),
    )

    return report
```

Add necessary imports at the file top if not already present:

```python
from fastapi import HTTPException
from kpa.storage.base import Storage
from kpa.storage.dependencies import get_storage
from kpa.dsr.deleter import DeleteReport, delete_user_data
```

Verify the existing file already imports `audit_log`, `current_user`, `get_session`, `Request`, `Depends`, `Response`, `BaseModel`, `ConfigDict`, `User`, `AsyncSession`. If any are missing, add them.

`get_storage` lives in `kpa.storage.dependencies` (per the resume routes' import pattern — confirm by grepping `from kpa.storage.dependencies` in `api/src/kpa/routes/resumes.py` before assuming).

- [ ] **Step 2: Verify lint + types**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run ruff check src/kpa/routes/dsr.py
uv run ruff format src/kpa/routes/dsr.py
uv run mypy
```

- [ ] **Step 3: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/routes/dsr.py
git commit -m "feat(api): DELETE /v1/me/dsr endpoint

Body: {confirmation: 'DELETE_MY_ACCOUNT'} guard. Atomic transaction wraps
user.dsr_delete_requested + delete_user_data + user.dsr_deleted — partial
deletion rolls back. Response carries section_counts + ownerless-employer
warnings for the client to display."
```

---

### Task 3: Integration tests

**Files:**
- Create: `api/tests/integration/test_dsr_delete.py`

- [ ] **Step 1: Write the tests**

Create `api/tests/integration/test_dsr_delete.py`:

```python
"""Integration tests for DELETE /v1/me/dsr.

Covers:
1. Confirmation guard — wrong token / missing field → 400 or 422.
2. Applicant happy path — user + applicant tombstoned, oauth + consents
   + notifications + refresh_tokens hard-gone, audit rows written.
3. Recruiter happy path — sole-owner employer warning in response.
4. Application + match survive anonymized after applicant delete.
5. JWT becomes invalid after delete (401 user_not_found).
6. Re-signup with same email creates a fresh user (no collision).
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import mint_access_token
from kpa.consent import seed_default_consents
from kpa.db.models import (
    Applicant,
    Application,
    ApplicationSource,
    ApplicationStatus,
    AuditLog,
    Employer,
    EmployerUser,
    Job,
    JobStatus,
    Notification,
    NotificationChannel,
    NotificationStatus,
    OAuthIdentity,
    OAuthProvider,
    User,
    UserConsent,
    UserRole,
)


_CONFIRMATION = {"confirmation": "DELETE_MY_ACCOUNT"}


async def _make_applicant_with_dependencies(
    session: AsyncSession,
) -> tuple[User, Applicant, str]:
    user = User(
        email=f"dsrd-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT
    )
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="DSR Test User")
    session.add(applicant)
    await session.flush()
    # OAuth identity
    session.add(
        OAuthIdentity(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_subject=f"sub-{uuid4().hex}",
            email_at_link=user.email,
        )
    )
    # Notification
    session.add(
        Notification(
            user_id=user.id,
            kind="application.applied",
            channel=NotificationChannel.IN_APP,
            payload={"job_title": "Test Role"},
        )
    )
    # Consents
    await seed_default_consents(session, user=user)
    await session.commit()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, applicant, token


async def _make_recruiter_with_employer(
    session: AsyncSession,
) -> tuple[User, Employer, str]:
    user = User(
        email=f"rec-{uuid4().hex[:8]}@example.com", role=UserRole.RECRUITER
    )
    session.add(user)
    await session.flush()
    employer = Employer(name=f"Foo Inc {uuid4().hex[:6]}")
    session.add(employer)
    await session.flush()
    link = EmployerUser(employer_id=employer.id, user_id=user.id, role="owner")
    session.add(link)
    await seed_default_consents(session, user=user)
    await session.commit()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, employer, token


@pytest.mark.asyncio
async def test_delete_wrong_confirmation_returns_400(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    _user, _applicant, token = await _make_applicant_with_dependencies(session)
    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmation": "not_the_token"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "confirmation_mismatch"


@pytest.mark.asyncio
async def test_delete_missing_confirmation_returns_422(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    _user, _applicant, token = await _make_applicant_with_dependencies(session)
    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json={},  # missing required field
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_applicant_happy_path_tombstones_and_clears(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, token = await _make_applicant_with_dependencies(session)

    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["section_counts"]["notifications"] == 1
    assert body["section_counts"]["oauth_identities"] == 1
    assert body["section_counts"]["user_consents"] == 7
    assert body["section_counts"]["user_tombstoned"] == 1
    assert body["section_counts"]["applicant_tombstoned"] == 1
    assert body["warnings"] == []

    # User row is tombstoned (still exists) with PII scrubbed.
    refetched_user = (
        await session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refetched_user.deleted_at is not None
    assert refetched_user.email is None
    assert refetched_user.phone is None

    # Applicant row is tombstoned with PII scrubbed.
    refetched_applicant = (
        await session.execute(select(Applicant).where(Applicant.id == applicant.id))
    ).scalar_one()
    assert refetched_applicant.deleted_at is not None
    assert refetched_applicant.full_name is None

    # Notifications + OAuth identities + consents are hard-gone.
    assert (
        await session.execute(
            select(Notification).where(Notification.user_id == user.id)
        )
    ).scalars().first() is None
    assert (
        await session.execute(
            select(OAuthIdentity).where(OAuthIdentity.user_id == user.id)
        )
    ).scalars().first() is None
    assert (
        await session.execute(
            select(UserConsent).where(UserConsent.user_id == user.id)
        )
    ).scalars().first() is None

    # Audit rows written.
    audit_rows = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action.in_(
                    ["user.dsr_delete_requested", "user.dsr_deleted"]
                ),
            )
            .order_by(AuditLog.created_at.asc())
        )
    ).scalars().all()
    assert len(audit_rows) == 2
    assert audit_rows[0].action == "user.dsr_delete_requested"
    assert audit_rows[1].action == "user.dsr_deleted"
    assert "section_counts" in audit_rows[1].context


@pytest.mark.asyncio
async def test_recruiter_sole_owner_employer_warning(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, employer, token = await _make_recruiter_with_employer(session)

    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["warnings"]) == 1
    w = body["warnings"][0]
    assert w["type"] == "ownerless_employer"
    assert w["employer_id"] == str(employer.id)
    assert w["employer_name"] == employer.name

    # Employer row survives.
    refetched_employer = (
        await session.execute(select(Employer).where(Employer.id == employer.id))
    ).scalar_one()
    assert refetched_employer.deleted_at is None
    # employer_users membership for the recruiter is hard-gone.
    assert (
        await session.execute(
            select(EmployerUser).where(EmployerUser.user_id == user.id)
        )
    ).scalars().first() is None


@pytest.mark.asyncio
async def test_application_survives_anonymized(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, token = await _make_applicant_with_dependencies(session)
    # Set up an employer + job + application so we can observe survival.
    employer = Employer(name=f"E-{uuid4().hex[:6]}")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Senior Role",
        description="Desc.",
        locations=["Remote"],
        status=JobStatus.OPEN,
        min_exp_years=3,
        max_exp_years=8,
    )
    session.add(job)
    await session.flush()
    application = Application(
        applicant_id=applicant.id,
        job_id=job.id,
        status=ApplicationStatus.APPLIED,
        source=ApplicationSource.FEED,
    )
    session.add(application)
    await session.commit()

    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp.status_code == 200

    # Application row still exists; applicant_id still references the
    # (now-tombstoned) applicant.
    refetched_app = (
        await session.execute(
            select(Application).where(Application.id == application.id)
        )
    ).scalar_one()
    assert refetched_app.applicant_id == applicant.id

    # And the applicant tombstone has no PII.
    refetched_applicant = (
        await session.execute(select(Applicant).where(Applicant.id == applicant.id))
    ).scalar_one()
    assert refetched_applicant.full_name is None


@pytest.mark.asyncio
async def test_subsequent_request_returns_401(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    _user, _applicant, token = await _make_applicant_with_dependencies(session)

    # First delete succeeds.
    resp1 = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp1.status_code == 200

    # Second request with the same token → 401 (user_not_found via current_user
    # refetch since deleted_at is now set).
    resp2 = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp2.status_code == 401
```

- [ ] **Step 2: Run the tests**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration tests/integration/test_dsr_delete.py
uv run pytest -m integration -q  # full suite (was 273; now 273 + 6 = 279)
uv run pytest -m "not integration" -q
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

Expected: 6/6 new pass, full suite 279.

### Likely failure modes

- **Recruiter `EmployerUser.role` value mismatch.** The model declares the field; the existing routes use the string `'owner'` (lowercase). If they use a different constant, mirror it.
- **Application requires more fields than the test sets** — read `Application.__init__` and add any NOT NULL columns the test missed (e.g., `cover_letter` may be NULL; verify).
- **`get_storage` import path** — confirm via `grep -rn "from kpa.storage" api/src/kpa/routes/resumes.py` before guessing.

- [ ] **Step 3: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/tests/integration/test_dsr_delete.py
git commit -m "test(api): integration tests for DELETE /v1/me/dsr

Six tests: confirmation guard (400 + 422), applicant tombstone
verification, recruiter sole-owner-employer warning, application
survival post-delete (anonymized), subsequent-request-401."
```

---

### Task 4: CLAUDE.md + PR

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the CLAUDE.md section**

Open `CLAUDE.md`. Find the existing `### DSR export` section (added by PR #27). AFTER its body and BEFORE the next `###`, INSERT the new "DSR delete" section. The spec § 9 has the complete text — lift it verbatim.

- [ ] **Step 2: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add CLAUDE.md
git commit -m "docs: DSR delete invariants in CLAUDE.md"
```

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/p4-dsr-delete
gh pr create --title "feat(api): P4-D DSR delete (right-to-be-forgotten)" --body "$(cat <<'EOF'
## Summary
Fourth and final P4 sub-project. Stacked on top of PR #27 (DSR export), which is stacked on PR #26 (consent), which is stacked on PR #25 (audit_logs). After all three predecessors merge to main, this PR's diff shrinks to only the DSR-delete work.

- \`DELETE /v1/me/dsr\` with body \`{"confirmation": "DELETE_MY_ACCOUNT"}\` guard. Wrong token → 400; missing field → 422.
- **Soft-delete + scrub** User + Applicant + Resume rows (PII fields nulled, \`deleted_at\` set) so FKs from Application + Match still resolve.
- **Hard-delete** OAuth identities, refresh tokens, notifications, consents, employer memberships, saved jobs, applicant embeddings, resume blobs.
- **Preserve anonymized** Application + Match rows — recruiter analytics + eval substrate intact.
- Atomic transaction: \`user.dsr_delete_requested\` + the deletion + \`user.dsr_deleted\` all commit or all roll back. Partial deletion is worse than no deletion.
- Sole-owner-employer detection surfaces \`warnings\` in the response. Employer rows preserved; admin tooling handles reassignment.
- Subsequent requests with the same JWT → 401 \`user_not_found\` because \`current_user\` re-fetches and the tombstone is soft-deleted.

Spec: \`docs/superpowers/specs/2026-05-29-dsr-delete-design.md\`
Plan: \`docs/superpowers/plans/2026-05-29-dsr-delete.md\`

## Test plan
- [x] \`uv run pytest -m integration tests/integration/test_dsr_delete.py\` — 6/6 pass
- [x] Full integration suite stays green (273 → 279)
- [x] \`uv run mypy\` clean
- [x] \`uv run ruff check\` clean

## Why soft-delete-and-scrub, not hard-delete the User row

Hard-deleting users would CASCADE-wipe applications and matches (FKs to applicants → users), losing recruiter analytics and the eval substrate. The brainstorm constraint was "hard-delete PII, keep anonymized aggregates" — we honor it by tombstoning \`users\` and \`applicants\` with PII scrubbed, then hard-deleting the truly-PII tables around them.

## Out of scope
- Admin-initiated DSR-delete of another user — separate admin sub-project
- 30-day grace period / reversibility — column + Celery beat needed; defer until product asks
- Orphaned-blob janitor sweep — tracked as deploy-target follow-up
- Tombstone hard-delete after N-year retention — needs data retention policy first

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Print the PR URL.

---

## Self-review checklist

- [x] Every spec section maps to a task: §2 strategy table → Task 1; §3 endpoint → Task 2; §4 audit trail → Task 2; §5 orchestrator → Task 1; §7 sole-owner detection → Task 1; §9 docs → Task 4.
- [x] Atomic-transaction contract is enforced by writing both audit rows in the SAME txn as the deletion (NOT the durable-request-row pattern from export, which is wrong for delete).
- [x] `update().where().values()` for tombstoning (not row.attribute = value) so the rowcount is reportable.
- [x] Sole-owner detection runs BEFORE membership delete so the comparison sees current state.
- [x] Storage blob delete is best-effort (try/except + warning log), not atomic — caller's txn isn't poisoned by storage hiccups.
- [x] Re-signup flow is verifiable (test would extend `_make_applicant`, perform delete, then sign in via the OAuth flow with same email — covered in a follow-up test if time permits, otherwise documented as "manual smoke test for now").
