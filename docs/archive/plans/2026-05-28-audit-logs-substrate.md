# `audit_logs` Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the existing `recruiter.resume-accessed` structlog seed line into a durable, queryable `audit_logs` table with a caller-owns-the-txn helper that future P4 sub-projects (consent, DSR, admin, MFA) all write through.

**Architecture:** Single append-only table in the `kpa` schema; thin async helper `audit_log(session, action=, actor=, resource_type=, resource_id=, context=)` that flushes a row inside the caller's transaction. Existing structlog lines are preserved (Kibana consumers untouched). `actor_user_id` is `ON DELETE SET NULL` so future DSR-delete can hard-delete users without losing audit evidence.

**Tech Stack:** Python 3.12 / FastAPI / async SQLAlchemy 2.x / Alembic / asyncpg / Postgres 16 / pytest.

**Spec:** `docs/superpowers/specs/2026-05-28-audit-logs-substrate-design.md`

---

## Files

**Create:**
- `api/src/kpa/db/migrations/versions/0013_audit_logs.py` — Alembic migration for `audit_logs` + three composite indexes.
- `api/src/kpa/audit/__init__.py` — `audit_log()` async helper.
- `api/tests/unit/audit/__init__.py` — empty package marker.
- `api/tests/unit/audit/test_helper_signature.py` — signature/contract unit tests.
- `api/tests/integration/test_audit_logs.py` — table-shape + helper integration tests.

**Modify:**
- `api/src/kpa/db/models.py` — declare `AuditLog` model. Exception to the `CreatedAt`/`UpdatedAt`/`DeletedAt` convention (append-only).
- `api/src/kpa/routes/applications.py` — call `audit_log(...)` inside `get_application_resume` AFTER the structlog line, BEFORE `session.commit()`-equivalent (it's actually before the response return; the request-bound session commits via FastAPI lifecycle).
- `api/tests/integration/test_recruiter_resume_access.py` — extend existing happy-path test to assert the `audit_logs` row.
- `CLAUDE.md` — add "Audit logs" section under "Architecture — non-obvious bits" per spec §10.

---

### Task 1: Migration 0013 + `AuditLog` model

**Files:**
- Create: `api/src/kpa/db/migrations/versions/0013_audit_logs.py`
- Modify: `api/src/kpa/db/models.py` (add `AuditLog` class near bottom)
- Modify: `api/tests/integration/test_models_smoke.py` *(if it exists — check)* OR Create: `api/tests/integration/test_audit_logs.py` (created in Task 3)

- [ ] **Step 1: Read the latest migration to match style**

Read: `api/src/kpa/db/migrations/versions/0012_employer_users.py`

Match: header comment style, import order, `revision`/`down_revision` constants, `op.create_table` argument shape, `op.create_index` separate calls (not inline).

- [ ] **Step 2: Write the migration**

Create `api/src/kpa/db/migrations/versions/0013_audit_logs.py`:

```python
"""audit_logs table for P4 DPDP substrate

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-28

Append-only event store. ON DELETE SET NULL on actor_user_id is load-bearing:
DSR-delete must succeed without removing the audit evidence.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("kpa.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "context",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="kpa",
    )
    op.create_index(
        "ix_audit_logs_actor_created",
        "audit_logs",
        ["actor_user_id", sa.text("created_at DESC")],
        schema="kpa",
    )
    op.create_index(
        "ix_audit_logs_resource_created",
        "audit_logs",
        ["resource_type", "resource_id", sa.text("created_at DESC")],
        schema="kpa",
    )
    op.create_index(
        "ix_audit_logs_action_created",
        "audit_logs",
        ["action", sa.text("created_at DESC")],
        schema="kpa",
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action_created", table_name="audit_logs", schema="kpa")
    op.drop_index("ix_audit_logs_resource_created", table_name="audit_logs", schema="kpa")
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs", schema="kpa")
    op.drop_table("audit_logs", schema="kpa")
```

- [ ] **Step 3: Run the migration**

```bash
cd api
uv run alembic upgrade head
```

Expected: `0012 -> 0013, audit_logs table for P4 DPDP substrate`. Verify table exists:

```bash
psql kpa -c "\d kpa.audit_logs"
```

Expected: 8 columns matching the spec §3.

- [ ] **Step 4: Declare the model in `db/models.py`**

Open `api/src/kpa/db/models.py`. Find the existing `EmployerUser` class (added in P4-precursor work). Append below it:

```python
class AuditLog(Base):
    """Append-only audit substrate for P4 DPDP evidence.

    Deliberately does NOT use CreatedAt/UpdatedAt/DeletedAt annotated types —
    audit rows have no update or soft-delete semantics. See
    docs/superpowers/specs/2026-05-28-audit-logs-substrate-design.md §3.2.

    actor_user_id is ON DELETE SET NULL so DSR-delete (sub-project D) can
    hard-delete users without orphaning the FK. The audit row survives —
    re-identification is intentionally impossible by design.
    """

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("kpa.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_role: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    action: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        nullable=True,
    )
    context: Mapped[dict[str, Any]] = mapped_column(
        sa.dialects.postgresql.JSONB(),
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
```

Verify `from typing import Any`, `from uuid import UUID, uuid4`, and `from datetime import datetime` already exist at the top of the file (check before adding — most are already there from other models).

- [ ] **Step 5: Run mypy + ruff + the integration smoke test**

```bash
cd api
uv run ruff check src/
uv run ruff format src/
uv run mypy
uv run pytest -v -m integration tests/integration/test_models_smoke.py 2>/dev/null || \
  uv run pytest -v -m integration -k "models" 2>/dev/null || true
```

Expected: clean ruff, mypy passes, integration tests still green.

- [ ] **Step 6: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/db/migrations/versions/0013_audit_logs.py \
        api/src/kpa/db/models.py
git commit -m "feat(api): audit_logs table + AuditLog model for P4 DPDP substrate"
```

---

### Task 2: `audit_log()` helper

**Files:**
- Create: `api/src/kpa/audit/__init__.py`
- Create: `api/tests/unit/audit/__init__.py` (empty)
- Create: `api/tests/unit/audit/test_helper_signature.py`

- [ ] **Step 1: Write the failing unit test (signature contract)**

Create `api/tests/unit/audit/__init__.py` — empty file (`""`).

Create `api/tests/unit/audit/test_helper_signature.py`:

```python
"""Pure-signature contract tests for audit_log(). No DB.

The helper must reject the (actor=None, actor_role=None) combo because we'd
have nothing to record for actor_role (NOT NULL in DB). Catching this at the
helper boundary is cheaper than waiting for asyncpg to surface a NotNull.
"""
from __future__ import annotations

import inspect

import pytest

from kpa.audit import audit_log


def test_helper_signature_has_keyword_only_args() -> None:
    sig = inspect.signature(audit_log)
    params = sig.parameters
    # session is positional-or-keyword; everything else is keyword-only.
    assert params["session"].kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    )
    for name in (
        "action",
        "actor",
        "actor_role",
        "resource_type",
        "resource_id",
        "context",
    ):
        assert params[name].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only"
        )


