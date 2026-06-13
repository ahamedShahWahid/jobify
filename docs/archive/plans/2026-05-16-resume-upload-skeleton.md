# KPA P1.0: Resume upload skeleton

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the data plane for resume uploads — a `kpa.resumes` table, a `Storage` protocol with a local-filesystem implementation, and two endpoints (`POST` / `GET`) under `/v1/applicants/{applicant_id}/resumes`. No parsing, no Celery, no S3, no auth — each gets its own plan.

**Architecture:** Following the spec at `docs/superpowers/specs/2026-05-16-resume-upload-skeleton-design.md`. Files arrive in two clean layers: (a) a `Storage` protocol + `LocalFileStorage` impl under `src/kpa/integrations/storage/`, attached to `app.state.storage`; (b) a `Resume` SQLAlchemy model + a hand-written alembic migration `0002_resumes` + a `routes/resumes.py` router. Per-test isolation in integration tests uses the same `join_transaction_mode="create_savepoint"` pattern landed in P0, with a new `client` fixture that overrides `get_session` so the route handler and the test share one connection. There is no `/me` alias yet; the applicant id is path-supplied and matched against live rows.

**Tech additions:** `python-multipart` (FastAPI's `File()` dep), but this is already pulled by `fastapi>=0.115`. No new top-level deps.

**Working branch:** `feat/p1.0-resume-upload-skeleton`, branched **off `feat/p0-db-layer-and-user-model`** (i.e., stacked on PR #2). When PR #2 merges, rebase onto `main`. This stacks cleanly because the resumes FK depends on `kpa.applicants`, which lives in PR #2.

---

## File structure after this plan

```
api/
├── .env.example                                  # + KPA_STORAGE_ROOT, KPA_MAX_UPLOAD_BYTES, KPA_ALLOWED_RESUME_CONTENT_TYPES
├── .gitignore                                    # + var/
├── README.md                                     # + Resume upload section
├── src/kpa/
│   ├── settings.py                               # + storage_root, max_upload_bytes, allowed_resume_content_types
│   ├── app_factory.py                            # + storage construction, app.state.storage, resumes router mount
│   ├── integrations/
│   │   ├── __init__.py                           # new (empty)
│   │   └── storage/
│   │       ├── __init__.py                       # new (re-exports Storage, LocalFileStorage)
│   │       ├── base.py                           # Storage Protocol + get_storage FastAPI dep
│   │       └── local.py                          # LocalFileStorage
│   ├── db/
│   │   ├── models.py                             # + ResumeParseStatus + Resume
│   │   └── migrations/versions/0002_resumes.py   # new
│   └── routes/
│       └── resumes.py                            # POST + GET handlers
└── tests/
    ├── integration/
    │   ├── conftest.py                           # + client fixture with dep overrides + storage_root override
    │   └── test_resumes_upload.py                # POST + GET integration tests
    └── unit/
        └── test_storage_local.py                 # LocalFileStorage unit tests
```

Branch ends at 8 commits (1 per task).

---

## Task 1: Storage protocol + LocalFileStorage + `get_storage` dep

**Files:**
- Create: `api/src/kpa/integrations/__init__.py`
- Create: `api/src/kpa/integrations/storage/__init__.py`
- Create: `api/src/kpa/integrations/storage/base.py`
- Create: `api/src/kpa/integrations/storage/local.py`
- Create: `api/tests/unit/test_storage_local.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_storage_local.py`:

```python
"""Unit tests for LocalFileStorage.

These tests don't need a DB; they use pytest's `tmp_path` fixture for an
isolated filesystem root per test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kpa.integrations.storage.local import LocalFileStorage


async def test_save_and_read_round_trip(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    await storage.save(key="resumes/abc.pdf", content=b"hello world", content_type="application/pdf")

    out = await storage.read("resumes/abc.pdf")

    assert out == b"hello world"
    assert (tmp_path / "resumes" / "abc.pdf").is_file()


async def test_save_creates_intermediate_directories(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)

    await storage.save(
        key="resumes/2026/05/16/abc.pdf",
        content=b"x",
        content_type="application/pdf",
    )

    assert (tmp_path / "resumes" / "2026" / "05" / "16" / "abc.pdf").is_file()


async def test_delete_removes_the_file(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    await storage.save(key="resumes/abc.pdf", content=b"x", content_type="application/pdf")

    await storage.delete("resumes/abc.pdf")

    assert not (tmp_path / "resumes" / "abc.pdf").exists()


async def test_delete_is_idempotent(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    # No save before delete — must not raise.
    await storage.delete("resumes/never-existed.pdf")


async def test_read_missing_key_raises_file_not_found(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        await storage.read("resumes/missing.pdf")


async def test_save_rejects_keys_that_escape_root(tmp_path: Path) -> None:
    """Defense in depth: a malicious key must not let the caller write outside root."""
    storage = LocalFileStorage(root=tmp_path)
    with pytest.raises(ValueError, match="must be a relative path under the storage root"):
        await storage.save(
            key="../escaped.pdf", content=b"x", content_type="application/pdf"
        )
```

- [ ] **Step 2: Run the tests, confirm they fail with import errors**

```bash
cd api
uv run pytest tests/unit/test_storage_local.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'kpa.integrations'`.

- [ ] **Step 3: Implement the protocol**

Create `src/kpa/integrations/__init__.py` (empty).
Create `src/kpa/integrations/storage/__init__.py`:

```python
"""Storage interface + concrete implementations.

The protocol is in :mod:`.base`; the local-filesystem impl is in :mod:`.local`.
An S3 impl will live in :mod:`.s3` once it's needed.
"""

from kpa.integrations.storage.base import Storage, get_storage
from kpa.integrations.storage.local import LocalFileStorage

__all__ = ["LocalFileStorage", "Storage", "get_storage"]
```

Create `src/kpa/integrations/storage/base.py`:

```python
"""Storage protocol + FastAPI dependency.

Keeps the route layer storage-agnostic: routes only see the ``Storage``
protocol and pull a concrete instance via ``Depends(get_storage)``.
"""

from __future__ import annotations

from typing import Protocol

from fastapi import Request


class Storage(Protocol):
    """Object-storage abstraction over async byte payloads.

    Keys are opaque strings; impls decide how to map them to paths/objects.
    Content is `bytes` because the upload cap is small (see settings); a
    streaming variant lands the day we lift the cap into the hundreds of MB.
    """

    async def save(self, *, key: str, content: bytes, content_type: str) -> None: ...
    async def read(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


def get_storage(request: Request) -> Storage:
    """FastAPI dependency: pull the configured Storage off ``app.state``."""
    storage: Storage = request.app.state.storage
    return storage
```

Create `src/kpa/integrations/storage/local.py`:

```python
"""Filesystem-backed Storage. Default for local dev + CI.

S3 swap is a config + impl change; nothing in the route layer or the DB
layer needs to know about it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


class LocalFileStorage:
    """Writes under ``root``. ``key`` is treated as a relative path; intermediate
    directories are created on save. Reads and deletes resolve against ``root``.

    Keys that try to escape the root (`..`, absolute paths) raise ``ValueError``.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _resolve(self, key: str) -> Path:
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(
                "key must be a relative path under the storage root"
            ) from exc
        return candidate

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(self._write, path, content)

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(self._unlink, path)

    @staticmethod
    def _unlink(path: Path) -> None:
        path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run the tests, confirm green**

```bash
uv run pytest tests/unit/test_storage_local.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
```

All clean.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/integrations/ api/tests/unit/test_storage_local.py
git commit -m "$(cat <<'EOF'
feat(api): add Storage protocol and LocalFileStorage

Storage is the abstraction the route layer talks to; LocalFileStorage is
the default impl for local dev + CI. S3 lands behind the same interface
later. Defends against path escapes via the storage_key.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Settings — `storage_root`, `max_upload_bytes`, `allowed_resume_content_types`

**Files:**
- Modify: `api/src/kpa/settings.py`
- Modify: `api/.env.example`
- Modify: `api/tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_settings.py`:

```python
from pathlib import Path


def test_settings_storage_root_defaults_to_var_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.delenv("KPA_STORAGE_ROOT", raising=False)

    settings = Settings()

    assert settings.storage_root == Path("var/uploads")


def test_settings_storage_root_honors_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))

    settings = Settings()

    assert settings.storage_root == tmp_path


