# P4-B Consent + notification-channel preferences — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** Persist per-user consent state for the three v0 notification scopes, gate the P3.1 notification sweep on it, and write every grant/revoke through the audit substrate that sub-project A shipped.

**Architecture:** One `user_consents` table (soft-delete + partial-UNIQUE per `(user_id, scope)`). A `consent` helper module with `get_consent`/`set_consent`/`seed_default_consents`. Two endpoints (`GET`+`PATCH /v1/me/consents`). Eager seeding at signup in `_upsert_identity`. Sweep gate before channel dispatch. `NotificationStatus.CANCELLED` added via `ALTER TYPE` inside an autocommit block.

**Tech Stack:** Python 3.12 / FastAPI / async SQLAlchemy 2.x / Alembic / asyncpg / Postgres 16 / Celery / pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-consent-channel-prefs-design.md`

---

## Files

**Create:**
- `api/src/kpa/db/migrations/versions/0014_user_consents.py`
- `api/src/kpa/consent/__init__.py`
- `api/src/kpa/routes/consents.py`
- `api/src/kpa/cli/seed_consents.py`
- `api/tests/unit/consent/__init__.py` (empty)
- `api/tests/unit/consent/test_consent_helper_signature.py`
- `api/tests/integration/test_user_consents.py`
- `api/tests/integration/test_consents_routes.py`
- `api/tests/integration/test_sweep_consent_gate.py`
- `api/tests/integration/test_seed_consents_cli.py`

**Modify:**
- `api/src/kpa/db/models.py` — add `ConsentScope` StrEnum, `UserConsent` model, `Notification.cancelled_at` column, `NotificationStatus.CANCELLED`.
- `api/src/kpa/auth/service.py` — call `seed_default_consents` in `_upsert_identity` new-user branch. Plumb `request_id` through the call site.
- `api/src/kpa/routes/auth.py` (or wherever `AuthService` is instantiated) — pass `request_id` into `sign_in_with_google`.
- `api/src/kpa/workers/tasks/sweep_notifications.py` — gate on consent between user load and channel dispatch.
- `api/src/kpa/routes/notifications.py` — exclude `status='cancelled'` from `/v1/notifications`.
- `api/src/kpa/app_factory.py` — mount the new `routes/consents.py` router under `/v1`.
- `api/pyproject.toml` — register `kpa-seed-consents` script.
- `CLAUDE.md` — add the "Consent + notification-channel preferences" section.

---

### Task 1: Migration 0014 + model changes

**Files:**
- Create: `api/src/kpa/db/migrations/versions/0014_user_consents.py`
- Modify: `api/src/kpa/db/models.py`

- [ ] **Step 1: Read the most recent migration for style**

Read `api/src/kpa/db/migrations/versions/0013_audit_logs.py` (most recent — shipped via PR #25). Match: header docstring, imports, the `op.execute(...)` style for raw SQL indexes, downgrade order.

- [ ] **Step 2: Write the migration**

Create `api/src/kpa/db/migrations/versions/0014_user_consents.py`:

```python
"""user_consents + Notification.cancelled status

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-29

Adds the operational consent table for P4 DPDP scopes, plus the
NotificationStatus.CANCELLED enum value + Notification.cancelled_at column
that the sweep uses when consent is revoked.

NOTE: ALTER TYPE ... ADD VALUE cannot run inside a transaction with other
DDL. We use op.get_context().autocommit_block() for that statement.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- user_consents ---
    op.create_table(
        "user_consents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("kpa.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="kpa",
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_user_consents_user_scope_live "
        "ON kpa.user_consents (user_id, scope) WHERE deleted_at IS NULL"
    )

    # --- Notification.cancelled_at column ---
    op.add_column(
        "notifications",
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="kpa",
    )

    # --- NotificationStatus.CANCELLED enum value (autocommit-block required) ---
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE kpa.notification_status ADD VALUE IF NOT EXISTS 'cancelled'"
        )


def downgrade() -> None:
    # Note: Postgres does NOT support DROP VALUE on enums. The 'cancelled'
    # value stays in the type after downgrade — that's an accepted limitation
    # of Postgres native enums. The model + sweep no longer reference it.

    op.drop_column("notifications", "cancelled_at", schema="kpa")
    op.execute("DROP INDEX kpa.ix_user_consents_user_scope_live")
    op.drop_table("user_consents", schema="kpa")
```

- [ ] **Step 3: Run the migration (round-trip)**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run alembic upgrade head
psql kpa -c "\d kpa.user_consents"   # verify 7 cols + partial UNIQUE
psql kpa -c "\d kpa.notifications" | grep cancelled_at  # verify column added
psql kpa -c "\dT+ kpa.notification_status"  # verify 'cancelled' value present
uv run alembic downgrade -1
uv run alembic upgrade head
```

All must succeed.

- [ ] **Step 4: Add `ConsentScope` enum + `UserConsent` model + `Notification.cancelled_at` + `NotificationStatus.CANCELLED`**

Edit `api/src/kpa/db/models.py`.

(a) Locate the existing `NotificationStatus` StrEnum (around line 624). Add `CANCELLED = "cancelled"` to it.

(b) Locate the `Notification` class. Add a `cancelled_at` column near `sent_at`:

```python
cancelled_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

(c) Near the bottom of the file (after `AuditLog` from sub-project A), add the `ConsentScope` enum and `UserConsent` model:

```python
class ConsentScope(StrEnum):
    EMAIL_TRANSACTIONAL = "email_transactional"
    EMAIL_MARKETING = "email_marketing"
    IN_APP_NOTIFICATIONS = "in_app_notifications"
    WHATSAPP_NOTIFICATIONS = "whatsapp_notifications"
    SMS_NOTIFICATIONS = "sms_notifications"
    PROFILE_VISIBILITY_RECRUITERS = "profile_visibility_recruiters"
    THIRD_PARTY_SHARING_RECRUITERS = "third_party_sharing_recruiters"


# Defaults are the single source of truth for new-user seeding AND for the
# sweep's LookupError fallback.
DEFAULT_CONSENTS: dict[ConsentScope, bool] = {
    ConsentScope.EMAIL_TRANSACTIONAL: True,
    ConsentScope.EMAIL_MARKETING: False,
    ConsentScope.IN_APP_NOTIFICATIONS: True,
    ConsentScope.WHATSAPP_NOTIFICATIONS: False,
    ConsentScope.SMS_NOTIFICATIONS: False,
    ConsentScope.PROFILE_VISIBILITY_RECRUITERS: False,
    ConsentScope.THIRD_PARTY_SHARING_RECRUITERS: False,
}


class UserConsent(Base):
    """Operational consent state for P4 DPDP scopes. History lives in audit_logs.

    Soft-delete + partial-UNIQUE on (user_id, scope) WHERE deleted_at IS NULL.
    ON DELETE CASCADE on user_id (opposite of audit_logs — consent for a
    non-existent user is meaningless; the audit history outlives the user via
    audit_logs.actor_user_id ON DELETE SET NULL).
    """

    __tablename__ = "user_consents"

    id: Mapped[UuidPK]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]
```

This IS a normal soft-deleted domain table — `CreatedAt`/`UpdatedAt`/`DeletedAt` Annotated types apply (unlike `AuditLog`). The partial-UNIQUE index is already declared in the migration; no `__table_args__` entry needed because the migration owns it.

`scope` is plain TEXT in the DB (per spec §4) — Pydantic at the API boundary maps strings to `ConsentScope`. Don't use `SAEnum` here.

- [ ] **Step 5: Verify lint / type / tests still pass**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run ruff check src/
uv run ruff format src/
uv run mypy
uv run pytest -m integration -q  # full suite must stay green
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/db/migrations/versions/0014_user_consents.py \
        api/src/kpa/db/models.py
git commit -m "feat(api): user_consents + NotificationStatus.CANCELLED for P4-B"
```

---

### Task 2: `consent` helper module + unit test

**Files:**
- Create: `api/src/kpa/consent/__init__.py`
- Create: `api/tests/unit/consent/__init__.py` (empty)
- Create: `api/tests/unit/consent/test_consent_helper_signature.py`

- [ ] **Step 1: Write the failing unit test**

Create `api/tests/unit/consent/__init__.py`: empty (`""`).

Create `api/tests/unit/consent/test_consent_helper_signature.py`:

```python
"""Pure-signature contract tests for consent helpers. No DB."""
from __future__ import annotations

import inspect

from kpa.consent import get_consent, seed_default_consents, set_consent


def test_get_consent_signature() -> None:
    sig = inspect.signature(get_consent)
    assert list(sig.parameters)[0] == "session"
    for name in ("user", "scope"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_set_consent_signature() -> None:
    sig = inspect.signature(set_consent)
    assert list(sig.parameters)[0] == "session"
    for name in ("user", "scope", "granted", "request_id"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_seed_default_consents_signature() -> None:
    sig = inspect.signature(seed_default_consents)
    assert list(sig.parameters)[0] == "session"
    for name in ("user", "request_id"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
```

Run: `uv run pytest -v tests/unit/consent/`. Expected: FAIL (module doesn't exist).

- [ ] **Step 2: Write the helper**

Create `api/src/kpa/consent/__init__.py`:

```python
"""Per-user consent state for P4 DPDP scopes.

