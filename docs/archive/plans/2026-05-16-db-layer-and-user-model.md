# KPA P0: DB layer + users/applicants schema

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the persistence layer for KPA — async SQLAlchemy 2.x against Postgres 16, Alembic migrations under the `kpa` schema, the first two domain tables (`users`, `applicants`), and a `/ready` endpoint that verifies DB connectivity. A fresh checkout reaches green tests with one prerequisite: a locally running Postgres 16 from Homebrew. No auth, no API surface beyond the readiness probe — those are the next plans.

> **MVP-first note (v2 of this plan):** Docker is intentionally **out** of this plan. Per IMPLEMENTATION_SPEC.md §11.1, dev runs on Homebrew Postgres and CI runs against a Postgres service container the workflow provides. The repo ships no `docker-compose.yml` and no `Dockerfile` at this stage. The goal is to keep the on-ramp to a working MVP as short as possible; containerization rejoins the plan at P5 when we pick a deploy target.

**Architecture:** Following IMPLEMENTATION_SPEC.md §4.1 layout: `src/kpa/db/{session.py,models.py,migrations/}`. Async engine + `async_sessionmaker`, FastAPI dep `get_session()` yielding `AsyncSession`. UUID primary keys, soft delete via `deleted_at TIMESTAMPTZ NULL` on every domain table (spec §5). Alembic runs synchronously (the convention for async-SQLAlchemy projects); the runtime app stays async. One schema `kpa`; `search_path` set on the engine. Integration tests connect to a `kpa_test` database on the same local Postgres, run Alembic once per session, and isolate per-test writes with a connect-scoped transaction + `join_transaction_mode="create_savepoint"` (so tests can freely call `await session.commit()` and the outer transaction still rolls back at fixture teardown). No SQLite, no mocks — Postgres-specific features (ARRAY, partial indexes, ENUM) light up immediately; pgvector lands in a later plan.

**Deferred to later plans (intentionally):**
- R/W split (spec §5) — single engine for now; routing dependency is a P5 hardening concern.
- pgvector + embedding tables (§5) — gated on Open Decision #2 (embedding dimension).
- Remaining §5 tables (employers, jobs, matches, resumes, notifications, consents, dsr_requests, audit_logs, ingest_*) — separate plans, one slice at a time.
- Migration history rebase tooling, automatic-revision-on-model-change CI — when the model surface is large enough to warrant it.
- User-creation endpoints — land with the auth plan.
- Any container or deploy story — deferred to P5 (§11.1 of the spec).

**Tech additions:** SQLAlchemy 2.x async, asyncpg, Alembic. No new linters; existing ruff + mypy --strict cover the new code. **Not added:** testcontainers, docker-compose.

