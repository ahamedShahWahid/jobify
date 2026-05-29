# P4-E Admin Moderation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship the minimum admin surface — suspend/unsuspend users, view audit logs with filters, and a bootstrap CLI to elevate the first admin. Every admin action writes through `audit_log()` from PR #25.

**Architecture:** Migration 0016 adds `users.suspended_at` + `suspension_reason`. `auth/dependencies.py` extends `current_user` (401 `user_suspended`) + adds `_require_admin`. New `routes/admin.py` with 3 endpoints. New `scripts/grant_admin.py` CLI.

**Tech Stack:** FastAPI / async SQLAlchemy / Alembic / asyncpg / pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-admin-moderation-design.md`

---

## Files

**Create:**
- `api/src/kpa/db/migrations/versions/0016_user_suspension.py`
- `api/src/kpa/routes/admin.py`
- `api/src/kpa/scripts/grant_admin.py`
- `api/tests/integration/test_admin_suspend.py`
- `api/tests/integration/test_admin_audit_logs.py`
- `api/tests/integration/test_grant_admin_cli.py`

**Modify:**
- `api/src/kpa/db/models.py` — add the two columns on `User`.
- `api/src/kpa/auth/dependencies.py` — extend `current_user` for suspension; add `_require_admin`.
- `api/src/kpa/app_factory.py` — mount the new router.
- `api/pyproject.toml` — register `kpa-grant-admin`.
- `api/tests/integration/conftest.py` — fixture for an admin user + token (optional but helpful).
- `app/lib/data/api/refresh_on_401_interceptor.dart` — short-circuit on `user_suspended` (already short-circuits any non-`invalid_access_token`; verify and add a test).
- `app/lib/core/error/auth_slugs.dart` — add the new slug constant.
- `CLAUDE.md` — add the "Admin moderation" section per spec § 7.

---

### Task 1: Migration + model + dependency changes

**Files:**
- Create: `api/src/kpa/db/migrations/versions/0016_user_suspension.py`
- Modify: `api/src/kpa/db/models.py`, `api/src/kpa/auth/dependencies.py`

- [ ] **Step 1: Write the migration**

Read `api/src/kpa/db/migrations/versions/0015_dsr_nullable_pii_fields.py` for style. Then create `0016_user_suspension.py`:

```python
"""users.suspended_at + suspension_reason for admin moderation

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-29

Both nullable. suspended_at IS NULL <=> user is active. Clearing the
suspension always clears BOTH columns (admin tooling reads
suspension_reason IS NOT NULL as 'this user is suspended' defensively).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("suspended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="kpa",
    )
    op.add_column(
        "users",
        sa.Column("suspension_reason", sa.Text(), nullable=True),
        schema="kpa",
    )


def downgrade() -> None:
    op.drop_column("users", "suspension_reason", schema="kpa")
    op.drop_column("users", "suspended_at", schema="kpa")
```

- [ ] **Step 2: Round-trip the migration**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run alembic upgrade head
psql kpa -c "\d kpa.users" | grep suspend
uv run alembic downgrade -1
uv run alembic upgrade head
```

- [ ] **Step 3: Add the columns to the `User` model**

Open `api/src/kpa/db/models.py`. Find the `User` class. Add (near the other timestamps):

```python
suspended_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Verify `Text` and `DateTime` are imported at top of file (they are — `User` already uses them).

- [ ] **Step 4: Extend `current_user` for suspension**

Open `api/src/kpa/auth/dependencies.py`. Find the `current_user` function. Find the block:

```python
if user is None or user.deleted_at is not None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="user_not_found",
    )
```

Immediately AFTER it (before `request.state.current_user_id = ...`), add:

```python
if user.suspended_at is not None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="user_suspended",
    )
```

- [ ] **Step 5: Add `_require_admin`**

In the same file, after `_require_recruiter` (~line 89), add:

```python
async def _require_admin(user: User) -> User:
    """403 not_an_admin if the caller is not an admin."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_an_admin")
    return user
```

- [ ] **Step 6: Verify lint, types, tests**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run ruff check src/
uv run ruff format src/
uv run mypy
uv run pytest -m integration -q  # full suite must stay green (baseline 279)
```

- [ ] **Step 7: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/db/migrations/versions/0016_user_suspension.py \
        api/src/kpa/db/models.py \
        api/src/kpa/auth/dependencies.py
git commit -m "feat(api): users.suspended_at + _require_admin