Three entry points:

* ``get_consent`` — read current state. Raises ``LookupError`` if no live
  row exists (means seeding was skipped — caller may fall back to
  ``DEFAULT_CONSENTS[scope]``).
* ``set_consent`` — UPSERT + audit row. No-op on noop (doesn't write
  audit when the requested state matches current state).
* ``seed_default_consents`` — insert one row per ConsentScope using
  ``DEFAULT_CONSENTS`` as values, + one audit row per insertion. Idempotent.

All three participate in the caller's transaction — no commit, no
fire-and-forget. Mirrors ``audit_log()``.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.db.models import (
    DEFAULT_CONSENTS,
    ConsentScope,
    User,
    UserConsent,
)


async def get_consent(
    session: AsyncSession,
    *,
    user: User,
    scope: ConsentScope,
) -> bool:
    row = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == scope.value,
                UserConsent.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise LookupError(
            f"no live consent row for user={user.id} scope={scope.value}"
        )
    return row.granted


async def set_consent(
    session: AsyncSession,
    *,
    user: User,
    scope: ConsentScope,
    granted: bool,
    request_id: str | None = None,
) -> UserConsent:
    row = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == scope.value,
                UserConsent.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if row is not None and row.granted == granted:
        # No-op — don't write a spurious audit row.
        return row

    if row is None:
        row = UserConsent(user_id=user.id, scope=scope.value, granted=granted)
        session.add(row)
    else:
        row.granted = granted

    await session.flush()

    await audit_log(
        session,
        action="consent.granted" if granted else "consent.revoked",
        actor=user,
        resource_type="consent",
        resource_id=row.id,
        context={
            "scope": scope.value,
            "granted": granted,
            **({"request_id": request_id} if request_id else {}),
        },
    )

    return row