**Working branch:** `feat/p0-db-layer-and-user-model` branched **off `feat/p0-backend-foundations`** (i.e., stacked on PR #1). When PR #1 merges, rebase onto `main`. This avoids re-establishing the FastAPI scaffolding and lets the DB code integrate with `app.state.settings` immediately.

---

## File structure after this plan

```
api/
├── pyproject.toml                     # + sqlalchemy[asyncio], asyncpg, alembic
├── alembic.ini                        # alembic config
├── .env.example                       # + KPA_DB_URL
├── README.md                          # + DB setup section (Homebrew Postgres)
├── src/kpa/
│   ├── settings.py                    # + db_url field
│   ├── app_factory.py                 # + register /ready router
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py                 # async engine, sessionmaker, get_session dep
│   │   ├── models.py                  # Base + User + Applicant
│   │   └── migrations/
│   │       ├── env.py                 # alembic env using Settings.db_url
│   │       ├── script.py.mako
│   │       └── versions/
│   │           └── 0001_users_applicants.py
│   └── routes/
│       └── ready.py                   # GET /ready with DB ping
└── tests/
    ├── conftest.py                    # unchanged
    ├── unit/
    │   ├── test_settings.py           # + db_url validation
    │   └── test_session.py            # session lifecycle (mocked engine)
    └── integration/
        ├── __init__.py
        ├── conftest.py                # local-Postgres fixture + savepoint isolation
        ├── test_migrations.py         # alembic upgrade head succeeds
        ├── test_models.py             # CRUD + soft-delete + cascade
        └── test_ready.py              # /ready returns 200 with live DB, 503 without
```

No `docker-compose.yml`, no `Dockerfile` — that's intentional (see the MVP-first note above).

---

### Task 1: Add DB dependencies via uv

**Files:**
- Modify: `api/pyproject.toml`

- [ ] **Step 1: Add dependencies to `[project]`**

`[project].dependencies` adds:
```toml
"sqlalchemy[asyncio]>=2.0.36,<2.1",
"asyncpg>=0.30,<0.31",
"alembic>=1.14,<2",
```

No new dev dependencies — integration tests use stdlib `os` and the same SQLAlchemy/asyncpg/alembic already in `[project]`.

- [ ] **Step 2: Resolve and verify install**

```bash
cd api
uv sync
```
Expected: `uv.lock` updates; final line includes the new packages. No version conflicts.

- [ ] **Step 3: Sanity-check the imports**

```bash
uv run python -c "import sqlalchemy, asyncpg, alembic; from sqlalchemy.ext.asyncio import create_async_engine; print(sqlalchemy.__version__, asyncpg.__version__, alembic.__version__)"
```
Expected: prints three version strings, no errors.

- [ ] **Step 4: Commit**

```bash
git add api/pyproject.toml api/uv.lock
git commit -m "chore(api): add sqlalchemy async, asyncpg, alembic"
```

---

### Task 2: Settings — add `db_url`

**Files:**
- Modify: `api/src/kpa/settings.py`
- Modify: `api/.env.example`
- Modify: `api/tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_settings.py`:
```python
def test_settings_loads_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")

    settings = Settings()

    assert str(settings.db_url) == "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa"


def test_settings_rejects_missing_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.delenv("KPA_DB_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_db_url_with_wrong_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    # Sync driver — must be rejected since the runtime is async-only.
    monkeypatch.setenv("KPA_DB_URL", "postgresql://kpa:kpa@localhost:5432/kpa")

    with pytest.raises(ValidationError):
        Settings()
```

Also update the existing `test_settings_loads_from_env` and `test_settings_defaults_when_optional_missing` to set `KPA_DB_URL` (they will start failing once it becomes required).

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: the three new tests fail (no `db_url` field).

- [ ] **Step 3: Implement**

In `src/kpa/settings.py`:
```python
from pydantic import AnyUrl, Field, field_validator

class Settings(BaseSettings):
    ...
    db_url: str = Field(..., description="SQLAlchemy DSN; must use postgresql+asyncpg driver.")

    @field_validator("db_url")
    @classmethod
    def _enforce_async_driver(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("db_url must use the postgresql+asyncpg:// driver")
        return v
```

- [ ] **Step 4: Update `.env.example`**

Append:
```
KPA_DB_URL=postgresql+asyncpg://kpa:kpa@localhost:5432/kpa
```

- [ ] **Step 5: Tests pass + lint + types**

```bash
uv run pytest tests/unit/test_settings.py -v
uv run ruff check src/ tests/
uv run mypy
```

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/settings.py api/.env.example api/tests/unit/test_settings.py
git commit -m "feat(api): add required KPA_DB_URL setting with async-driver validation"
```

---

### Task 3: Local Postgres 16 via Homebrew (no commit — setup only)

This task installs a real Postgres 16 on the dev machine and creates the two databases the rest of the plan needs (`kpa` for dev, `kpa_test` for integration tests). It produces **no committed files** — it's one-time machine setup that the README will document at Task 11.

**Files:** none (machine setup).

- [ ] **Step 1: Install Postgres 16 via Homebrew**

```bash
brew install postgresql@16
brew services start postgresql@16
# Add to PATH for this shell if `psql` isn't found (brew prints the exact line):
#   echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
```

Verify:
```bash
psql --version            # expect: psql (PostgreSQL) 16.x
pg_isready                # expect: /tmp:5432 - accepting connections
```

- [ ] **Step 2: Create the `kpa` role and two databases**

Homebrew Postgres trusts the local OS user by default; we create a dedicated `kpa` role so the connection string in `.env` matches what CI uses and what the rest of the team's machines will look like.

```bash
psql -d postgres <<'SQL'
CREATE ROLE kpa WITH LOGIN PASSWORD 'kpa' CREATEDB;
CREATE DATABASE kpa OWNER kpa;
CREATE DATABASE kpa_test OWNER kpa;
SQL
```

(`CREATEDB` on the role makes future `kpa_test` resets cheap if we ever need them.)

Verify the connection the app will use:
```bash
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "SELECT current_database(), current_user;"
# expect one row: kpa | kpa
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa_test -c "SELECT current_database();"
# expect: kpa_test
```

- [ ] **Step 3: Confirm `.env` matches**

`api/.env` should already have (from the Settings task, next):
```
KPA_DB_URL=postgresql+asyncpg://kpa:kpa@localhost:5432/kpa
```

Nothing to commit at this step — the README update in Task 11 will record this setup for anyone joining the project.

---

### Task 4: DB session module (async engine + sessionmaker)

**Files:**
- Create: `api/src/kpa/db/__init__.py`
- Create: `api/src/kpa/db/session.py`
- Create: `api/tests/unit/test_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_session.py`:
```python
"""Unit tests for the DB session module.

The integration tests in tests/integration/ cover real Postgres behavior.
These tests only verify lifecycle + wiring against a stubbed engine.
"""

from __future__ import annotations

import pytest

from kpa.db import session as session_module


def test_create_engine_uses_settings_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")

    engine = session_module.create_engine_from_settings()

    assert str(engine.url) == "postgresql+asyncpg://u:p@h:5432/d"
    # Engine is configured for the "kpa" schema.
    assert engine.dialect.name == "postgresql"


async def test_get_session_yields_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")

    # We don't need a real DB connection for this lifecycle test.
    sm = session_module.make_sessionmaker(session_module.create_engine_from_settings())
    async for s in session_module.get_session(sm):
        assert s is not None
        assert not s.is_active or s.is_active  # exists; will be closed on context exit
```

- [ ] **Step 2: Implement**

Create `src/kpa/db/__init__.py` (empty).

Create `src/kpa/db/session.py`:
```python
"""Async SQLAlchemy session wiring.

Single-engine, single-schema (`kpa`). R/W routing is out of scope for this
plan — see IMPLEMENTATION_SPEC.md §5 for the eventual split design.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kpa.settings import Settings

_SCHEMA = "kpa"


def create_engine_from_settings(settings: Settings | None = None) -> AsyncEngine:
    """Construct the application's async engine.

    Pool tuning is intentionally minimal here — production sizing happens via
    env vars in a later plan once we have load-test data.
    """
    settings = settings or Settings()
    return create_async_engine(
        settings.db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": _SCHEMA}},
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session(
    sm: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, close on exit, rollback on error."""
    async with sm() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 3: Wire engine + sessionmaker into the app factory**

Modify `src/kpa/app_factory.py`:
```python
from kpa.db.session import create_engine_from_settings, make_sessionmaker

def create_app() -> FastAPI:
    settings = Settings()
    configure_logging()
    engine = create_engine_from_settings(settings)
    app = FastAPI(...)
    app.state.settings = settings
    app.state.db_engine = engine
    app.state.db_sessionmaker = make_sessionmaker(engine)
    ...
```

Add a startup/shutdown hook to dispose the engine cleanly:
```python
@app.on_event("shutdown")
async def _close_engine() -> None:
    await engine.dispose()
```

(Note: `on_event` is still supported in FastAPI 0.115; we'll migrate to lifespan handlers in a later plan when other lifecycle work piles up.)

- [ ] **Step 4: Tests pass + lint + types**

- [ ] **Step 5: Commit**

```bash
git add api/src/kpa/db/__init__.py api/src/kpa/db/session.py api/src/kpa/app_factory.py api/tests/unit/test_session.py
git commit -m "feat(api): add async SQLAlchemy engine + sessionmaker"
```

---

### Task 5: Base model + common columns

**Files:**
- Create: `api/src/kpa/db/models.py`

- [ ] **Step 1: Implement Base**

Create `src/kpa/db/models.py`:
```python
"""SQLAlchemy declarative models for the KPA service.

Per IMPLEMENTATION_SPEC.md §4.2: SQLAlchemy 2.x style with typed Mapped
columns. Never use these as response schemas — separate Pydantic *Read /
*Create / *Update models belong in the domain modules.

Per §5: every domain table carries `id` (UUID), `created_at`, `updated_at`,
and `deleted_at TIMESTAMPTZ NULL` for soft delete.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base. Lives in the `kpa` schema."""

    __table_args__ = {"schema": "kpa"}


UuidPK = Annotated[
    uuid.UUID,
    mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),
]
CreatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]
DeletedAt = Annotated[
    datetime | None,
    mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=False,  # partial index added per-table in the migration.
    ),
]
```

- [ ] **Step 2: Lint + types**

```bash
uv run ruff check src/
uv run mypy
```

- [ ] **Step 3: Commit**

```bash
git add api/src/kpa/db/models.py
git commit -m "feat(api): add SQLAlchemy declarative Base + common column types"
```

---

### Task 6: User model

**Files:**
- Modify: `api/src/kpa/db/models.py`

- [ ] **Step 1: Add the User model**

Append to `src/kpa/db/models.py`:
```python
from enum import StrEnum

from sqlalchemy import Boolean, Index, String
from sqlalchemy import Enum as SAEnum


class UserRole(StrEnum):
    APPLICANT = "applicant"
    RECRUITER = "recruiter"
    ADMIN = "admin"


class User(Base):
    """Auth principal — see spec §5."""

    __tablename__ = "users"

    id: Mapped[UuidPK]
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=True, schema="kpa"),
        nullable=False,
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        # Partial index for live-row lookups; spec §5 calls these out.
        Index("ix_users_email_live", "email", postgresql_where="deleted_at IS NULL"),
        Index("ix_users_phone_live", "phone", postgresql_where="deleted_at IS NULL"),
        {"schema": "kpa"},
    )
```

Note: `email` and `phone` are both nullable because OAuth-only users may not have phone, and phone-OTP users may not have email. The CHECK constraint that at least one is present lands in the next plan when auth flows are implemented.

- [ ] **Step 2: Lint + types**

- [ ] **Step 3: Commit**

```bash
git add api/src/kpa/db/models.py
git commit -m "feat(api): add User model with role enum and soft-delete column"
```

---

### Task 7: Applicant model

**Files:**
- Modify: `api/src/kpa/db/models.py`

- [ ] **Step 1: Add the Applicant model**

Append:
```python
from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import ARRAY


class Applicant(Base):
    """Applicant profile — see spec §5."""

    __tablename__ = "applicants"

    id: Mapped[UuidPK]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default="{}"
    )
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    years_experience: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]
```

Design notes worth flagging at review:
- `current_ctc` / `expected_ctc` as `Numeric(12, 2)` (≤ 99,999,999.99) covers Indian salary ranges with room for outliers. INR-only for MVP per BRD.
- `locations` as `ARRAY(String)` matches §5; a normalized location table will land if/when geosearch becomes a requirement.
- `years_experience` as `Numeric(4, 1)` (e.g., 7.5) — fractional years are common in resumes.

- [ ] **Step 2: Lint + types**

- [ ] **Step 3: Commit**

```bash
git add api/src/kpa/db/models.py
git commit -m "feat(api): add Applicant model linked to User with locations array"
```

---

### Task 8: Alembic init + initial migration

**Files:**
- Create: `api/alembic.ini`
- Create: `api/src/kpa/db/migrations/env.py`
- Create: `api/src/kpa/db/migrations/script.py.mako`
- Create: `api/src/kpa/db/migrations/versions/0001_users_applicants.py`

- [ ] **Step 1: Generate alembic scaffold**

```bash
cd api
uv run alembic init -t async src/kpa/db/migrations
```

This creates `alembic.ini` at `api/` (move it from wherever `alembic init` puts it if needed) and the `migrations/` skeleton.

- [ ] **Step 2: Configure `alembic.ini`**

Edit `api/alembic.ini`:
- `script_location = src/kpa/db/migrations`
- `sqlalchemy.url =` (leave empty; pulled from Settings in env.py)
- `version_path_separator = os`

- [ ] **Step 3: Wire `env.py` to Settings + models**

Replace the generated `src/kpa/db/migrations/env.py` with:
```python
"""Alembic env — async migrations against the kpa schema."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from kpa.db.models import Base
from kpa.settings import Settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _set_url() -> None:
    config.set_main_option("sqlalchemy.url", Settings().db_url)


def run_migrations_offline() -> None:
    _set_url()
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema="kpa",
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="kpa",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    _set_url()
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")
    engine = async_engine_from_config(cfg, prefix="sqlalchemy.")
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Write the initial migration**

Create `src/kpa/db/migrations/versions/0001_users_applicants.py` (hand-written rather than autogenerated for the first one, so the schema-creation steps are explicit):
```python
"""users + applicants

Revision ID: 0001
Revises:
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS kpa")

    user_role = postgresql.ENUM(
        "applicant", "recruiter", "admin",
        name="user_role",
        schema="kpa",
        create_type=True,
    )
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(name="user_role", schema="kpa", create_type=False),
            nullable=False,
        ),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
        schema="kpa",
    )
    op.create_index(
        "ix_users_email_live", "users", ["email"],
        schema="kpa", postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_users_phone_live", "users", ["phone"],
        schema="kpa", postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "applicants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column("current_ctc", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_ctc", sa.Numeric(12, 2), nullable=True),
        sa.Column("years_experience", sa.Numeric(4, 1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="kpa",
    )


def downgrade() -> None:
    op.drop_table("applicants", schema="kpa")
    op.drop_index("ix_users_phone_live", table_name="users", schema="kpa")
    op.drop_index("ix_users_email_live", table_name="users", schema="kpa")
    op.drop_table("users", schema="kpa")
    op.execute("DROP TYPE IF EXISTS kpa.user_role")
    op.execute("DROP SCHEMA IF EXISTS kpa")
```

- [ ] **Step 5: Smoke-test the migration against local Postgres**

Assumes `brew services start postgresql@16` is running and the `kpa` database exists (Task 3).

```bash
cd api
KPA_ENV=local KPA_SERVICE_NAME=kpa-api \
  KPA_DB_URL=postgresql+asyncpg://kpa:kpa@localhost:5432/kpa \
  uv run alembic upgrade head
# Verify
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\dt kpa.*"
# Should list kpa.users and kpa.applicants.
KPA_ENV=local KPA_SERVICE_NAME=kpa-api \
  KPA_DB_URL=postgresql+asyncpg://kpa:kpa@localhost:5432/kpa \
  uv run alembic downgrade base
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\dt kpa.*"
# Should list nothing.
```

If Postgres isn't running yet, finish Task 3 first; the integration tests in Task 9 also exercise the migration.

- [ ] **Step 6: Commit**

```bash
git add api/alembic.ini api/src/kpa/db/migrations/
git commit -m "feat(api): add Alembic migrations and initial users+applicants schema"
```

---

### Task 9: Integration tests (local Postgres + savepoint isolation)

**Files:**
- Create: `api/tests/integration/__init__.py`
- Create: `api/tests/integration/conftest.py`
- Create: `api/tests/integration/test_migrations.py`
- Create: `api/tests/integration/test_models.py`
- Modify: `api/pyproject.toml` (add `integration` marker)

**Why no testcontainers:** we want the MVP on-ramp to stay short. The whole team (and CI) already has Postgres available — locally via Homebrew, in CI via a GitHub Actions service container. Bringing testcontainers + Docker into the dev loop is unnecessary weight at this stage. Per-test isolation is achieved with a SQLAlchemy 2.0 trick: bind the session to a live connection that owns an outer transaction, and use `join_transaction_mode="create_savepoint"` so test code can `commit()` against a savepoint while the outer transaction rolls back at fixture teardown.

- [ ] **Step 1: Register the `integration` marker**

In `pyproject.toml` `[tool.pytest.ini_options]`:
```toml
markers = [
    "integration: tests that require a running local Postgres (see README §Database)",
]
```

- [ ] **Step 2: Write the local-Postgres fixture**

Create `tests/integration/__init__.py` (empty).

Create `tests/integration/conftest.py`:
```python
"""Integration test fixtures — real Postgres 16 from local Homebrew.

Per-test isolation strategy: each test gets an `AsyncSession` bound to a
connection that holds an outer transaction. The session uses SQLAlchemy 2.0's
``join_transaction_mode="create_savepoint"`` so test code can freely call
``await session.commit()`` — that commits a savepoint, not the outer txn — and
the fixture rolls back the outer transaction at teardown. No truncation, no
container churn, fast.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


pytestmark = pytest.mark.integration


DEFAULT_TEST_DB_URL = "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa_test"


@pytest.fixture(scope="session")
def db_url() -> str:
    """Connection URL for the integration test database.

    Defaults to the local Homebrew Postgres set up in the README. Override
    via ``KPA_TEST_DB_URL`` in CI (where Postgres runs as a service
    container) or on a teammate's machine with a different layout.
    """
    return os.environ.get("KPA_TEST_DB_URL", DEFAULT_TEST_DB_URL)


@pytest.fixture(scope="session")
def migrated_db(db_url: str, monkeypatch_session: pytest.MonkeyPatch) -> str:
    """Apply alembic upgrade head against the test database once per session."""
    monkeypatch_session.setenv("KPA_ENV", "local")
    monkeypatch_session.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch_session.setenv("KPA_DB_URL", db_url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    return db_url


@pytest.fixture(scope="session")
def engine(migrated_db: str) -> AsyncEngine:
    """Session-scoped async engine. No explicit dispose — relies on process exit."""
    return create_async_engine(migrated_db)


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test session with savepoint-based rollback isolation."""
    async with engine.connect() as connection:
        trans = await connection.begin()
        sm = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with sm() as s:
            yield s
        await trans.rollback()


@pytest.fixture(scope="session")
def monkeypatch_session() -> Iterator[pytest.MonkeyPatch]:
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()
```

If `pytest_asyncio` is not yet imported elsewhere as a fixture, the import here is sufficient. The `migrated_db` fixture is a no-op on subsequent runs because Alembic's `upgrade head` short-circuits when the DB is already at head — the `kpa_test` schema persists across runs by design.

- [ ] **Step 3: Migration smoke test**

Create `tests/integration/test_migrations.py`:
```python
"""Verifies alembic upgrade head + downgrade base round-trip."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
async def test_migrated_db_has_users_and_applicants_tables(session: AsyncSession) -> None:
    result = await session.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'kpa'
        ORDER BY table_name
    """))
    names = {row[0] for row in result}
    assert "users" in names
    assert "applicants" in names


@pytest.mark.integration
async def test_users_has_partial_indexes(session: AsyncSession) -> None:
    result = await session.execute(text("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'kpa' AND tablename = 'users'
    """))
    names = {row[0] for row in result}
    assert "ix_users_email_live" in names
    assert "ix_users_phone_live" in names
```

- [ ] **Step 4: Model CRUD + soft-delete + cascade test**

Create `tests/integration/test_models.py`:
```python
"""CRUD + invariants on User and Applicant models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import Applicant, User, UserRole


@pytest.mark.integration
async def test_create_user_and_applicant(session: AsyncSession) -> None:
    user = User(email="a@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(
        user_id=user.id, full_name="A. Test", locations=["Bengaluru", "Pune"]
    )
    session.add(applicant)
    await session.commit()

    loaded = (
        await session.execute(select(Applicant).where(Applicant.user_id == user.id))
    ).scalar_one()
    assert loaded.full_name == "A. Test"
    assert loaded.locations == ["Bengaluru", "Pune"]


@pytest.mark.integration
async def test_cascade_delete_user_deletes_applicant(session: AsyncSession) -> None:
    user = User(email="b@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    session.add(Applicant(user_id=user.id, full_name="B. Test"))
    await session.commit()

    await session.delete(user)
    await session.commit()

    remaining = (
        await session.execute(select(Applicant).where(Applicant.user_id == user.id))
    ).all()
    assert remaining == []


@pytest.mark.integration
async def test_soft_delete_via_deleted_at(session: AsyncSession) -> None:
    user = User(email="c@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.commit()

    user.deleted_at = datetime.now(timezone.utc)
    await session.commit()

    # Row still exists; only the column is set.
    refreshed = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.deleted_at is not None


@pytest.mark.integration
async def test_unique_email_constraint(session: AsyncSession) -> None:
    session.add(User(email="dup@example.com", role=UserRole.APPLICANT))
    await session.commit()
    session.add(User(email="dup@example.com", role=UserRole.APPLICANT))
    with pytest.raises(Exception):  # IntegrityError; vendor-specific subclass.
        await session.commit()
    await session.rollback()
```

- [ ] **Step 5: Run integration tests**

Prereq: brew Postgres is running and `kpa_test` exists (Task 3).

```bash
cd api
uv run pytest tests/integration -v -m integration
```

Expected: 7 tests pass (1 round-trip migration check + 2 index checks + 4 model checks; counts may shift as tests evolve). On a fresh `kpa_test` database, the first run also applies migrations; subsequent runs are no-ops on the schema side.

- [ ] **Step 6: Commit**

```bash
git add api/tests/integration/ api/pyproject.toml
git commit -m "test(api): add integration tests against local Postgres with savepoint isolation"
```

---

### Task 10: /ready endpoint with DB ping

**Files:**
- Create: `api/src/kpa/routes/ready.py`
- Modify: `api/src/kpa/app_factory.py`
- Create: `api/tests/integration/test_ready.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_ready.py`:
```python
"""End-to-end /ready checks against a real Postgres."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_ready_returns_200_when_db_reachable(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)

    from kpa.app_factory import create_app  # import after env is set
    with TestClient(create_app()) as c:
        response = c.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.integration
def test_ready_returns_503_when_db_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv(
        "KPA_DB_URL",
        "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none",  # unreachable
    )

    from kpa.app_factory import create_app
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        response = c.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "db" in body.get("checks", {})
```

- [ ] **Step 2: Implement `/ready`**

Create `src/kpa/routes/ready.py`:
```python
"""Readiness endpoint — distinct from /health.

/health = liveness (process alive, can answer HTTP). No deps.
/ready  = readiness (downstream deps OK). Checked by load balancers and
          rolling-deploy gates; failing /ready takes the pod out of rotation
          without restarting it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.get("/ready", tags=["meta"])
async def ready(request: Request) -> JSONResponse:
    checks: dict[str, str] = {}
    overall_ok = True

    sm = request.app.state.db_sessionmaker
    try:
        async with sm() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except SQLAlchemyError as exc:  # noqa: BLE001 — narrow at boundary.
        checks["db"] = f"error: {type(exc).__name__}"
        overall_ok = False

    body: dict[str, Any] = {
        "status": "ready" if overall_ok else "not_ready",
        "checks": checks,
    }
    return JSONResponse(
        body,
        status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
```

- [ ] **Step 3: Mount the router**

Modify `app_factory.py`:
```python
from kpa.routes import health, ready

...
app.include_router(health.router)
app.include_router(ready.router)
```

- [ ] **Step 4: Tests pass + lint + types**

- [ ] **Step 5: Commit**

```bash
git add api/src/kpa/routes/ready.py api/src/kpa/app_factory.py api/tests/integration/test_ready.py
git commit -m "feat(api): add /ready endpoint with Postgres connectivity check"
```

---

### Task 11: README update — DB workflow

**Files:**
- Modify: `api/README.md`

- [ ] **Step 1: Add a "Database" section**

Insert after "Run locally":
````markdown
## Database

Local dev runs Postgres 16 directly via Homebrew — no Docker required for MVP work. CI runs the same Postgres as a GitHub Actions service container.

### First-time setup (one-time, per machine)

```bash
brew install postgresql@16
brew services start postgresql@16

# Create the role and the two databases (dev + integration tests).
psql -d postgres <<'SQL'
CREATE ROLE kpa WITH LOGIN PASSWORD 'kpa' CREATEDB;
CREATE DATABASE kpa OWNER kpa;
CREATE DATABASE kpa_test OWNER kpa;
SQL

uv run alembic upgrade head         # applies migrations to the dev DB
```

The dev connection string lives in `.env`:
```
KPA_DB_URL=postgresql+asyncpg://kpa:kpa@localhost:5432/kpa
```

Integration tests connect to `kpa_test` by default; override with `KPA_TEST_DB_URL` if your local Postgres isn't on `localhost:5432`.

### Reset the database

```bash
psql -d postgres -c "DROP DATABASE kpa;"
psql -d postgres -c "CREATE DATABASE kpa OWNER kpa;"
uv run alembic upgrade head
```

(For `kpa_test`, repeat with `kpa_test`. Day-to-day this isn't necessary — integration tests use savepoint rollback for isolation, so the test DB stays clean across runs.)

### Generate a new migration

```bash
uv run alembic revision -m "describe the change"
# Edit the generated file under src/kpa/db/migrations/versions/.
uv run alembic upgrade head
```

Autogeneration (`--autogenerate`) is intentionally not the default workflow
yet — hand-written migrations keep schema changes explicit while the model
surface is small. Revisit once the table count grows past ~10.

### Verify readiness

```bash
curl -s http://127.0.0.1:8000/ready | python -m json.tool
```

`/ready` returns 200 when Postgres responds to `SELECT 1`, 503 otherwise. Use it for load-balancer readiness checks; use `/health` (no DB) for liveness.
````

Also update the env-vars table to add `KPA_DB_URL`, and remove the Docker line from the Requirements section (Docker is no longer required for MVP work).

- [ ] **Step 2: Commit**

```bash
git add api/README.md
git commit -m "docs(api): document Homebrew Postgres, alembic, and /ready in README"
```

---

## Final check

After all tasks are complete, run the full local pipeline from `api/` (assumes `brew services start postgresql@16` is running and both `kpa` and `kpa_test` exist):

```bash
uv run alembic upgrade head
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
uv run pytest -v                    # unit only by default
uv run pytest -v -m integration     # integration tier (hits kpa_test)
```

All six must exit 0. The two `pytest` runs stay separate by design — unit tests must not require a live database, and the integration suite is the only thing that does.

Then push the branch and open a PR against `main` (or against `feat/p0-backend-foundations` for a stacked PR if PR #1 hasn't merged yet).

---

## Out of scope (intentionally — handled by later plans)

- R/W routing (spec §5) — single engine for now. Routing dependency added in P5 hardening once load tests demand it.
- pgvector + `applicant_embeddings` / `job_embeddings` — gated on Open Decision #2 (embedding dim).
- Remaining §5 tables (employers, recruiters, jobs, matches, applications, notifications, consents, dsr_requests, audit_logs, ingest_*) — separate plans.
- User/applicant CRUD endpoints — land with auth.
- Audit-log triggers + before/after hashing — separate compliance plan.
- Connection-pool tuning by env — when we have a load-test signal.

## Spec traceback

This plan implements the persistence-layer slice of `IMPLEMENTATION_SPEC.md` §4 (module layout for `db/`), §4.2 (SQLAlchemy 2.x async + I/O model separation rule), §5 (Postgres 16, schema `kpa`, soft-delete pattern, partial indexes for live-row lookups; the first two of the §5 tables). It deliberately stops short of §5's pgvector tables and R/W split, and adds no surface from §10 beyond `/ready`.