Migration 0016 adds the two suspension columns (both nullable). current_user
rejects suspended users with 401 user_suspended (new slug — refresh
interceptor must NOT retry, mirrors user_not_found behavior).
_require_admin checks UserRole.ADMIN and returns 403 not_an_admin."
```

---

### Task 2: Admin endpoints + integration tests

**Files:**
- Create: `api/src/kpa/routes/admin.py`, `api/tests/integration/test_admin_suspend.py`, `api/tests/integration/test_admin_audit_logs.py`
- Modify: `api/src/kpa/app_factory.py` (mount router); optionally `tests/integration/conftest.py` (admin fixture).

- [ ] **Step 1: Write the router (suspend + unsuspend)**

Create `api/src/kpa/routes/admin.py`. Imports + suspend handlers:

```python
"""Admin moderation endpoints — /v1/admin/*.

All routes require ADMIN role. Layer order per CLAUDE.md error-ladder
convention: current_user → 401 invariants (already done by the dep) →
_require_admin → 403 not_an_admin → DB read for the target resource.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.auth.dependencies import _require_admin, current_user
from kpa.db.models import AuditLog, User
from kpa.db.session import get_session

router = APIRouter(prefix="/v1/admin", tags=["admin"])
_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic shapes
# ---------------------------------------------------------------------------


class _UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    role: str
    suspended_at: datetime | None
    suspension_reason: str | None


class SuspendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=255)


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_role: str
    action: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    context: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# POST /v1/admin/users/{user_id}/suspend
# ---------------------------------------------------------------------------


@router.post("/users/{user_id}/suspend", response_model=_UserRead)
async def suspend_user(
    user_id: uuid.UUID,
    body: SuspendRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> _UserRead:
    await _require_admin(user)

    if user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot_suspend_self")

    target = await session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="user_not_found")

    now = func.now()
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            suspended_at=now,
            suspension_reason=body.reason,
            updated_at=now,
        )
    )

    await audit_log(
        session,
        action="admin.user.suspended",
        actor=user,
        resource_type="user",
        resource_id=user_id,
        context={
            "request_id": request.state.request_id,
            "reason": body.reason,
            "target_user_role": target.role.value,
        },
    )

    await session.commit()

    refreshed = await session.get(User, user_id)
    assert refreshed is not None
    _log.info(
        "admin.user-suspended",
        admin_user_id=str(user.id),
        target_user_id=str(user_id),
        reason=body.reason,
    )
    return _UserRead.model_validate(refreshed)


# ---------------------------------------------------------------------------
# DELETE /v1/admin/users/{user_id}/suspend
# ---------------------------------------------------------------------------


@router.delete("/users/{user_id}/suspend", response_model=_UserRead)
async def unsuspend_user(
    user_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> _UserRead:
    await _require_admin(user)

    target = await session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="user_not_found")

    # No-op on noop — same pattern as set_consent in PR #26.
    if target.suspended_at is None and target.suspension_reason is None:
        return _UserRead.model_validate(target)

    now = func.now()
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            suspended_at=None,
            suspension_reason=None,
            updated_at=now,
        )
    )

    await audit_log(
        session,
        action="admin.user.unsuspended",
        actor=user,
        resource_type="user",
        resource_id=user_id,
        context={"request_id": request.state.request_id},
    )

    await session.commit()

    refreshed = await session.get(User, user_id)
    assert refreshed is not None
    _log.info(
        "admin.user-unsuspended",
        admin_user_id=str(user.id),
        target_user_id=str(user_id),
    )
    return _UserRead.model_validate(refreshed)


# ---------------------------------------------------------------------------
# GET /v1/admin/audit-logs
# ---------------------------------------------------------------------------


def _encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    payload = {"c": created_at.isoformat(), "i": str(row_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return datetime.fromisoformat(payload["c"]), uuid.UUID(payload["i"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid_cursor") from exc


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    action: str | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditLogListResponse:
    await _require_admin(user)

    stmt = select(AuditLog)
    filters = []
    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    if resource_type is not None:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        filters.append(AuditLog.resource_id == resource_id)
    if action is not None:
        filters.append(AuditLog.action == action)
    if from_ is not None:
        filters.append(AuditLog.created_at >= from_)
    if to is not None:
        filters.append(AuditLog.created_at <= to)

    if cursor is not None:
        cursor_created, cursor_id = _decode_cursor(cursor)
        # Tuple comparison: (created_at, id) < (cursor_created, cursor_id).
        filters.append(
            (AuditLog.created_at < cursor_created)
            | (
                (AuditLog.created_at == cursor_created)
                & (AuditLog.id < cursor_id)
            )
        )

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = (
        stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit + 1)
    )
    rows = (await session.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    items = [AuditLogRead.model_validate(r) for r in rows[:limit]]
    next_cursor = (
        _encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id)
        if has_more
        else None
    )
    return AuditLogListResponse(items=items, next_cursor=next_cursor)
```

- [ ] **Step 2: Mount the router**

In `api/src/kpa/app_factory.py`, find the existing `from kpa.routes import dsr as dsr_routes` (added by PR #27). Add:

```python
from kpa.routes import admin as admin_routes
# ... with the others:
app.include_router(admin_routes.router)
```

- [ ] **Step 3: Add admin fixture to conftest**

In `api/tests/integration/conftest.py`, find the existing `applicant_user_and_token` fixture (around line 335). Add a sibling:

```python
@pytest_asyncio.fixture
async def admin_user_and_token(session: AsyncSession) -> tuple[User, str]:
    user = User(email=f"admin-{uuid4().hex[:8]}@example.com", role=UserRole.ADMIN)
    session.add(user)
    await session.flush()
    token = mint_access_token(
        user_id=user.id,
        role=user.role.value,
        secret="x" * 32,
        ttl_seconds=600,
    )
    return user, token
```

Verify the `uuid4` import — if it's not at the top of conftest, add `from uuid import uuid4`.

- [ ] **Step 4: Integration tests — suspend / unsuspend**

Create `api/tests/integration/test_admin_suspend.py`:

```python
"""Integration tests for /v1/admin/users/{id}/suspend (POST + DELETE)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import mint_access_token
from kpa.db.models import AuditLog, User, UserRole