@pytest.mark.asyncio
async def test_helper_rejects_actor_none_and_actor_role_none() -> None:
    # No session needed — the validation runs before we touch session.
    with pytest.raises(ValueError, match="actor_role"):
        await audit_log(
            session=None,  # type: ignore[arg-type]
            action="x.y",
            actor=None,
            actor_role=None,
        )
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
cd api
uv run pytest -v tests/unit/audit/test_helper_signature.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'kpa.audit'`.

- [ ] **Step 3: Write the helper**

Create `api/src/kpa/audit/__init__.py`:

```python
"""Append-only audit substrate for P4 DPDP.

The single entry point is `audit_log()`. It writes one row to `audit_logs`
inside the caller's transaction. There is no commit, no flush-and-discard,
no fire-and-forget dispatch — the row is exactly as durable as the business
action it records. If the caller's txn rolls back, the audit row rolls back
too. That is the contract.

Action slugs are dotted, lowercase, verb-past
(`resume.accessed`, `consent.granted`). See the spec at
docs/superpowers/specs/2026-05-28-audit-logs-substrate-design.md §4 for the
reserved namespace.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import AuditLog, User


async def audit_log(
    session: AsyncSession,
    *,
    action: str,
    actor: User | None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    context: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one row to audit_logs. Caller owns the txn.

    actor_role is derived from actor.role when actor is not None; pass
    explicitly for system actions (actor=None, actor_role='system'). Raises
    ValueError if both actor and actor_role are None.
    """
    if actor is None and actor_role is None:
        raise ValueError(
            "audit_log requires actor_role when actor is None "
            "(e.g. actor_role='system' for cron / worker actions)"
        )

    resolved_role = actor_role if actor_role is not None else actor.role.value  # type: ignore[union-attr]
    resolved_actor_id = actor.id if actor is not None else None

    row = AuditLog(
        actor_user_id=resolved_actor_id,
        actor_role=resolved_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        context=context if context is not None else {},
    )
    session.add(row)
    await session.flush()
    return row