def test_settings_max_upload_bytes_defaults_to_10mb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.delenv("KPA_MAX_UPLOAD_BYTES", raising=False)

    settings = Settings()

    assert settings.max_upload_bytes == 10 * 1024 * 1024


def test_settings_allowed_resume_content_types_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.delenv("KPA_ALLOWED_RESUME_CONTENT_TYPES", raising=False)

    settings = Settings()

    assert settings.allowed_resume_content_types == [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]


def test_settings_allowed_resume_content_types_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pydantic settings parses comma-separated strings into list[str] for env-var input."""
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_ALLOWED_RESUME_CONTENT_TYPES", "application/pdf,text/plain")

    settings = Settings()

    assert settings.allowed_resume_content_types == ["application/pdf", "text/plain"]
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
uv run pytest tests/unit/test_settings.py -v
```

Expected: the five new tests fail with AttributeError or ValidationError (fields don't exist yet).

- [ ] **Step 3: Implement**

In `src/kpa/settings.py`, add the imports + fields. The complete updated file:

```python
"""Application settings, sourced from environment variables.

Settings are validated at startup; the app refuses to boot on invalid input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]


_DEFAULT_ALLOWED_RESUME_CONTENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


class Settings(BaseSettings):
    """Service-wide configuration.

    Backed by environment variables prefixed with ``KPA_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="KPA_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment
    service_name: str
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "text"
    db_url: str = Field(..., description="SQLAlchemy DSN; must use postgresql+asyncpg driver.")
    storage_root: Path = Field(
        default=Path("var/uploads"),
        description="Filesystem root for LocalFileStorage. Relative paths resolve against the API's CWD.",
    )
    max_upload_bytes: int = Field(
        default=10 * 1024 * 1024,
        description="Max bytes accepted for an uploaded file (per request).",
    )
    allowed_resume_content_types: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_ALLOWED_RESUME_CONTENT_TYPES),
        description="Whitelist of Content-Type values accepted by the resume upload route.",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v

    @field_validator("log_format", mode="before")
    @classmethod
    def _lower_log_format(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v

    @field_validator("allowed_resume_content_types", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Parse comma-separated env strings into list[str].

        Pydantic-settings defaults to JSON parsing for list fields, which
        would force users to write KPA_ALLOWED_RESUME_CONTENT_TYPES='["a","b"]'.
        A CSV split keeps the env-var format ergonomic.
        """
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("db_url")
    @classmethod
    def _enforce_async_driver(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("db_url must use the postgresql+asyncpg:// driver")
        return v
```

- [ ] **Step 4: Update `.env.example`**

Append to `api/.env.example`:

```
KPA_STORAGE_ROOT=var/uploads
KPA_MAX_UPLOAD_BYTES=10485760
KPA_ALLOWED_RESUME_CONTENT_TYPES=application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

- [ ] **Step 5: Run the tests + linters**

```bash
uv run pytest tests/unit/test_settings.py -v
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
```

All clean. Settings file has 5 new tests passing on top of the existing ones.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/settings.py api/.env.example api/tests/unit/test_settings.py
git commit -m "$(cat <<'EOF'
feat(api): add storage_root + upload-limit settings

storage_root (Path), max_upload_bytes (default 10 MiB), and
allowed_resume_content_types (CSV in env, list[str] in code) drive the
resume upload route's validation + file persistence.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire `LocalFileStorage` into the app factory

**Files:**
- Modify: `api/src/kpa/app_factory.py`
- Modify: `.gitignore` (repo root)

- [ ] **Step 1: Read the current `app_factory.py`**

```bash
cat api/src/kpa/app_factory.py
```

You'll see it currently creates the engine + sessionmaker, attaches them to `app.state`, and mounts `health.router` + `ready.router`. We're adding storage construction + attachment between the sessionmaker line and the router mounts.

- [ ] **Step 2: Patch `app_factory.py`**

Add the import:

```python
from kpa.integrations.storage import LocalFileStorage
```

After the `app.state.db_sessionmaker = make_sessionmaker(engine)` line and before the existing router mounts, insert:

```python
    app.state.storage = LocalFileStorage(root=settings.storage_root)
```

Do **not** reorder any existing lines. Do **not** remove the existing comments.

- [ ] **Step 3: Update `.gitignore` to keep `var/` out of git**

The repo-root `.gitignore` already exists. Append:

```
# Local upload storage (LocalFileStorage default root).
api/var/
```

- [ ] **Step 4: Smoke-test the wiring**

The existing `/health` and `/ready` tests already exercise `create_app()`. They'll fail if storage construction blows up (e.g., bad path). Run the full suite to confirm:

```bash
cd api
uv run pytest -v
```

Expected: 31+ tests passing, no regressions.

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
```

All clean.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/app_factory.py .gitignore
git commit -m "$(cat <<'EOF'
feat(api): wire LocalFileStorage into app.state.storage

Route handlers and Depends(get_storage) read from app.state. Gitignored
var/ keeps the dev-mode upload directory out of source control.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `ResumeParseStatus` enum + `Resume` model

**Files:**
- Modify: `api/src/kpa/db/models.py`

- [ ] **Step 1: Append the new enum + model**

Add the imports near the top (alongside the existing sqlalchemy imports):

```python
from sqlalchemy import BigInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
```

Append below the existing `Applicant` class:

```python
class ResumeParseStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class Resume(Base):
    """Uploaded resume — see spec §6.1 and the P1.0 design doc.

    In this slice, every row is created with parse_status='pending' and never
    transitions. The parse worker plan moves rows through parsing → parsed/failed.
    """

    __tablename__ = "resumes"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[ResumeParseStatus] = mapped_column(
        SAEnum(
            ResumeParseStatus,
            name="resume_parse_status",
            native_enum=True,
            schema="kpa",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ResumeParseStatus.PENDING,
        server_default=ResumeParseStatus.PENDING.value,
    )
    parsed_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]
```

Note: the `BigInteger` import isn't strictly used (we picked `Integer` because 10 MB fits in int4 — 2^31 = 2.1 GB headroom). Remove the `BigInteger` import line if you didn't end up using it. The `Text` and `JSONB` imports are used.

- [ ] **Step 2: Lint + types**

```bash
cd api
uv run ruff check src/ tests/
uv run mypy
```

All clean. ruff will flag unused imports (F401) if you left `BigInteger` in — drop it.

- [ ] **Step 3: Commit**

```bash
git add api/src/kpa/db/models.py
git commit -m "$(cat <<'EOF'
feat(api): add Resume model with parse_status enum

resume_parse_status defines all four states (pending → parsing → parsed/
failed) now so the parse-worker plan never has to ALTER TYPE.
parsed_json + parse_error stay nullable until that plan lands.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Alembic migration `0002_resumes.py`

**Files:**
- Create: `api/src/kpa/db/migrations/versions/0002_resumes.py`

- [ ] **Step 1: Write the hand-written migration**

Create `src/kpa/db/migrations/versions/0002_resumes.py`:

```python
"""resumes

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    parse_status = postgresql.ENUM(
        "pending",
        "parsing",
        "parsed",
        "failed",
        name="resume_parse_status",
        schema="kpa",
        create_type=True,
    )
    parse_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "applicant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "parse_status",
            postgresql.ENUM(
                name="resume_parse_status",
                schema="kpa",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("parsed_json", postgresql.JSONB(), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="kpa",
    )
    op.create_index(
        "ix_resumes_applicant_id",
        "resumes",
        ["applicant_id"],
        schema="kpa",
    )


def downgrade() -> None:
    op.drop_index("ix_resumes_applicant_id", table_name="resumes", schema="kpa")
    op.drop_table("resumes", schema="kpa")
    op.execute("DROP TYPE IF EXISTS kpa.resume_parse_status")
    # Schema persists — dropping it would destroy alembic_version.
```

- [ ] **Step 2: Smoke-test upgrade + downgrade against local Postgres**

```bash
cd api
uv run --env-file=.env alembic upgrade head
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\dt kpa.*"
# Expected: alembic_version, applicants, resumes, users (4 tables).

PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\d kpa.resumes"
# Expected: 11 columns (id, applicant_id, storage_key, original_filename,
# content_type, size_bytes, parse_status, parsed_json, parse_error,
# created_at, updated_at, deleted_at). FK to applicants with ON DELETE CASCADE.
# Index ix_resumes_applicant_id on (applicant_id).

PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "SELECT enumlabel FROM pg_enum
  WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'resume_parse_status') ORDER BY enumsortorder;"
# Expected: pending, parsing, parsed, failed.

uv run --env-file=.env alembic downgrade 0001
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\dt kpa.*"
# Expected: alembic_version, applicants, users (3 tables; resumes gone).

# Restore head so subsequent tasks have the table.
uv run --env-file=.env alembic upgrade head
```

If any check fails: the migration is wrong. Fix it before continuing.

- [ ] **Step 3: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

All clean (migrations dir is excluded from mypy).

- [ ] **Step 4: Commit**

```bash
git add api/src/kpa/db/migrations/versions/0002_resumes.py
git commit -m "$(cat <<'EOF'
feat(api): add 0002_resumes migration

Creates kpa.resume_parse_status enum and kpa.resumes table with FK to
applicants (ON DELETE CASCADE) and an index on applicant_id. Round-trips
cleanly (upgrade head → downgrade 0001 → upgrade head).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Integration test fixtures — `client` with savepoint-shared session + tmp storage

**Files:**
- Modify: `api/tests/integration/conftest.py`

Before writing the route, we need a fixture that:
1. Sets env vars (including a `tmp_path`-rooted `KPA_STORAGE_ROOT`).
2. Builds the app via `create_app()`.
3. Overrides `kpa.db.session.get_session` so the route handler shares the test's savepoint-isolated connection.
4. Yields a sync `TestClient` ready to call the API.

The override is essential — without it, the route's session lives on a different connection than the test's `session` fixture, so `session.add(...)` (e.g., creating an applicant for the test) is invisible to the route handler.

- [ ] **Step 1: Append the new fixture to `tests/integration/conftest.py`**

Add these imports at the top (next to the existing imports):

```python
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncConnection
```

Append (after the existing `session` fixture):

```python
@pytest.fixture
def client(
    session: AsyncSession,
    db_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Test client that shares the savepoint-isolated session with the route handler.

    Steps:
      1. Set env vars (including KPA_STORAGE_ROOT pointed at tmp_path).
      2. Build the app via create_app().
      3. Override Depends(get_session) so every route handler reuses
         the test's session (same connection, same savepoint).
      4. Yield a sync TestClient.
    """
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _shared_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
```

Add `from pathlib import Path` to the imports if not already there.

- [ ] **Step 2: Verify the fixture compiles**

```bash
cd api
uv run pytest tests/integration/ --collect-only 2>&1 | tail -10
```

Expected: tests are collected without error. (No tests use the fixture yet, but the conftest must parse cleanly.)

- [ ] **Step 3: Lint + types**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
```

All clean.

- [ ] **Step 4: Commit**

```bash
git add api/tests/integration/conftest.py
git commit -m "$(cat <<'EOF'
test(api): add `client` fixture sharing savepoint session with handlers

Without the dep override, the route's session lives on a different
connection than the test's savepoint-isolated session — rows the test
inserts are invisible to the handler. The override binds them to the
same connection so the savepoint covers both.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `POST /v1/applicants/{applicant_id}/resumes`

**Files:**
- Create: `api/src/kpa/routes/resumes.py`
- Modify: `api/src/kpa/app_factory.py`
- Create: `api/tests/integration/test_resumes_upload.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_resumes_upload.py`:

```python
"""POST /v1/applicants/{applicant_id}/resumes — upload + persistence."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole


_TINY_PDF = b"%PDF-1.4\n%minimal\n"


async def _make_applicant(session: AsyncSession) -> Applicant:
    user = User(email=f"applicant-{uuid.uuid4()}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Test Applicant")
    session.add(applicant)
    await session.commit()
    return applicant


@pytest.mark.integration
async def test_upload_resume_happy_path(
    client: TestClient, session: AsyncSession, tmp_path: Path
) -> None:
    applicant = await _make_applicant(session)

    response = client.post(
        f"/v1/applicants/{applicant.id}/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["applicant_id"] == str(applicant.id)
    assert body["original_filename"] == "cv.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(_TINY_PDF)
    assert body["parse_status"] == "pending"

    resume_id = uuid.UUID(body["id"])
    row = (
        await session.execute(select(Resume).where(Resume.id == resume_id))
    ).scalar_one()
    assert row.parse_status is ResumeParseStatus.PENDING

    on_disk = tmp_path / row.storage_key
    assert on_disk.is_file()
    assert on_disk.read_bytes() == _TINY_PDF


@pytest.mark.integration
async def test_upload_resume_unknown_applicant_returns_404(client: TestClient) -> None:
    bogus = uuid.uuid4()

    response = client.post(
        f"/v1/applicants/{bogus}/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.integration
async def test_upload_resume_rejects_disallowed_content_type(
    client: TestClient, session: AsyncSession, tmp_path: Path
) -> None:
    applicant = await _make_applicant(session)

    response = client.post(
        f"/v1/applicants/{applicant.id}/resumes",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    # No row persisted, no file written.
    rows = (
        await session.execute(select(Resume).where(Resume.applicant_id == applicant.id))
    ).all()
    assert rows == []
    assert not any(tmp_path.rglob("*"))


@pytest.mark.integration
async def test_upload_resume_rejects_oversized_payload(
    client: TestClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use a low cap so we don't allocate real 10 MB blobs in tests."""
    # The cap was set in the client fixture's env; override it directly on settings
    # by hitting the route with a tiny cap and a slightly-larger payload.
    # We re-create the app with a stricter cap.
    monkeypatch.setenv("KPA_MAX_UPLOAD_BYTES", "16")  # 16 bytes
    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session():
        yield session

    app.dependency_overrides[get_session] = _shared_session
    applicant = await _make_applicant(session)

    payload = b"x" * 32  # over 16 bytes

    with TestClient(app) as c:
        response = c.post(
            f"/v1/applicants/{applicant.id}/resumes",
            files={"file": ("cv.pdf", payload, "application/pdf")},
        )

    assert response.status_code == 413
    rows = (
        await session.execute(select(Resume).where(Resume.applicant_id == applicant.id))
    ).all()
    assert rows == []
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd api
uv run pytest tests/integration/test_resumes_upload.py -v -m integration
```

Expected: collection error (`/v1/applicants/.../resumes` route doesn't exist yet) or 404s on every endpoint.

- [ ] **Step 3: Implement the route**

Create `src/kpa/routes/resumes.py`:

```python
"""Resume upload + retrieval endpoints.

Routes are nested under the applicant id; no auth in this slice (the
applicant id is supplied directly in the path). Auth lands later and
adds a /v1/applicants/me/resumes alias.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import Applicant, Resume, ResumeParseStatus
from kpa.db.session import get_session
from kpa.integrations.storage import Storage, get_storage
from kpa.settings import Settings

router = APIRouter(prefix="/v1/applicants/{applicant_id}", tags=["resumes"])


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


async def _load_live_applicant(session: AsyncSession, applicant_id: UUID) -> Applicant:
    row = (
        await session.execute(
            select(Applicant).where(
                Applicant.id == applicant_id,
                Applicant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="applicant not found"
        )
    return row


@router.post(
    "/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    applicant_id: UUID,
    request: Request,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> Resume:
    settings: Settings = request.app.state.settings

    if (
        file.content_type is None
        or file.content_type not in settings.allowed_resume_content_types
    ):
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

    applicant = await _load_live_applicant(session, applicant_id)

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

    await storage.save(
        key=resume.storage_key, content=content, content_type=file.content_type
    )
    await session.commit()
    await session.refresh(resume)
    return resume
```

- [ ] **Step 4: Mount the router in `app_factory.py`**

Update the imports:

```python
from kpa.routes import health, ready, resumes
```

Add the include below the existing ones:

```python
    app.include_router(resumes.router)
```

- [ ] **Step 5: Run the four POST tests**

```bash
cd api
uv run pytest tests/integration/test_resumes_upload.py -v -m integration
```

Expected: 4 tests pass (happy path, 404, 415, 413).

If a test fails:
- 404 case: ensure `_load_live_applicant` runs *after* content-type/size validation — actually it doesn't matter for that test, but ensure the response Content-Type is `application/problem+json` (the existing error handler does this).
- 413 case: the size check happens after `file.read()` — that's intentional. For a real prod hardening, we'd cap at the multipart-parsing layer too, but FastAPI's `UploadFile` doesn't expose a clean way to do that without monkeypatching starlette. Acceptable for MVP.
- Happy path: if `storage_key` is empty in the response, you wrote it before `flush()` — re-check the ordering.

- [ ] **Step 6: Lint + types + full suite**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
uv run pytest -v
```

All clean. Full suite is now 46 tests (31 from P0 + 5 settings + 6 storage + 4 POST).

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/routes/resumes.py api/src/kpa/app_factory.py api/tests/integration/test_resumes_upload.py
git commit -m "$(cat <<'EOF'
feat(api): POST /v1/applicants/{aid}/resumes accepts multipart uploads

Validates content-type against settings whitelist (415 otherwise),
enforces max_upload_bytes (413 otherwise), persists via the Storage
protocol, and creates a kpa.resumes row with parse_status='pending'.
Extension comes from a trusted content-type map, not the filename.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `GET /v1/applicants/{applicant_id}/resumes/{resume_id}`

**Files:**
- Modify: `api/src/kpa/routes/resumes.py`
- Modify: `api/tests/integration/test_resumes_upload.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/integration/test_resumes_upload.py`:

```python
@pytest.mark.integration
async def test_get_resume_returns_metadata(
    client: TestClient, session: AsyncSession
) -> None:
    applicant = await _make_applicant(session)
    post = client.post(
        f"/v1/applicants/{applicant.id}/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
    )
    assert post.status_code == 201, post.text
    posted = post.json()

    response = client.get(f"/v1/applicants/{applicant.id}/resumes/{posted['id']}")

    assert response.status_code == 200
    assert response.json() == posted


@pytest.mark.integration
async def test_get_resume_unknown_id_returns_404(
    client: TestClient, session: AsyncSession
) -> None:
    applicant = await _make_applicant(session)
    bogus = uuid.uuid4()

    response = client.get(f"/v1/applicants/{applicant.id}/resumes/{bogus}")

    assert response.status_code == 404


@pytest.mark.integration
async def test_get_resume_from_wrong_applicant_returns_404(
    client: TestClient, session: AsyncSession
) -> None:
    """A real resume id queried under a *different* applicant's path must 404.

    Returning 403 would leak the existence of the resume to an unauthorized
    caller; 404 keeps the surface flat.
    """
    owner = await _make_applicant(session)
    intruder = await _make_applicant(session)

    post = client.post(
        f"/v1/applicants/{owner.id}/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
    )
    posted = post.json()

    response = client.get(f"/v1/applicants/{intruder.id}/resumes/{posted['id']}")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd api
uv run pytest tests/integration/test_resumes_upload.py -v -m integration
```

Expected: the three new tests fail (route doesn't exist).

- [ ] **Step 3: Implement the GET route**

Append to `src/kpa/routes/resumes.py`:

```python
@router.get(
    "/resumes/{resume_id}",
    response_model=ResumeRead,
)
async def get_resume(
    applicant_id: UUID,
    resume_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Resume:
    # Apply the same live-applicant check as POST so we don't leak the
    # resume's existence to callers using an unknown applicant id.
    await _load_live_applicant(session, applicant_id)

    row = (
        await session.execute(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.applicant_id == applicant_id,
                Resume.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resume not found"
        )
    return row
```

- [ ] **Step 4: Run the new tests**

```bash
uv run pytest tests/integration/test_resumes_upload.py -v -m integration
```

Expected: 7 tests pass (4 prior + 3 new).

- [ ] **Step 5: Run the full pipeline**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
uv run pytest -v
```

All clean. Full suite is 49 tests (46 prior + 3 GET).

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/routes/resumes.py api/tests/integration/test_resumes_upload.py
git commit -m "$(cat <<'EOF'
feat(api): GET /v1/applicants/{aid}/resumes/{rid} returns metadata

Cross-applicant lookups return 404 rather than 403 to avoid leaking
existence. Soft-deleted rows (deleted_at IS NOT NULL) are invisible.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: README — document upload endpoints + new env vars

**Files:**
- Modify: `api/README.md`

- [ ] **Step 1: Update the env-vars table**

In `api/README.md`, find the Configuration table and add three rows:

```markdown
| `KPA_STORAGE_ROOT` | no       | `var/uploads` | Filesystem root for LocalFileStorage. Relative to CWD. |
| `KPA_MAX_UPLOAD_BYTES` | no   | `10485760`    | Max bytes per upload (10 MiB).                       |
| `KPA_ALLOWED_RESUME_CONTENT_TYPES` | no | (pdf/doc/docx) | Comma-separated content-type whitelist.       |
```

- [ ] **Step 2: Add a Resume uploads section**

After the existing Database section, before "Run with JSON logs", insert:

````markdown
## Resume uploads

Two endpoints, both nested under an applicant id:

```
POST   /v1/applicants/{applicant_id}/resumes
GET    /v1/applicants/{applicant_id}/resumes/{resume_id}
```

POST accepts `multipart/form-data` with one field `file`. Content-type is checked against `KPA_ALLOWED_RESUME_CONTENT_TYPES`; size against `KPA_MAX_UPLOAD_BYTES`. The file is persisted under `KPA_STORAGE_ROOT` (gitignored `var/` by default); the resume row in `kpa.resumes` lands with `parse_status=pending`. Parsing is a later plan.

There's no auth in this slice — the applicant id is supplied directly in the URL. The `/v1/applicants/me/resumes` alias lands with the auth plan.

Quick test from the shell once the server is running:

```bash
# Create a user + applicant first via psql (until signup endpoints exist).
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa <<'SQL'
INSERT INTO kpa.users (id, email, role) VALUES (gen_random_uuid(), 'demo@example.com', 'applicant');
INSERT INTO kpa.applicants (id, user_id, full_name)
SELECT gen_random_uuid(), id, 'Demo' FROM kpa.users WHERE email = 'demo@example.com';
SELECT id FROM kpa.applicants WHERE full_name = 'Demo';
SQL

APPLICANT_ID=<paste the id from above>
curl -s -X POST "http://127.0.0.1:8000/v1/applicants/$APPLICANT_ID/resumes" \
    -F "file=@/path/to/cv.pdf" | python -m json.tool
```
````

- [ ] **Step 3: Update the Project layout**

Replace the existing layout block with:

````markdown
```
api/
├── alembic.ini
├── src/kpa/
│   ├── app_factory.py        # create_app() — middlewares + routes + engine + storage
│   ├── main.py               # uvicorn entry point
│   ├── settings.py
│   ├── middleware/
│   │   ├── request_id.py     # X-Request-Id propagation
│   │   └── error_handler.py  # RFC 7807 problem+json
│   ├── observability/
│   │   └── logging.py        # structlog config
│   ├── integrations/
│   │   └── storage/          # Storage protocol + LocalFileStorage
│   ├── db/
│   │   ├── session.py        # async engine, sessionmaker, get_session dep
│   │   ├── models.py         # Base, User, Applicant, Resume
│   │   └── migrations/       # alembic env + versions/
│   └── routes/
│       ├── health.py         # GET /health (liveness)
│       ├── ready.py          # GET /ready (readiness, DB ping)
│       └── resumes.py        # /v1/applicants/{aid}/resumes …
└── tests/
    ├── unit/                 # no DB required
    └── integration/          # require local Postgres (savepoint isolation)
```
````

- [ ] **Step 4: Commit**

```bash
git add api/README.md
git commit -m "$(cat <<'EOF'
docs(api): document resume upload endpoints + new storage env vars

Adds a Resume uploads section with a curl example, updates the env-vars
table with KPA_STORAGE_ROOT / KPA_MAX_UPLOAD_BYTES /
KPA_ALLOWED_RESUME_CONTENT_TYPES, and refreshes the project layout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final check

After all tasks land, run the full local pipeline from `api/`:

```bash
uv run --env-file=.env alembic upgrade head      # idempotent if already at head
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"            # unit only
uv run pytest -v -m integration                  # integration tier
uv run pytest -v                                 # full suite
```

All six must exit 0. Full suite should be 49 tests (31 from P0 + 5 settings + 6 storage + 7 resumes route).

Then push the branch and either:
- Open a PR against `feat/p0-db-layer-and-user-model` (stacked) if PR #2 hasn't merged yet.
- Open a PR against `main` if PR #2 already merged.

---

## Out of scope (intentionally — handled by later plans)

- Celery parse worker — separate plan.
- Embedding generation + `applicant_embeddings` table — pending Open Decision #2 (embedding dim).
- S3 storage impl — interface is here; impl + deploy-target choice come together in P5.
- Magic-byte content-type verification + ClamAV scan — both land with the parse pipeline (which reads bytes anyway).
- `/v1/applicants/me/resumes` alias — lands with the auth plan (Google OAuth).
- List endpoint + the `(applicant_id, created_at DESC)` partial index — deferred until a UI surface needs it.
- File download endpoint (`GET /resumes/{id}/file`) — no consumer yet.
- P0 cleanup items (Settings | None default, lifespan migration, partial-index test hardening) — separate small plan, can run in parallel with the parse-worker plan.

## Spec traceback

This plan implements the design at `docs/superpowers/specs/2026-05-16-resume-upload-skeleton-design.md`. Sections in the design map to tasks as follows:

- **Surface** (POST / GET) → Tasks 7 + 8.
- **Data model** (`kpa.resumes`, `ResumeParseStatus`) → Tasks 4 + 5.
- **Storage interface** (Storage protocol, LocalFileStorage) → Task 1.
- **Validation** (content-type whitelist, max bytes) → Task 2 (settings) + Task 7 (enforcement).
- **Auth bypass** (path-param applicant_id, live row check) → Task 7's `_load_live_applicant`.
- **Tests** (unit + 7 integration scenarios) → Tasks 1 + 7 + 8.
- **File layout** → matches the per-task file lists.