async def seed_default_consents(
    session: AsyncSession,
    *,
    user: User,
    request_id: str | None = None,
) -> list[UserConsent]:
    """Insert default rows for every scope that doesn't already have one.

    Idempotent: re-running on a user who already has live rows leaves them
    untouched and only inserts what's missing. The backfill CLI relies on
    this.
    """
    existing = {
        row.scope
        for row in (
            await session.execute(
                select(UserConsent).where(
                    UserConsent.user_id == user.id,
                    UserConsent.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }

    created: list[UserConsent] = []
    for scope, default_value in DEFAULT_CONSENTS.items():
        if scope.value in existing:
            continue
        row = UserConsent(
            user_id=user.id,
            scope=scope.value,
            granted=default_value,
        )
        session.add(row)
        created.append(row)

    if not created:
        return created

    await session.flush()

    for row in created:
        await audit_log(
            session,
            action="consent.seeded",
            actor=user,
            resource_type="consent",
            resource_id=row.id,
            context={
                "scope": row.scope,
                "granted": row.granted,
                **({"request_id": request_id} if request_id else {}),
            },
        )

    return created
```

- [ ] **Step 3: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v tests/unit/consent/
uv run ruff check src/kpa/consent/ tests/unit/consent/
uv run ruff format src/kpa/consent/ tests/unit/consent/
uv run mypy
```

3/3 unit tests pass, ruff + mypy clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/consent/ api/tests/unit/consent/
git commit -m "feat(api): consent helper module (get/set/seed) with audit writes"
```

---

### Task 3: Integration tests for the consent helper

**Files:**
- Create: `api/tests/integration/test_user_consents.py`

- [ ] **Step 1: Write the tests**

Create `api/tests/integration/test_user_consents.py`:

```python
"""Integration tests for consent helpers against real Postgres.

Covers happy paths + the load-bearing invariants:
- seed_default_consents inserts 7 rows + 7 audit rows on a fresh user.
- seed is idempotent (re-run inserts nothing).
- set_consent writes one audit row on a state change.
- set_consent is a no-op when state matches (no audit row).
- get_consent raises LookupError when no row exists.
- Soft-deleted rows are invisible to get_consent.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.consent import get_consent, seed_default_consents, set_consent
from kpa.db.models import (
    DEFAULT_CONSENTS,
    AuditLog,
    ConsentScope,
    User,
    UserConsent,
    UserRole,
)


@pytest.mark.asyncio
async def test_seed_inserts_all_scopes_and_audit_rows(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()

    created = await seed_default_consents(session, user=user, request_id="req-seed")

    assert len(created) == len(DEFAULT_CONSENTS)
    rows = (
        await session.execute(
            select(UserConsent).where(UserConsent.user_id == user.id)
        )
    ).scalars().all()
    assert len(rows) == len(DEFAULT_CONSENTS)
    by_scope = {r.scope: r.granted for r in rows}
    for scope, default in DEFAULT_CONSENTS.items():
        assert by_scope[scope.value] is default

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action == "consent.seeded",
            )
        )
    ).scalars().all()
    assert len(audits) == len(DEFAULT_CONSENTS)
    assert all(a.context["request_id"] == "req-seed" for a in audits)


@pytest.mark.asyncio
async def test_seed_is_idempotent(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()

    first = await seed_default_consents(session, user=user)
    assert len(first) == len(DEFAULT_CONSENTS)
    second = await seed_default_consents(session, user=user)
    assert second == []


@pytest.mark.asyncio
async def test_set_consent_writes_audit_on_state_change(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    # email_marketing defaults to False — flip to True.
    updated = await set_consent(
        session,
        user=user,
        scope=ConsentScope.EMAIL_MARKETING,
        granted=True,
        request_id="req-flip",
    )
    assert updated.granted is True

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action == "consent.granted",
                AuditLog.resource_id == updated.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].context["scope"] == "email_marketing"
    assert audits[0].context["request_id"] == "req-flip"


@pytest.mark.asyncio
async def test_set_consent_noop_writes_no_audit(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    # email_transactional defaults to True — set to True again (noop).
    await set_consent(
        session,
        user=user,
        scope=ConsentScope.EMAIL_TRANSACTIONAL,
        granted=True,
    )

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action.in_(["consent.granted", "consent.revoked"]),
            )
        )
    ).scalars().all()
    assert audits == []  # No grant/revoke audit, only the seed rows above.


@pytest.mark.asyncio
async def test_get_consent_raises_when_no_row(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    # No seeding — user has zero consent rows.

    with pytest.raises(LookupError, match="no live consent row"):
        await get_consent(session, user=user, scope=ConsentScope.EMAIL_TRANSACTIONAL)


@pytest.mark.asyncio
async def test_get_consent_ignores_soft_deleted(session: AsyncSession) -> None:
    user = User(email=f"c-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    row = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == ConsentScope.EMAIL_TRANSACTIONAL.value,
            )
        )
    ).scalar_one()

    from datetime import UTC, datetime
    row.deleted_at = datetime.now(UTC)
    await session.flush()

    with pytest.raises(LookupError):
        await get_consent(session, user=user, scope=ConsentScope.EMAIL_TRANSACTIONAL)
```

- [ ] **Step 2: Run**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration tests/integration/test_user_consents.py
```

Expected: 6/6 PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/tests/integration/test_user_consents.py
git commit -m "test(api): integration tests for consent helper module"
```

---

### Task 4: Wire seeding into `_upsert_identity`

**Files:**
- Modify: `api/src/kpa/auth/service.py`
- Modify: `api/src/kpa/routes/auth.py` (or wherever `sign_in_with_google` is invoked)

- [ ] **Step 1: Plumb `request_id` through AuthService**

Read `api/src/kpa/auth/service.py`. The `AuthService.sign_in_with_google(self, id_token: str)` signature doesn't currently take a `request_id`.

Add it as an optional parameter:

```python
async def sign_in_with_google(
    self,
    id_token: str,
    *,
    request_id: str | None = None,
) -> SignInResult:
```

Pass it down into `_upsert_identity`:

```python
async def _upsert_identity(
    self,
    claims: GoogleClaims,
    *,
    request_id: str | None = None,
) -> tuple[User, Applicant, bool]:
```

- [ ] **Step 2: Call `seed_default_consents` on the new-user branch**

In `_upsert_identity`, locate the new-user branch (the block after the email-collision check, where `User`, `Applicant`, `OAuthIdentity` are inserted). After `self._session.add(identity)` and BEFORE the final `await self._session.flush()`, add:

```python
from kpa.consent import seed_default_consents  # at the top of the file

# ... existing inserts ...
self._session.add(identity)
await self._session.flush()  # populate IDs first

await seed_default_consents(
    self._session,
    user=user,
    request_id=request_id,
)
return user, applicant, True
```

Note the `flush()` ordering — `user.id` must be populated before seeding because the consent rows FK to it.

- [ ] **Step 3: Plumb `request_id` from the route**

Find the route that calls `auth_service.sign_in_with_google(...)` (likely `routes/auth.py:POST /v1/auth/oauth/google`). It already takes a `request: Request` for `RequestIdMiddleware`. Pass `request_id=request.state.request_id` to `sign_in_with_google`.

- [ ] **Step 4: Integration test — first sign-in seeds consents + writes audit**

Locate the existing auth integration test (likely `api/tests/integration/test_auth_oauth.py` or similar). Extend the happy-path "first sign-in" test:

```python
from sqlalchemy import select
from kpa.db.models import AuditLog, UserConsent, DEFAULT_CONSENTS

# After the existing assertions on the SignInResult / 200 response:

consent_rows = (
    await session.execute(
        select(UserConsent).where(UserConsent.user_id == user.id)
    )
).scalars().all()
assert len(consent_rows) == len(DEFAULT_CONSENTS)

audit_rows = (
    await session.execute(
        select(AuditLog).where(
            AuditLog.actor_user_id == user.id,
            AuditLog.action == "consent.seeded",
        )
    )
).scalars().all()
assert len(audit_rows) == len(DEFAULT_CONSENTS)
```

If the test uses sync `client` instead of `async_client`, switch to `async_client` per CLAUDE.md's HTTP-client guidance.

- [ ] **Step 5: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration -k "auth or oauth or sign_in"
uv run pytest -v -m integration  # full suite
uv run ruff check src/ tests/
uv run mypy
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/auth/service.py api/src/kpa/routes/auth.py \
        api/tests/integration/
git commit -m "feat(api): seed default consents on first sign-in"
```

---

### Task 5: `/v1/me/consents` endpoints + tests

**Files:**
- Create: `api/src/kpa/routes/consents.py`
- Create: `api/tests/integration/test_consents_routes.py`
- Modify: `api/src/kpa/app_factory.py` (mount the router)

- [ ] **Step 1: Write the router**

Create `api/src/kpa/routes/consents.py`:

```python
"""Self-service consent endpoints. Any authenticated user reads/edits their
own consents — applicants, recruiters, and admins all have the same surface.
"""
from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import current_user
from kpa.consent import set_consent
from kpa.db.models import ConsentScope, User, UserConsent
from kpa.db.session import get_session

router = APIRouter(prefix="/v1/me", tags=["consents"])
_log = structlog.get_logger(__name__)


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope: str
    granted: bool
    updated_at: datetime


class ConsentListResponse(BaseModel):
    items: list[ConsentRead]


class ConsentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted: bool


@router.get("/consents", response_model=ConsentListResponse)
async def list_consents(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ConsentListResponse:
    rows = (
        await session.execute(
            select(UserConsent)
            .where(
                UserConsent.user_id == user.id,
                UserConsent.deleted_at.is_(None),
            )
            .order_by(UserConsent.scope.asc())
        )
    ).scalars().all()
    return ConsentListResponse(items=[ConsentRead.model_validate(r) for r in rows])


@router.patch("/consents/{scope}", response_model=ConsentRead)
async def patch_consent(
    scope: ConsentScope,
    body: ConsentPatchRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ConsentRead:
    # Defensive: a soft-deleted row shouldn't normally appear here (admins
    # don't touch consents in this slice), but if one does, set_consent
    # would INSERT a fresh row and the partial-UNIQUE would still hold.
    # We surface a 404 instead — admin DSR action, user must re-grant via
    # support.
    existing = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == scope.value,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.deleted_at is not None:
        raise HTTPException(status_code=404, detail="consent_not_found")

    row = await set_consent(
        session,
        user=user,
        scope=scope,
        granted=body.granted,
        request_id=request.state.request_id,
    )
    return ConsentRead.model_validate(row)
```

- [ ] **Step 2: Mount the router**

In `api/src/kpa/app_factory.py`, find where other routers are included (likely a section with `app.include_router(...)` calls). Add:

```python
from kpa.routes import consents as consents_routes
# ... inside create_app, with the others:
app.include_router(consents_routes.router)
```

Match the surrounding pattern; if the file imports routers individually at the top, follow that style.

- [ ] **Step 3: Write integration tests**

Create `api/tests/integration/test_consents_routes.py`:

```python
"""Integration tests for GET + PATCH /v1/me/consents."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import mint_access_token
from kpa.consent import seed_default_consents
from kpa.db.models import AuditLog, DEFAULT_CONSENTS, User, UserRole


@pytest.fixture
async def applicant_with_consents(
    session: AsyncSession,
) -> tuple[User, str]:
    user = User(
        email=f"croute-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT
    )
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)
    await session.commit()  # commit the savepoint so async_client sees it
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, token


@pytest.mark.asyncio
async def test_get_consents_returns_all_seeded_scopes(
    async_client: AsyncClient, applicant_with_consents: tuple[User, str]
) -> None:
    _user, token = applicant_with_consents
    resp = await async_client.get(
        "/v1/me/consents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == len(DEFAULT_CONSENTS)
    by_scope = {it["scope"]: it["granted"] for it in body["items"]}
    for scope, default in DEFAULT_CONSENTS.items():
        assert by_scope[scope.value] is default


@pytest.mark.asyncio
async def test_patch_consent_flips_and_writes_audit(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_with_consents: tuple[User, str],
) -> None:
    user, token = applicant_with_consents
    resp = await async_client.patch(
        "/v1/me/consents/email_marketing",
        headers={"Authorization": f"Bearer {token}"},
        json={"granted": True},
    )
    assert resp.status_code == 200
    assert resp.json()["granted"] is True

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action == "consent.granted",
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].context["scope"] == "email_marketing"


@pytest.mark.asyncio
async def test_patch_consent_unknown_scope_returns_422(
    async_client: AsyncClient, applicant_with_consents: tuple[User, str]
) -> None:
    _user, token = applicant_with_consents
    resp = await async_client.patch(
        "/v1/me/consents/not_a_real_scope",
        headers={"Authorization": f"Bearer {token}"},
        json={"granted": True},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_consent_extra_field_returns_422(
    async_client: AsyncClient, applicant_with_consents: tuple[User, str]
) -> None:
    _user, token = applicant_with_consents
    resp = await async_client.patch(
        "/v1/me/consents/email_marketing",
        headers={"Authorization": f"Bearer {token}"},
        json={"granted": True, "extra": "nope"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_consent_requires_auth(async_client: AsyncClient) -> None:
    resp = await async_client.patch(
        "/v1/me/consents/email_marketing", json={"granted": True}
    )
    assert resp.status_code == 401
```

If the existing fixture pattern in `conftest.py` already provides a logged-in user with seeded consents, prefer reusing that. Read `tests/integration/conftest.py` once to confirm.

**Important fixture note:** `applicant_with_consents` calls `session.commit()` to push the savepoint state into the outer transaction so `async_client` (which routes through the same savepoint-bound session via dependency override) can see the writes. This is the standard pattern for tests that exercise an HTTP endpoint AND fixture-side DB writes. Per CLAUDE.md, calling `session.commit()` inside an integration test commits the savepoint, not the outer txn — teardown still rolls everything back.

- [ ] **Step 4: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration tests/integration/test_consents_routes.py
uv run pytest -v -m integration  # full suite
uv run ruff check src/ tests/
uv run mypy
```

- [ ] **Step 5: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/routes/consents.py api/src/kpa/app_factory.py \
        api/tests/integration/test_consents_routes.py
git commit -m "feat(api): GET + PATCH /v1/me/consents"
```

---

### Task 6: Sweep gates on consent + inbox excludes CANCELLED

**Files:**
- Modify: `api/src/kpa/workers/tasks/sweep_notifications.py`
- Modify: `api/src/kpa/routes/notifications.py`
- Create: `api/tests/integration/test_sweep_consent_gate.py`

- [ ] **Step 1: Add `_scope_for_notification`**

In `api/src/kpa/workers/tasks/sweep_notifications.py`, at module level (near the other private helpers), add:

```python
from kpa.db.models import ConsentScope


def _scope_for_notification(n: Notification) -> ConsentScope:
    if n.channel == NotificationChannel.EMAIL:
        return ConsentScope.EMAIL_TRANSACTIONAL
    if n.channel == NotificationChannel.IN_APP:
        return ConsentScope.IN_APP_NOTIFICATIONS
    raise ValueError(f"unmapped channel: {n.channel}")
```

- [ ] **Step 2: Insert the gate in `_dispatch_one`**

Locate `_dispatch_one` and the block where `user` is loaded (the existing `user = await session.get(User, n.user_id)` and the FAILED-if-missing branch). AFTER that block and BEFORE the `# --- Channel dispatch ---` line, insert:

```python
from kpa.consent import get_consent
from kpa.db.models import DEFAULT_CONSENTS

scope = _scope_for_notification(n)
try:
    granted = await get_consent(session, user=user, scope=scope)
except LookupError:
    # Backfill miss or DSR-delete cascade; default is the safe behavior.
    granted = DEFAULT_CONSENTS[scope]

if not granted:
    n.status = NotificationStatus.CANCELLED
    n.cancelled_at = func.now()
    n.last_error = f"consent_revoked:{scope.value}"
    _log.info(
        "sweep.cancelled-no-consent",
        notification_id=str(notification_id),
        user_id=str(user.id),
        scope=scope.value,
    )
    await session.commit()
    return
```

Imports should be at module top, not inside the function body. Move them up if the module currently imports `Notification`/etc. at module level.

- [ ] **Step 3: Exclude `CANCELLED` from the inbox**

Open `api/src/kpa/routes/notifications.py`. Find the existing `status != 'failed'` filter on `GET /v1/notifications`. Extend to also exclude `cancelled`:

```python
.where(
    Notification.user_id == user.id,
    Notification.deleted_at.is_(None),
    Notification.status.notin_([NotificationStatus.FAILED, NotificationStatus.CANCELLED]),
)
```

(Adjust to match the existing query's actual style — it may use `Notification.status != "failed"` or similar.)

- [ ] **Step 4: Integration test — revocation cancels next sweep**

Create `api/tests/integration/test_sweep_consent_gate.py`:

```python
"""Integration: revoke consent → next sweep marks pending row CANCELLED.

The sweep uses the real connection pool (not the test session), so the
test must commit consent state to the outer txn before triggering the
sweep. We use the savepoint-commit pattern (CLAUDE.md integration-test
guidance) — the conftest's session is savepoint-bound so this is safe.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.consent import seed_default_consents, set_consent
from kpa.db.models import (
    ConsentScope,
    Notification,
    NotificationChannel,
    NotificationStatus,
    User,
    UserRole,
)
from kpa.workers.tasks.sweep_notifications import _sweep_notifications_async


@pytest.mark.asyncio
async def test_revoked_email_consent_cancels_next_sweep(
    session: AsyncSession,
    sm,  # savepoint-bound sessionmaker fixture from conftest
    fake_email_channel,  # fake email channel fixture
) -> None:
    user = User(
        email=f"sw-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT
    )
    session.add(user)
    await session.flush()
    await seed_default_consents(session, user=user)

    # Revoke email_transactional.
    await set_consent(
        session,
        user=user,
        scope=ConsentScope.EMAIL_TRANSACTIONAL,
        granted=False,
    )

    # Queue a pending email notification.
    notif = Notification(
        user_id=user.id,
        kind="application.applied",
        channel=NotificationChannel.EMAIL,
        payload={"job_title": "Test Role"},
    )
    session.add(notif)
    await session.commit()  # commit savepoint so the sweep's separate session sees it

    await _sweep_notifications_async(
        sm=sm, email_channel=fake_email_channel, batch_size=10
    )

    # Re-fetch the notification — it must now be CANCELLED.
    refetched = (
        await session.execute(
            select(Notification).where(Notification.id == notif.id)
        )
    ).scalar_one()
    assert refetched.status == NotificationStatus.CANCELLED
    assert refetched.cancelled_at is not None
    assert refetched.last_error == "consent_revoked:email_transactional"
    # The fake channel must not have been called.
    assert fake_email_channel.sent == []
```

Required fixtures (`sm`, `fake_email_channel`) likely already exist in `conftest.py` for the existing sweep tests — read the existing `tests/integration/test_sweep_notifications*.py` (if it exists) to find the names and reuse. If they don't exist, the test must build them inline; ask for guidance.

- [ ] **Step 5: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration tests/integration/test_sweep_consent_gate.py
uv run pytest -v -m integration  # full suite must stay green
uv run ruff check src/ tests/
uv run mypy
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/workers/tasks/sweep_notifications.py \
        api/src/kpa/routes/notifications.py \
        api/tests/integration/test_sweep_consent_gate.py
git commit -m "feat(api): notifications sweep gates on consent; CANCELLED hidden from inbox"
```

---

### Task 7: Backfill CLI + CLAUDE.md + PR

**Files:**
- Create: `api/src/kpa/cli/seed_consents.py`
- Create: `api/tests/integration/test_seed_consents_cli.py`
- Modify: `api/pyproject.toml` (register script)
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read the existing seed CLI for shape**

Read `api/src/kpa/cli/seed_jobs.py`. Match: imports, the `_apply_in_session(session, report)` test seam, the `main()` entry point.

- [ ] **Step 2: Write the CLI**

Create `api/src/kpa/cli/seed_consents.py`:

```python
"""kpa-seed-consents — backfill default consents for users created before the
P4-B migration. Safe to re-run; seed_default_consents is idempotent.

Usage:
    uv run --env-file=.env kpa-seed-consents
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kpa.consent import seed_default_consents
from kpa.db.models import User
from kpa.settings import Settings

_log = structlog.get_logger(__name__)


@dataclass
class SeedReport:
    scanned: int = 0
    seeded_users: int = 0
    rows_inserted: int = 0
    skipped_already_seeded: int = 0
    user_ids_seeded: list[str] = field(default_factory=list)


async def _apply_in_session(session: AsyncSession, report: SeedReport) -> None:
    users = (
        await session.execute(select(User).where(User.deleted_at.is_(None)))
    ).scalars().all()
    report.scanned = len(users)
    for user in users:
        created = await seed_default_consents(session, user=user)
        if created:
            report.seeded_users += 1
            report.rows_inserted += len(created)
            report.user_ids_seeded.append(str(user.id))
        else:
            report.skipped_already_seeded += 1


async def _apply() -> SeedReport:
    settings = Settings()
    engine = create_async_engine(settings.db_url, echo=False)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    report = SeedReport()
    async with sm() as session:
        await _apply_in_session(session, report)
        await session.commit()
    await engine.dispose()
    return report


def main() -> None:
    report = asyncio.run(_apply())
    _log.info(
        "seed-consents.done",
        scanned=report.scanned,
        seeded_users=report.seeded_users,
        rows_inserted=report.rows_inserted,
        skipped=report.skipped_already_seeded,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Register the script**

Edit `api/pyproject.toml`. Find the existing `[project.scripts]` section:

```toml
[project.scripts]
kpa-seed-jobs = "kpa.cli.seed_jobs:main"
```

Add:

```toml
kpa-seed-consents = "kpa.cli.seed_consents:main"
```

- [ ] **Step 4: Integration test**

Create `api/tests/integration/test_seed_consents_cli.py`:

```python
"""Integration test for the kpa-seed-consents CLI's _apply_in_session
test seam. Mirrors test_seed_jobs_cli pattern.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.cli.seed_consents import SeedReport, _apply_in_session
from kpa.consent import seed_default_consents
from kpa.db.models import DEFAULT_CONSENTS, User, UserConsent, UserRole


@pytest.mark.asyncio
async def test_backfills_users_missing_consents(session: AsyncSession) -> None:
    pre_existing = User(
        email=f"pre-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT
    )
    session.add(pre_existing)
    await session.flush()
    # NO seed call — this is the legacy user.

    already_seeded = User(
        email=f"seeded-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT
    )
    session.add(already_seeded)
    await session.flush()
    await seed_default_consents(session, user=already_seeded)

    report = SeedReport()
    await _apply_in_session(session, report)

    assert report.scanned >= 2
    assert str(pre_existing.id) in report.user_ids_seeded
    assert str(already_seeded.id) not in report.user_ids_seeded

    pre_rows = (
        await session.execute(
            select(UserConsent).where(UserConsent.user_id == pre_existing.id)
        )
    ).scalars().all()
    assert len(pre_rows) == len(DEFAULT_CONSENTS)


@pytest.mark.asyncio
async def test_idempotent_rerun(session: AsyncSession) -> None:
    user = User(
        email=f"i-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT
    )
    session.add(user)
    await session.flush()

    r1 = SeedReport()
    await _apply_in_session(session, r1)
    inserted_first = r1.rows_inserted

    r2 = SeedReport()
    await _apply_in_session(session, r2)
    assert r2.rows_inserted == 0
    assert str(user.id) not in r2.user_ids_seeded
    assert inserted_first >= len(DEFAULT_CONSENTS)
```

- [ ] **Step 5: Add CLAUDE.md section**

Open `CLAUDE.md`. Find the `### Audit logs` section added in PR #25. AFTER that section, INSERT the new section:

```markdown
### Consent + notification-channel preferences

- **`user_consents` is the operational state**, `audit_logs` is the history. Every grant/revoke via `set_consent(...)` writes one audit row in the same txn. No-op flips (`granted=true → granted=true`) write no audit row — DPDP auditability is about state changes, not re-affirmations.
- **`ON DELETE CASCADE` on `user_id`** — opposite of `audit_logs` (SET NULL). Consent for a non-existent user is meaningless; the row vanishes with the user. The audit-log entries documenting their grants survive via `audit_logs.actor_user_id ON DELETE SET NULL`.
- **Eager seeding at signup.** `auth/service.py:_upsert_identity` calls `seed_default_consents(...)` on the new-user branch in the same txn. All later reads are simple SELECTs — no default-fallback logic in the hot path. Changing a default later affects only NEW signups; existing users' explicit values aren't unilaterally revoked.
- **`email_transactional` defaults to `true` at signup** — legally-borderline call. The signup UI MUST notify the user ("by signing up, you agree to receive service-related communications"); sub-project F's consent screen will own that copy.
- **Sweep gate.** `sweep_notifications._dispatch_one` looks up consent between the user load and the channel dispatch. No consent → `status=CANCELLED`, `cancelled_at=now()`, terminal. Re-granting does NOT resurrect cancelled rows.
- **`LookupError` fallback in the sweep.** If `get_consent` raises (means seeding was skipped — pre-P4-B user, or DSR-delete cascaded the row), the sweep falls back to `DEFAULT_CONSENTS[scope]`. The backfill CLI (`kpa-seed-consents`) closes the pre-P4-B gap for existing users.
- **`CANCELLED` is a Postgres native-enum value** added via `ALTER TYPE ... ADD VALUE` inside `op.get_context().autocommit_block()` (Alembic 0014). This is the canonical example of a future enum-extension migration. Note: Postgres does NOT support `DROP VALUE` — downgrading 0014 leaves `cancelled` in the type, which is harmless.
- **Inbox excludes `CANCELLED`.** `GET /v1/notifications` filters `status NOT IN ('failed', 'cancelled')`. The user explicitly didn't want these; they shouldn't surface.
- **Scopes are a `StrEnum` at the API boundary, plain TEXT in the DB.** Mirrors `audit_logs.action`. Reserved scopes ship in v0 with default `false` (WhatsApp, SMS, recruiter visibility, third-party sharing) so adding their impls later doesn't need an enum migration.
- **`set_consent` is the only path that writes a `consent.*` audit row.** Don't write audit rows for consent state changes by hand — the no-op-on-noop optimization is centralized.
```

- [ ] **Step 6: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration tests/integration/test_seed_consents_cli.py
uv run pytest -v -m integration  # full suite
uv run pytest -v -m "not integration"  # unit suite
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

All green.

- [ ] **Step 7: Commit + push + open PR**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/cli/seed_consents.py \
        api/pyproject.toml \
        api/tests/integration/test_seed_consents_cli.py \
        CLAUDE.md
git commit -m "feat(api): kpa-seed-consents backfill CLI + CLAUDE.md docs"

git push -u origin feat/p4-consent-channel-prefs
gh pr create --title "feat(api): P4-B consent + notification-channel preferences" --body "$(cat <<'EOF'
## Summary
Second P4 sub-project (of A→B→C in the approved DPDP plan).

- New `user_consents` table — one live row per `(user_id, scope)` — with seven v0 scopes (three active, four reserved). `ON DELETE CASCADE` on `user_id` (opposite of `audit_logs.actor_user_id`'s `SET NULL`).
- New `consent` helper module: `get_consent` / `set_consent` / `seed_default_consents`. All three caller-owns-the-txn; every state change writes through `audit_log()` from PR #25.
- Eager seeding at signup — `_upsert_identity` writes the seven rows + seven `consent.seeded` audit entries in the same txn.
- `GET` + `PATCH /v1/me/consents` — any authenticated user manages their own consents.
- Notifications sweep gates on consent. No consent → `status=CANCELLED`, terminal (re-granting does NOT resurrect). `LookupError` fallback to `DEFAULT_CONSENTS` covers pre-P4-B users + future DSR-delete cascade.
- `NotificationStatus.CANCELLED` added via `ALTER TYPE ... ADD VALUE` inside an Alembic autocommit block. Inbox endpoint excludes cancelled.
- `kpa-seed-consents` CLI backfills users created before this migration (idempotent).

Spec: `docs/superpowers/specs/2026-05-29-consent-channel-prefs-design.md`
Plan: `docs/superpowers/plans/2026-05-29-consent-channel-prefs.md`

## Why "no audit row on noop"

If a user PATCHes `{granted: true}` and current state is already `true`, we write no audit row. A regulator audit of "how many times did the user consent to marketing?" should not show inflated counts from accidental UI re-toggles. The `set_consent` helper centralizes this — never write `consent.*` audit rows by hand.

## Test plan
- [x] `uv run alembic upgrade head` / `downgrade -1` / `upgrade head` round-trip clean (including the autocommit-block enum extension)
- [x] `uv run pytest -m "not integration"` — N passed (consent helper signature tests included)
- [x] `uv run pytest -m integration` — N passed (6 helper + 5 routes + 1 sweep gate + 2 CLI = 14 new integration tests, plus the auth-test extension)
- [x] `uv run mypy` clean
- [x] `uv run ruff check` clean

## Backfill
After deploying:
```bash
uv run --env-file=.env kpa-seed-consents
```
Seeds defaults for any user created before this migration. Safe to re-run.

## Out of scope
- Flutter consent screens → sub-project F
- Marketing-email content → none exist yet; gating plumbing waits for them
- DSR-export of consent history → sub-project C will query `audit_logs WHERE action LIKE 'consent.%'`
- WhatsApp / SMS adapters → providers TBD per spec §14 #5

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review checklist

- [x] Every spec section maps to a task: §3 table → Task 1; §4 scopes → Task 1; §5 seeding → Task 4; §6 helper API → Tasks 2-3; §7 endpoints → Task 5; §8 sweep gate → Task 6; §9 backfill → Task 7; §10 docs → Task 7.
- [x] No placeholders. Every step shows actual code or actual commands.
- [x] `ConsentScope` enum values match across model, helper, tests, routes (7 values, three actively-defaulted-true, four reserved-default-false).
- [x] `request_id` flow is end-to-end (route → AuthService → `seed_default_consents` → audit row context).
- [x] `actor_user_id` (audit_logs) vs `user_id` (user_consents) FK semantics are opposite-and-load-bearing — both are documented in CLAUDE.md.
- [x] The autocommit-block migration pattern is documented in both the migration file and CLAUDE.md so future enum extensions follow it.