async def _make_user(session: AsyncSession, role: UserRole = UserRole.APPLICANT) -> User:
    user = User(email=f"u-{uuid4().hex[:8]}@example.com", role=role)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_suspend_user_happy_path(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    target = await _make_user(session)
    await session.commit()

    resp = await async_client.post(
        f"/v1/admin/users/{target.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "spam_signup"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suspended_at"] is not None
    assert body["suspension_reason"] == "spam_signup"

    refreshed = (
        await session.execute(select(User).where(User.id == target.id))
    ).scalar_one()
    assert refreshed.suspended_at is not None
    assert refreshed.suspension_reason == "spam_signup"

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == admin.id,
                AuditLog.action == "admin.user.suspended",
                AuditLog.resource_id == target.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].context["reason"] == "spam_signup"


@pytest.mark.asyncio
async def test_suspend_self_blocked(
    async_client: AsyncClient,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    resp = await async_client.post(
        f"/v1/admin/users/{admin.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "oops"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "cannot_suspend_self"


@pytest.mark.asyncio
async def test_suspend_unknown_user_404(
    async_client: AsyncClient,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    resp = await async_client.post(
        f"/v1/admin/users/{uuid4()}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suspend_requires_admin_role(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _applicant, token = applicant_user_and_token
    resp = await async_client.post(
        f"/v1/admin/users/{uuid4()}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_admin"


@pytest.mark.asyncio
async def test_suspended_user_gets_401_user_suspended_on_subsequent_request(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, admin_token = admin_user_and_token

    # Make a victim user with their own token.
    victim = await _make_user(session)
    victim_token = mint_access_token(
        user_id=victim.id, role=victim.role.value, secret="x" * 32, ttl_seconds=600
    )
    await session.commit()

    # Suspend victim via admin.
    suspend_resp = await async_client.post(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "abuse"},
    )
    assert suspend_resp.status_code == 200

    # Victim hits an authenticated endpoint with their token → 401 user_suspended.
    me_resp = await async_client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {victim_token}"},
    )
    assert me_resp.status_code == 401
    assert me_resp.json()["detail"] == "user_suspended"


@pytest.mark.asyncio
async def test_unsuspend_user_clears_and_audits(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    victim = await _make_user(session)
    await session.commit()

    await async_client.post(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "abuse"},
    )

    resp = await async_client.delete(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["suspended_at"] is None
    assert resp.json()["suspension_reason"] is None

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == admin.id,
                AuditLog.action == "admin.user.unsuspended",
                AuditLog.resource_id == victim.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_unsuspend_already_active_is_noop_no_audit(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    admin, token = admin_user_and_token
    victim = await _make_user(session)
    await session.commit()

    resp = await async_client.delete(
        f"/v1/admin/users/{victim.id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == admin.id,
                AuditLog.action == "admin.user.unsuspended",
            )
        )
    ).scalars().all()
    assert audits == []
```

- [ ] **Step 5: Integration tests — audit-logs viewer**

Create `api/tests/integration/test_admin_audit_logs.py`:

```python
"""Integration tests for GET /v1/admin/audit-logs."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.db.models import User, UserRole


async def _seed_audit_rows(session: AsyncSession, *, count: int = 5) -> User:
    """Make a user + N audit_logs rows tied to them."""
    user = User(email=f"u-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    for i in range(count):
        await audit_log(
            session,
            action=f"test.event_{i}",
            actor=user,
            resource_type="test",
            resource_id=uuid4(),
            context={"i": i},
        )
    return user


@pytest.mark.asyncio
async def test_audit_logs_returns_filtered_by_actor(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    actor = await _seed_audit_rows(session, count=3)
    # Noise: another user's audit rows.
    other = User(email=f"n-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(other)
    await session.flush()
    await audit_log(
        session,
        action="other.event",
        actor=other,
        resource_type="test",
    )
    await session.commit()

    resp = await async_client.get(
        f"/v1/admin/audit-logs?actor_user_id={actor.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    actions = sorted(it["action"] for it in body["items"])
    assert actions == ["test.event_0", "test.event_1", "test.event_2"]


@pytest.mark.asyncio
async def test_audit_logs_filtered_by_action(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    user = await _seed_audit_rows(session, count=5)
    await session.commit()

    resp = await async_client.get(
        "/v1/admin/audit-logs?action=test.event_2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["action"] == "test.event_2"


@pytest.mark.asyncio
async def test_audit_logs_pagination(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _admin, token = admin_user_and_token
    actor = await _seed_audit_rows(session, count=5)
    await session.commit()

    page1 = await async_client.get(
        f"/v1/admin/audit-logs?actor_user_id={actor.id}&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    page2 = await async_client.get(
        f"/v1/admin/audit-logs?actor_user_id={actor.id}&limit=2&cursor={body1['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["items"]) == 2
    # No overlap.
    page1_ids = {it["id"] for it in body1["items"]}
    page2_ids = {it["id"] for it in body2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_audit_logs_requires_admin(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _applicant, token = applicant_user_and_token
    resp = await async_client.get(
        "/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration tests/integration/test_admin_suspend.py tests/integration/test_admin_audit_logs.py
uv run pytest -m integration -q  # full suite — must stay green (was 279)
uv run pytest -m "not integration" -q
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

Expected: 11 new integration tests pass. Full suite ~290.

- [ ] **Step 7: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/routes/admin.py \
        api/src/kpa/app_factory.py \
        api/tests/integration/test_admin_suspend.py \
        api/tests/integration/test_admin_audit_logs.py \
        api/tests/integration/conftest.py
git commit -m "feat(api): admin suspend/unsuspend + audit-logs viewer

POST /v1/admin/users/{id}/suspend (body: reason) sets the columns +
writes admin.user.suspended audit row. DELETE clears + writes
admin.user.unsuspended (no-op on noop, no audit). GET /v1/admin/audit-logs
with cursor pagination + filters on actor_user_id, resource_type,
resource_id, action, from, to."
```

---

### Task 3: `kpa-grant-admin` CLI

**Files:**
- Create: `api/src/kpa/scripts/grant_admin.py`, `api/tests/integration/test_grant_admin_cli.py`
- Modify: `api/pyproject.toml`

- [ ] **Step 1: Read the existing CLI for the pattern**

```bash
cat /Users/ahamadshah/ahamed_personal/kpa/api/src/kpa/scripts/seed_consents.py
```

Match: imports, `_apply_in_session(session, ...)` test seam, `main()` entry point, structured logging on completion.

- [ ] **Step 2: Write the CLI**

Create `api/src/kpa/scripts/grant_admin.py`:

```python
"""kpa-grant-admin — bootstrap CLI to elevate a user to ADMIN role.

Usage:
    uv run --env-file=.env kpa-grant-admin <email>

Idempotent — if the user is already ADMIN, logs 'no change' and exits 0.
Exits 1 if no live user matches the email.

Writes one auth.role.granted audit row with actor_user_id=NULL (system
actor — there's no admin user logged in to grant the FIRST admin).
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kpa.audit import audit_log
from kpa.db.models import User, UserRole
from kpa.settings import Settings

_log = structlog.get_logger(__name__)


@dataclass
class GrantReport:
    matched: bool
    already_admin: bool
    user_id: str | None
    from_role: str | None


async def _apply_in_session(session: AsyncSession, *, email: str) -> GrantReport:
    user = (
        await session.execute(
            select(User).where(
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if user is None:
        return GrantReport(matched=False, already_admin=False, user_id=None, from_role=None)

    if user.role == UserRole.ADMIN:
        return GrantReport(
            matched=True, already_admin=True, user_id=str(user.id), from_role="admin"
        )

    from_role = user.role.value
    user.role = UserRole.ADMIN
    await session.flush()

    await audit_log(
        session,
        action="auth.role.granted",
        actor=None,
        actor_role="system",
        resource_type="user",
        resource_id=user.id,
        context={
            "from_role": from_role,
            "to_role": "admin",
            "by": "kpa-grant-admin-cli",
        },
    )

    return GrantReport(
        matched=True, already_admin=False, user_id=str(user.id), from_role=from_role
    )


async def _apply(email: str) -> GrantReport:
    settings = Settings()
    engine = create_async_engine(settings.db_url, echo=False)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        report = await _apply_in_session(session, email=email)
        await session.commit()
    await engine.dispose()
    return report


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: kpa-grant-admin <email>", file=sys.stderr)
        sys.exit(2)

    email = sys.argv[1].strip()
    report = asyncio.run(_apply(email))

    if not report.matched:
        _log.error("grant-admin.user-not-found", email=email)
        sys.exit(1)

    if report.already_admin:
        _log.info("grant-admin.no-change", email=email, user_id=report.user_id)
        return

    _log.info(
        "grant-admin.done",
        email=email,
        user_id=report.user_id,
        from_role=report.from_role,
        to_role="admin",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Register the script**

In `api/pyproject.toml`, find `[project.scripts]`. Add:

```toml
kpa-grant-admin = "kpa.scripts.grant_admin:main"
```

Run `uv sync`.

- [ ] **Step 4: Integration test**

Create `api/tests/integration/test_grant_admin_cli.py`:

```python
"""Integration tests for the kpa-grant-admin CLI's _apply_in_session seam."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import AuditLog, User, UserRole
from kpa.scripts.grant_admin import _apply_in_session


@pytest.mark.asyncio
async def test_grants_admin_to_existing_user(session: AsyncSession) -> None:
    email = f"a-{uuid4().hex[:8]}@example.com"
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()

    report = await _apply_in_session(session, email=email)

    assert report.matched
    assert not report.already_admin
    assert report.from_role == "applicant"

    refreshed = (
        await session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.role == UserRole.ADMIN

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == user.id,
                AuditLog.action == "auth.role.granted",
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].actor_user_id is None  # system actor
    assert audits[0].actor_role == "system"
    assert audits[0].context["from_role"] == "applicant"


@pytest.mark.asyncio
async def test_idempotent_on_already_admin(session: AsyncSession) -> None:
    email = f"a-{uuid4().hex[:8]}@example.com"
    user = User(email=email, role=UserRole.ADMIN)
    session.add(user)
    await session.flush()

    report = await _apply_in_session(session, email=email)
    assert report.matched
    assert report.already_admin

    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == user.id,
                AuditLog.action == "auth.role.granted",
            )
        )
    ).scalars().all()
    assert audits == []  # No-op writes no audit row.


@pytest.mark.asyncio
async def test_unknown_email_reports_unmatched(session: AsyncSession) -> None:
    report = await _apply_in_session(session, email="ghost@example.com")
    assert not report.matched
    assert report.user_id is None
```

- [ ] **Step 5: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv sync
uv run pytest -v -m integration tests/integration/test_grant_admin_cli.py
uv run pytest -m integration -q
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

Smoke run (will exit 1 unless there's a live user with that email — that's expected):

```bash
uv run kpa-grant-admin nonexistent@example.com
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/scripts/grant_admin.py \
        api/pyproject.toml \
        api/uv.lock \
        api/tests/integration/test_grant_admin_cli.py
git commit -m "feat(api): kpa-grant-admin bootstrap CLI

Elevates a user to ADMIN role by email. Idempotent — already-admin users
are a no-op. Writes one auth.role.granted audit row with actor_user_id=NULL
(system actor) per the audit-logs spec convention for cron/CLI actors."
```

---

### Task 4: Flutter `user_suspended` slug + CLAUDE.md + PR

**Files:**
- Modify: `app/lib/core/error/auth_slugs.dart`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the slug constant**

Open `app/lib/core/error/auth_slugs.dart`. Add `static const userSuspended = 'user_suspended';` next to the existing slug constants.

The refresh interceptor (`app/lib/data/api/refresh_on_401_interceptor.dart`) ALREADY short-circuits to sign-out for any 401 with `detail != invalid_access_token` — see PR #24. So no interceptor change is needed. The new slug just gets a Dart-side name so future error-mapping can identify it specifically.

- [ ] **Step 2: CLAUDE.md update**

Open `CLAUDE.md`. Find the `### Auth + JWT invariants` section. Use the spec §7 content — insert the new `### Admin moderation` section AFTER the JWT invariants section, BEFORE the next `###` header. Lift verbatim from spec §7.

- [ ] **Step 3: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add app/lib/core/error/auth_slugs.dart CLAUDE.md
git commit -m "docs+app: user_suspended slug constant + CLAUDE.md admin moderation"
```

- [ ] **Step 4: Push + PR**

```bash
git push -u origin feat/p4-admin-moderation
gh pr create --title "feat(api): P4-E admin moderation (suspend, audit viewer, grant CLI)" --body "$(cat <<'EOF'
## Summary
Fifth P4 sub-project. Builds on PR #25's audit_logs substrate; every admin action writes through `audit_log()`.

- New columns: \`users.suspended_at\` + \`users.suspension_reason\` (migration 0016).
- \`current_user\` rejects suspended users with new 401 slug \`user_suspended\`. Refresh interceptor already short-circuits to sign-out on non-\`invalid_access_token\` 401s (PR #24), so suspended users get the right Flutter behavior for free.
- \`POST /v1/admin/users/{id}/suspend\` body \`{reason}\` — sets state + writes \`admin.user.suspended\` audit row. Self-suspension blocked with 400 \`cannot_suspend_self\`.
- \`DELETE /v1/admin/users/{id}/suspend\` — clears state + writes \`admin.user.unsuspended\` audit row. No-op on already-active user (no audit).
- \`GET /v1/admin/audit-logs\` — cursor-paginated, filters on actor/resource/action/from/to.
- \`kpa-grant-admin <email>\` bootstrap CLI — needed because there's no admin to grant admin via a route on day 0.

## Why CLI for granting admin (and not a route)

Chicken-and-egg: before the first admin exists, no one can call \`/v1/admin/users/{id}/grant-admin\`. CLI is the only bootstrap. Once an admin exists, a future PR can ship a grant-admin route.

## Test plan
- [x] Migration 0016 round-trip clean
- [x] \`uv run pytest -m integration tests/integration/test_admin_suspend.py\` — 7/7 pass
- [x] \`uv run pytest -m integration tests/integration/test_admin_audit_logs.py\` — 4/4 pass
- [x] \`uv run pytest -m integration tests/integration/test_grant_admin_cli.py\` — 3/3 pass
- [x] Full integration suite stays green (279 → 293)
- [x] \`uv run mypy\` clean
- [x] \`uv run ruff check\` clean

## Out of scope
- Admin Flutter/web UI — admins curl the endpoints today
- Job unpublish endpoint (\`admin.job.unpublished\` reserved)
- Admin-initiated DSR-export / DSR-delete of another user
- MFA for admins (sub-project G)
- Bulk admin operations

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Print the PR URL.

---

## Self-review checklist

- [x] Spec sections map to tasks: §3 schema → Task 1; §3.1 current_user → Task 1; §4 _require_admin → Task 1; §5 endpoints → Task 2; §6 CLI → Task 3; §7 docs → Task 4.
- [x] No placeholders. Each step has actual code or actual commands.
- [x] Self-suspend guard is in BOTH the spec §5.1 acceptance ladder AND the route AND the test.
- [x] Unsuspend no-op-on-noop matches the consent helper's pattern (no spurious audit rows).
- [x] CLI writes `actor=None, actor_role="system"` per the audit-logs convention for cron/CLI actors.
- [x] `user_suspended` slug surfaces in the Dart constants for future error-mapping use.