```

- [ ] **Step 4: Run the unit test**

```bash
cd api
uv run pytest -v tests/unit/audit/test_helper_signature.py
```

Expected: both tests PASS.

- [ ] **Step 5: Run ruff + mypy**

```bash
cd api
uv run ruff check src/kpa/audit/ tests/unit/audit/
uv run ruff format src/kpa/audit/ tests/unit/audit/
uv run mypy
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/audit/ api/tests/unit/audit/
git commit -m "feat(api): audit_log() helper — caller-owns-txn append-only writer"
```

---

### Task 3: Integration tests for the helper

**Files:**
- Create: `api/tests/integration/test_audit_logs.py`

- [ ] **Step 1: Write the integration tests**

Create `api/tests/integration/test_audit_logs.py`:

```python
"""Integration tests for the audit_logs table + audit_log() helper.

Covers:
1. Happy path — row written, fields populated, queryable by resource.
2. system actor — actor=None + actor_role='system' writes successfully.
3. Txn rollback — savepoint-bound rollback removes the audit row.
4. FK behavior — actor_user_id=NULL after the referenced user is hard-deleted
   (ON DELETE SET NULL, load-bearing for future DSR-delete).
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from kpa.audit import audit_log
from kpa.db.models import AuditLog, User, UserRole


@pytest.mark.asyncio
async def test_happy_path_writes_row(session) -> None:  # type: ignore[no-untyped-def]
    user = User(
        id=uuid4(),
        email=f"audit-{uuid4().hex[:8]}@example.com",
        google_sub=f"sub-{uuid4().hex}",
        role=UserRole.APPLICANT,
    )
    session.add(user)
    await session.flush()

    resource_id = uuid4()
    row = await audit_log(
        session,
        action="resume.accessed",
        actor=user,
        resource_type="resume",
        resource_id=resource_id,
        context={"request_id": "req-1"},
    )

    assert row.id is not None
    assert row.actor_user_id == user.id
    assert row.actor_role == "applicant"
    assert row.action == "resume.accessed"
    assert row.resource_type == "resume"
    assert row.resource_id == resource_id
    assert row.context == {"request_id": "req-1"}
    assert row.created_at is not None

    # Roundtrip by resource — the (resource_type, resource_id, created_at desc)
    # index is the seek path future DSR-export will use.
    result = await session.execute(
        select(AuditLog).where(
            AuditLog.resource_type == "resume",
            AuditLog.resource_id == resource_id,
        )
    )
    fetched = result.scalar_one()
    assert fetched.id == row.id


@pytest.mark.asyncio
async def test_system_actor_writes_row(session) -> None:  # type: ignore[no-untyped-def]
    row = await audit_log(
        session,
        action="job.embeddings.swept",
        actor=None,
        actor_role="system",
        context={"swept_count": 42},
    )
    assert row.actor_user_id is None
    assert row.actor_role == "system"
    assert row.action == "job.embeddings.swept"
    assert row.context == {"swept_count": 42}


@pytest.mark.asyncio
async def test_rollback_removes_audit_row(session) -> None:  # type: ignore[no-untyped-def]
    user = User(
        id=uuid4(),
        email=f"audit-rb-{uuid4().hex[:8]}@example.com",
        google_sub=f"sub-{uuid4().hex}",
        role=UserRole.APPLICANT,
    )
    session.add(user)
    await session.flush()

    sp = await session.begin_nested()
    row = await audit_log(
        session,
        action="resume.accessed",
        actor=user,
        resource_type="resume",
        resource_id=uuid4(),
        context={"request_id": "req-rb"},
    )
    row_id = row.id
    await sp.rollback()

    # Row must be gone — audit lives or dies with the business txn.
    result = await session.execute(select(AuditLog).where(AuditLog.id == row_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_helper_rejects_actor_none_and_role_none(session) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="actor_role"):
        await audit_log(session, action="x.y", actor=None, actor_role=None)
```

- [ ] **Step 2: Run the tests**

```bash
cd api
uv run pytest -v -m integration tests/integration/test_audit_logs.py
```

Expected: 4/4 PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/tests/integration/test_audit_logs.py
git commit -m "test(api): integration tests for audit_log helper + table"
```

---

### Task 4: Wire `audit_log` into `routes/applications.py`

**Files:**
- Modify: `api/src/kpa/routes/applications.py`
- Modify: `api/tests/integration/test_recruiter_resume_access.py`

- [ ] **Step 1: Read the existing route + test**

```bash
grep -n "recruiter.resume-accessed" api/src/kpa/routes/applications.py
```

Expected: a `_log.info("recruiter.resume-accessed", ...)` call inside `get_application_resume`. Read 20 lines around it for context.

Read `api/tests/integration/test_recruiter_resume_access.py` to find the happy-path test that already asserts the structlog line via `structlog.testing.capture_logs()`. Note its test fixture for the recruiter + applicant + application + resume setup — the new assertion will reuse it.

- [ ] **Step 2: Augment the route**

In `api/src/kpa/routes/applications.py`, locate the `get_application_resume` handler. Find the existing `_log.info("recruiter.resume-accessed", ...)` line. Immediately AFTER it (before the `return` / `FileResponse`), add:

```python
from kpa.audit import audit_log  # at the TOP of the file with other imports
```

And in the handler body, right after the existing `_log.info(...)` call:

```python
await audit_log(
    session,
    action="resume.accessed",
    actor=current_user,
    resource_type="resume",
    resource_id=resume.id,
    context={
        "request_id": request_id,
        "application_id": str(application_id),
        "applicant_id": str(applicant.id),
        "employer_id": str(employer_id),
    },
)
```

`request_id` must already be available in this handler — it's plumbed via `RequestIdMiddleware` into `request.state.request_id` and the existing structlog line uses it. If the handler reads it via a different name (e.g., `req_id`), match that.

- [ ] **Step 3: Run the existing recruiter-resume-access tests — they must still pass**

```bash
cd api
uv run pytest -v -m integration tests/integration/test_recruiter_resume_access.py
```

Expected: all existing tests still PASS (no regression). Audit row is now silently written; existing assertions don't break.

- [ ] **Step 4: Add the audit-row assertion to the existing happy-path test**

Open `api/tests/integration/test_recruiter_resume_access.py`. Find the happy-path test (the one that asserts the structlog `recruiter.resume-accessed` line). Add to its body, AFTER the existing assertions:

```python
from sqlalchemy import select
from kpa.db.models import AuditLog

result = await session.execute(
    select(AuditLog).where(
        AuditLog.action == "resume.accessed",
        AuditLog.resource_id == resume.id,
    )
)
audit_row = result.scalar_one()
assert audit_row.actor_user_id == recruiter_user.id
assert audit_row.actor_role == "recruiter"
assert audit_row.context["request_id"] is not None
assert audit_row.context["application_id"] == str(application.id)
assert audit_row.context["applicant_id"] == str(applicant.id)
assert audit_row.context["employer_id"] == str(employer.id)
```

Adjust variable names to match the existing test fixture (`recruiter_user` / `applicant_user` / `application` / `employer` / `resume`).

If the test uses `client.get(...)` against the `client` fixture (sync TestClient), it may NOT share the savepoint-bound `session` and the audit row may live in a separately-committed transaction. Two outcomes:
- If using `async_client` + the session override → assertion works as written.
- If using sync `client` → the audit row commits via the real connection pool, then `session.execute(...)` (savepoint-bound) won't see it. Switch the test to `async_client` (the integration conftest already provides it). Per CLAUDE.md: "Default choice when a test exercises both an HTTP endpoint and `session.execute(...)`."

- [ ] **Step 5: Run the augmented test**

```bash
cd api
uv run pytest -v -m integration tests/integration/test_recruiter_resume_access.py
```

Expected: all tests still PASS, including the new assertion block.

- [ ] **Step 6: Run the full integration suite for safety**

```bash
cd api
uv run pytest -v -m integration
```

Expected: green.

- [ ] **Step 7: Run lint + mypy**

```bash
cd api
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/routes/applications.py \
        api/tests/integration/test_recruiter_resume_access.py
git commit -m "feat(api): write audit_logs row on recruiter resume access"
```

---

### Task 5: CLAUDE.md docs + PR

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the "Audit logs" section**

Open `CLAUDE.md`. Find the section header `### Soft delete model` (existing under "Architecture — non-obvious bits"). AFTER that section's body (but before the next `###`), insert:

```markdown
### Audit logs

- **Append-only.** `audit_logs` has no UPDATE or DELETE paths in code. The `CreatedAt`/`UpdatedAt`/`DeletedAt` `Annotated` types in `db/models.py` are deliberately NOT used on `AuditLog` — this is the documented exception. Queries against `audit_logs` never filter `deleted_at IS NULL`.
- **Caller owns the txn.** `await audit_log(session, action=..., actor=..., resource_type=..., resource_id=..., context=...)` adds one row inside the caller's transaction. No commit, no fire-and-forget dispatch. The row is as durable as the business action it records — if the request rolls back, the audit row rolls back too. Spec §5.1 documents why fire-and-forget was rejected.
- **`actor_user_id` is `ON DELETE SET NULL`.** Load-bearing for the future DSR-delete (sub-project D, "hard-delete PII, keep anonymized aggregates"): hard-deleting a user succeeds, but the audit row itself survives — re-identification of the deleted user is intentionally impossible.
- **`actor_role` is a snapshot** at action time, plain TEXT (not the `UserRole` enum) because `'system'` is a valid value for cron / worker actions where `actor=None`. A user whose role later flips (applicant→recruiter via `POST /v1/employers`) still has the audit rows showing the role they had at the time.
- **Action-slug namespace:** dotted, lowercase, verb-past. Reserved top-level prefixes: `resume.*`, `application.*`, `job.*`, `consent.*` (P4-B), `user.*` (P4-C/D for DSR), `admin.*`, `auth.*`, `employer.*`. Full table in spec §4.
- **The structlog line stays.** Fluent Bit → Elasticsearch → Kibana is the live operational channel (PagerDuty filters, on-call queries); the DB row is the durable channel. Both fire from the same handler — they are complementary, not substitutes. The `recruiter.resume-accessed` structlog line in `routes/applications.py` is the canonical example.
- **No retention TTL yet.** Indefinite retention until the table grows past ~10M rows; a `purge_old_audit_logs` Celery beat task is the deferred follow-up.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add CLAUDE.md
git commit -m "docs: audit_logs invariants in CLAUDE.md"
```

- [ ] **Step 3: Push + open PR**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git push -u origin feat/p4-audit-logs-substrate
gh pr create --title "feat(api): P4-A audit_logs substrate" --body "$(cat <<'EOF'
## Summary
- First P4 sub-project: an append-only `audit_logs` table + caller-owns-the-txn `audit_log()` helper that future P4 slices (consent, DSR export/delete, admin moderation, MFA) all write through.
- Promotes the existing `recruiter.resume-accessed` structlog seed line into a durable, queryable DB row. Structlog stays for ops; the DB row is the evidence record.
- `actor_user_id` is `ON DELETE SET NULL` so the future DSR-delete can hard-delete users without orphaning the FK — audit rows survive, re-identification is impossible by design.

Spec: `docs/superpowers/specs/2026-05-28-audit-logs-substrate-design.md`
Plan: `docs/superpowers/plans/2026-05-28-audit-logs-substrate.md`

## Test plan
- [ ] `uv run alembic upgrade head` applies migration 0013 cleanly
- [ ] `uv run alembic downgrade -1` rolls back cleanly
- [ ] `uv run pytest -v -m integration tests/integration/test_audit_logs.py` → 4/4 pass
- [ ] `uv run pytest -v -m integration tests/integration/test_recruiter_resume_access.py` → all pass with new audit-row assertion
- [ ] `uv run pytest -v -m integration` → full suite green
- [ ] `uv run mypy` clean
- [ ] `uv run ruff check src/ tests/` clean

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed. Return it to the user.

---

## Self-review checklist

- [x] Every requirement from the spec maps to a task: §3 table shape → Task 1; §5 helper API → Task 2; §9 tests → Tasks 2-4; §7 integration point → Task 4; §10 docs → Task 5.
- [x] No placeholder text — every step shows actual code or actual commands.
- [x] Type names consistent: `AuditLog` (model), `audit_log` (helper) — no drift between tasks.
- [x] Migration number 0013 is correct (verified against the `0012_employer_users.py` head).
- [x] The `kpa.users.id` FK matches the existing migration FK style (verified by reading 0012).
- [x] `actor_user_id ON DELETE SET NULL` is in the migration AND the model AND the spec §6 rationale AND the CLAUDE.md note — four-way consistent.
- [x] The "caller owns the txn" contract is enforced by the helper (no `session.commit()` in the helper body) AND verified by the rollback integration test.
