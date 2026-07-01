# Resume Review + Job Preferences Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a resume finishes parsing, show the applicant a summary of what was extracted and capture desired role / location / expected CTC; nudge applicants who haven't uploaded a resume, or who have one but haven't answered the 3 questions yet.

**Architecture:** A new `applicant_preferences` table (one row per applicant, eagerly created at signup) becomes the single source for `desired_role` (new), `locations`, and `expected_ctc` (both moved off `Applicant`, where they already existed and already fed the scoring workers). Two new endpoints (`GET`/`PATCH /v1/applicants/me/preferences`) replace the `locations`/`expected_ctc` slice of the existing profile PATCH. Both scoring workers (`score_applicant`, `score_job`) are repointed to read from the new table via an outer join so a missing row degrades to the same empty defaults `Applicant.locations`/`expected_ctc` had before. On the Flutter side, a new `PreferencesScreen` is reached either right after a resume finishes parsing (if any of the 3 fields are still empty) or via a persistent feed banner; the existing profile edit screen keeps its own UI but now saves to two endpoints instead of one.

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Alembic (hand-written migrations) + Celery workers (backend); Flutter + Riverpod 4.x codegen + dio + go_router (frontend).

## Global Constraints

- **uv only** — run all backend commands via `uv run ...` from the repo root.
- **Soft delete everywhere** — new table carries `id`/`created_at`/`updated_at`/`deleted_at`; live queries filter `deleted_at IS NULL`; uniqueness via a partial index `WHERE deleted_at IS NULL`.
- **Hand-written migrations** in `core/src/jobify/db/migrations/versions/` — autogenerate is off. New revision `0021`, `down_revision = "0020"`.
- **structlog only**, no `print`/`logging.getLogger`.
- **All FastAPI handlers `async def`.** Routes under `/v1`.
- **SQLAlchemy models are never response schemas** — define `*Read`/`*Update` Pydantic v2 models in the route module.
- **CI verbatim commands** (run before claiming any backend task green): `uv run ruff check core/src api/src worker/src tests`, `uv run ruff format --check core/src api/src worker/src tests`, `uv run mypy`, `uv run pytest -v -m "not integration and not eval"`, `uv run pytest -v -m integration`.
- **Frontend CI verbatim**: `dart format --set-exit-if-changed lib test`, `flutter analyze`, `flutter test` — all from `app/`.
- **Every `tests/integration/test_*.py` needs module-level `pytestmark = pytest.mark.integration`.**
- **Riverpod codegen**: after touching any `@riverpod`/`@freezed`/`@JsonSerializable` class, run `dart run build_runner build --delete-conflicting-outputs` from `app/`.
- **No new users exist on this platform** — no backfill/migration-data concerns anywhere in this plan.
- **New PII table → DSR coverage is mandatory**, not optional: `applicant_preferences` must be wired into `jobify_api.dsr` (export), `jobify_api.dsr.deleter` (delete), and the `tests/unit/dsr/test_dsr_coverage.py` pinned set, or CI fails by design.

---

## Part A — Backend: data model, migration, eager provisioning

### Task 1: `RoleCategory` enum + `ApplicantPreferences` model; drop `locations`/`expected_ctc` from `Applicant`

**Files:**
- Modify: `core/src/jobify/db/models.py`
- Test: `tests/unit/test_models.py` (create if it doesn't already cover this — check first; if a `tests/unit/test_models.py` doesn't exist, add assertions to `tests/integration/test_models.py` instead since model identity doesn't need a DB)

**Interfaces:**
- Produces: `jobify.db.models.RoleCategory` (StrEnum, 16 values), `jobify.db.models.ApplicantPreferences` (SQLAlchemy model: `id`, `applicant_id`, `desired_role: RoleCategory | None`, `locations: list[str]`, `expected_ctc: float | None`, `created_at`, `updated_at`, `deleted_at`). `Applicant` no longer has `locations`/`expected_ctc`.

- [ ] **Step 1: Add `RoleCategory` + `ApplicantPreferences` to `core/src/jobify/db/models.py`, and drop the two columns from `Applicant`**

Edit `Applicant` (currently `core/src/jobify/db/models.py:117-139`) — remove the `locations` and `expected_ctc` mapped columns:

```python
class Applicant(Base):
    """Applicant profile — see spec §5."""

    __tablename__ = "applicants"

    id: Mapped[UuidPK]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobify.users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    years_experience: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]
```

Immediately after the `Applicant` class (before `class ResumeParseStatus`), add:

```python
class RoleCategory(StrEnum):
    SOFTWARE_ENGINEERING = "software_engineering"
    DATA_ANALYTICS = "data_analytics"
    PRODUCT_MANAGEMENT = "product_management"
    DESIGN = "design"
    SALES = "sales"
    MARKETING = "marketing"
    CUSTOMER_SUPPORT = "customer_support"
    OPERATIONS = "operations"
    FINANCE_ACCOUNTING = "finance_accounting"
    HR_RECRUITING = "hr_recruiting"
    LEGAL = "legal"
    CONSULTING = "consulting"
    BUSINESS_DEVELOPMENT = "business_development"
    CONTENT_COMMUNICATIONS = "content_communications"
    ADMINISTRATION = "administration"
    OTHER = "other"


class ApplicantPreferences(Base):
    """Desired role / location / expected CTC — captured after resume upload
    or via the profile edit screen. Single source for these 3 fields (they
    used to live on Applicant); one live row per applicant, eagerly created
    at signup by AuthService._upsert_identity so scoring workers and the
    GET endpoint never need to handle a missing row for a real applicant."""

    __tablename__ = "applicant_preferences"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobify.applicants.id", ondelete="CASCADE"),
        nullable=False,
    )
    desired_role: Mapped[RoleCategory | None] = mapped_column(
        SAEnum(
            RoleCategory,
            name="role_category",
            native_enum=True,
            schema="jobify",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default="{}"
    )
    expected_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        Index(
            "ix_applicant_preferences_applicant_live",
            "applicant_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        {"schema": "jobify"},
    )
```

- [ ] **Step 2: Add a model-identity test**

Append to `tests/integration/test_models.py` (no DB round-trip needed, but this file already runs under the integration marker — that's fine, it's cheap):

```python
def test_applicant_preferences_model_shape() -> None:
    from jobify.db.models import ApplicantPreferences, RoleCategory

    assert ApplicantPreferences.__tablename__ == "applicant_preferences"
    mapper = ApplicantPreferences.__mapper__
    columns = {c.key for c in mapper.columns}
    assert columns == {
        "id",
        "applicant_id",
        "desired_role",
        "locations",
        "expected_ctc",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert len(RoleCategory) == 16


def test_applicant_no_longer_has_locations_or_expected_ctc() -> None:
    from jobify.db.models import Applicant

    columns = {c.key for c in Applicant.__mapper__.columns}
    assert "locations" not in columns
    assert "expected_ctc" not in columns
```

- [ ] **Step 3: Run the test to verify it fails before the migration exists**

Run: `uv run pytest tests/integration/test_models.py -k "applicant_preferences or no_longer_has" -v`
Expected: at this point it should actually PASS (the model change alone is enough — no DB round-trip in this test), confirming the model edit is syntactically correct. If it errors on import, fix `models.py` before continuing.

- [ ] **Step 4: Commit**

```bash
git add core/src/jobify/db/models.py tests/integration/test_models.py
git commit -m "feat(core): add ApplicantPreferences model, drop locations/expected_ctc from Applicant"
```

---

### Task 2: Migration 0021 — create `applicant_preferences`, drop the two `Applicant` columns

**Files:**
- Create: `core/src/jobify/db/migrations/versions/0021_applicant_preferences.py`

**Interfaces:**
- Consumes: `Task 1`'s model shape (must match exactly — column names, types, nullability).
- Produces: `jobify.applicant_preferences` table + `jobify.role_category` enum type in the real DB; `jobify.applicants.locations`/`expected_ctc` columns dropped.

- [ ] **Step 1: Write the migration**

```python
"""applicant_preferences: desired_role/locations/expected_ctc, single source

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-01

Adds:
- jobify.role_category ENUM (16 values)
- jobify.applicant_preferences (one live row per applicant, partial-unique
  on applicant_id)

Drops:
- jobify.applicants.locations
- jobify.applicants.expected_ctc

No backfill — no existing users on the platform (see docs/superpowers/specs/
2026-07-01-resume-review-preferences-design.md). Downgrade restores both
columns nullable (their pre-migration nullability) but cannot restore data.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_ROLE_CATEGORY_VALUES = (
    "software_engineering",
    "data_analytics",
    "product_management",
    "design",
    "sales",
    "marketing",
    "customer_support",
    "operations",
    "finance_accounting",
    "hr_recruiting",
    "legal",
    "consulting",
    "business_development",
    "content_communications",
    "administration",
    "other",
)


def upgrade() -> None:
    role_category = postgresql.ENUM(
        *_ROLE_CATEGORY_VALUES,
        name="role_category",
        schema="jobify",
        create_type=True,
    )
    role_category.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "applicant_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "applicant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.applicants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "desired_role",
            postgresql.ENUM(name="role_category", schema="jobify", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("expected_ctc", sa.Numeric(12, 2), nullable=True),
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
        schema="jobify",
    )
    op.create_index(
        "ix_applicant_preferences_applicant_live",
        "applicant_preferences",
        ["applicant_id"],
        unique=True,
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_column("applicants", "locations", schema="jobify")
    op.drop_column("applicants", "expected_ctc", schema="jobify")


def downgrade() -> None:
    op.add_column(
        "applicants",
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(100)),
            nullable=True,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        schema="jobify",
    )
    op.add_column(
        "applicants",
        sa.Column("expected_ctc", sa.Numeric(12, 2), nullable=True),
        schema="jobify",
    )

    op.drop_index(
        "ix_applicant_preferences_applicant_live",
        table_name="applicant_preferences",
        schema="jobify",
    )
    op.drop_table("applicant_preferences", schema="jobify")
    op.execute("DROP TYPE IF EXISTS jobify.role_category")
```

- [ ] **Step 2: Apply the migration to the local dev DB**

Run: `cd core && uv run alembic upgrade head && cd ..`
Expected: no errors; `alembic_version` now shows `0021`.

- [ ] **Step 3: Verify the table + dropped columns directly**

Run: `psql "$JOBIFY_DB_URL" -c "\d jobify.applicant_preferences" && psql "$JOBIFY_DB_URL" -c "\d jobify.applicants"`
Expected: `applicant_preferences` shows all 8 columns + the unique index; `applicants` no longer lists `locations`/`expected_ctc`.

- [ ] **Step 4: Verify downgrade round-trips cleanly**

Run: `cd core && uv run alembic downgrade -1 && uv run alembic upgrade head && cd ..`
Expected: both commands succeed with no errors (proves the downgrade path is at least syntactically sound, even though it can't restore dropped data).

- [ ] **Step 5: Commit**

```bash
git add core/src/jobify/db/migrations/versions/0021_applicant_preferences.py
git commit -m "feat(core): migration 0021 — applicant_preferences table, drop Applicant.locations/expected_ctc"
```

---

### Task 3: Eagerly provision an `ApplicantPreferences` row at signup

**Files:**
- Modify: `api/src/jobify_api/auth/service.py`
- Test: `tests/integration/test_auth_google_signin.py` (check this filename first — grep `tests/integration/test_auth*.py` for whichever file covers `sign_in_with_google`'s new-user path; add the assertion there)

**Interfaces:**
- Consumes: `ApplicantPreferences` from `jobify.db.models` (Task 1).
- Produces: guarantee that every applicant created via Google sign-in has exactly one live `ApplicantPreferences` row immediately, in the same transaction as the `Applicant` row and consent seeding.

- [ ] **Step 1: Locate the exact new-user test file**

Run: `grep -rl "is_new_user\|_upsert_identity" tests/integration/*.py`

Use whichever file this returns (there should be exactly one test file exercising the Google sign-in new-user path) for Step 3 below.

- [ ] **Step 2: Add the eager-create call in `_upsert_identity`**

In `api/src/jobify_api/auth/service.py`, the new-identity branch (currently ending at line ~181) creates `applicant` and flushes `identity`. Add the import and the new row right after `applicant` is added:

Add to the imports at the top of the file (alongside the existing `from jobify.db.models import (...)` block):

```python
from jobify.db.models import ApplicantPreferences
```

Then, immediately after `self._session.add(applicant)` (currently line 163) and before `identity = OAuthIdentity(...)`:

```python
        self._session.add(applicant)
        await self._session.flush()  # populates applicant.id

        self._session.add(ApplicantPreferences(applicant_id=applicant.id))
```

(This requires flushing `applicant` one statement earlier than today — today the flush happens implicitly via the `identity` block's own `await self._session.flush()` a few lines down. Flushing right after `applicant` is added is safe: `Applicant.id` is a client-side `uuid.uuid4()` default, so no extra round-trip is introduced by flushing here versus later — but flushing explicitly here removes any ordering ambiguity about whether `applicant.id` is populated before `ApplicantPreferences(applicant_id=applicant.id)` reads it.)

- [ ] **Step 3: Add the assertion to the sign-in test**

Open the file found in Step 1. Find the test that asserts a new user + applicant are created on first sign-in (it will assert something like `is_new_user is True` and check the `applicant` row). Add, right after the existing applicant assertions in that same test:

```python
    from jobify.db.models import ApplicantPreferences

    prefs = (
        await session.execute(
            select(ApplicantPreferences).where(
                ApplicantPreferences.applicant_id == applicant.id
            )
        )
    ).scalar_one()
    assert prefs.desired_role is None
    assert prefs.locations == []
    assert prefs.expected_ctc is None
```

(Add `from sqlalchemy import select` to that file's imports if not already present — check first.)

- [ ] **Step 4: Run the test**

Run: `uv run pytest <path-to-the-file-from-step-1> -k "new" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/src/jobify_api/auth/service.py <path-to-the-file-from-step-1>
git commit -m "feat(api): eagerly create ApplicantPreferences row at signup"
```

---

## Part B — Backend: API surface

### Task 4: Expose `parsed_json` on `ResumeRead`

**Files:**
- Modify: `api/src/jobify_api/routes/resumes.py`
- Test: `tests/integration/test_resumes_auth.py` or wherever `GET /v1/applicants/me/resumes/{id}` is already tested — grep first.

**Interfaces:**
- Produces: `ResumeRead.parsed_json: dict[str, Any] | None`, present on the upload/list/get responses.

- [ ] **Step 1: Find the existing resume-get test**

Run: `grep -rl "get_resume\|/resumes/{" tests/integration/*.py | xargs grep -l "def test_"`

- [ ] **Step 2: Add `parsed_json` to `ResumeRead`**

In `api/src/jobify_api/routes/resumes.py`, add `Any` to the typing import (currently `from datetime import datetime` / `from uuid import UUID` at the top — add a new line `from typing import Any`), and edit `ResumeRead` (currently lines 47-58):

```python
class ResumeRead(BaseModel):
    """Response shape for resume metadata. Bytes are never returned here."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    applicant_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    parse_status: ResumeParseStatus
    parsed_json: dict[str, Any] | None = None
    created_at: datetime
```

- [ ] **Step 3: Add an integration test asserting it round-trips**

In the test file from Step 1, add:

```python
async def test_get_resume_includes_parsed_json(
    async_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    from jobify.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole
    from jobify_api.auth.tokens import mint_access_token

    user = User(email="parsed-json@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Parsed Json")
    session.add(applicant)
    await session.flush()
    resume = Resume(
        applicant_id=applicant.id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        storage_key="resumes/x.pdf",
        size_bytes=10,
        parse_status=ResumeParseStatus.PARSED,
        parsed_json={"name": "Parsed Json", "skills": ["Python"]},
    )
    session.add(resume)
    await session.commit()

    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    resp = await async_client.get(
        f"/v1/applicants/me/resumes/{resume.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["parsed_json"] == {"name": "Parsed Json", "skills": ["Python"]}
```

Adjust the imports at the top of the test file to match whatever's already imported vs. what needs adding (many of these — `Applicant`, `User`, `UserRole`, `mint_access_token` — are almost certainly already imported in this file; only add what's missing).

- [ ] **Step 4: Run it**

Run: `uv run pytest <test-file-from-step-1> -k parsed_json -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/src/jobify_api/routes/resumes.py <test-file-from-step-1>
git commit -m "feat(api): expose parsed_json on ResumeRead"
```

---

### Task 5: Drop `locations`/`expected_ctc` from `ApplicantRead` (`/v1/me`)

**Files:**
- Modify: `api/src/jobify_api/routes/me.py`
- Modify: `tests/integration/test_me.py`

**Interfaces:**
- Produces: `ApplicantRead` without `locations`/`expected_ctc` (7 fields → 5).

- [ ] **Step 1: Edit `ApplicantRead`**

In `api/src/jobify_api/routes/me.py`, replace the class (currently lines 23-34):

```python
class ApplicantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # Nullable to mirror the DB schema — migration 0015 made full_name
    # nullable for DSR scrubbing. A non-optional str here turns a NULL row
    # into a Pydantic ValidationError -> 500.
    full_name: str | None
    notice_period_days: int | None
    current_ctc: Decimal | None
    years_experience: Decimal | None
```

- [ ] **Step 2: Fix `tests/integration/test_me.py`**

Open the file. Two tests reference `locations` directly:

`test_me_returns_user_and_applicant` (around line 51) — remove the line `assert body["applicant"]["locations"] == []`.

`test_me_tolerates_nullable_email_and_scrubbed_applicant_fields` (around lines 120-152) — the docstring and the `Applicant(user_id=user.id, full_name=None, locations=None)` constructor call, plus the `update(Applicant)...values(locations=None)` and the final `assert body["applicant"]["locations"] is None`. Update to:

```python
async def test_me_tolerates_nullable_email_and_scrubbed_applicant_fields(
    async_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """users.email and applicants.full_name are nullable (DSR scrubbing) —
    /v1/me must not 500 on a scrubbed row."""
    user = User(email=None, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name=None)
    session.add(applicant)
    await session.commit()
    # ... (keep whatever follows unchanged except remove the
    # `update(Applicant).values(locations=None)` statement entirely — that
    # column no longer exists — and remove the final
    # `assert body["applicant"]["locations"] is None` line.)
```

Read the surrounding lines (110-155) directly before editing to preserve everything else in the test body exactly — only the `locations`-specific lines are being removed.

- [ ] **Step 3: Run the file's tests**

Run: `uv run pytest tests/integration/test_me.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add api/src/jobify_api/routes/me.py tests/integration/test_me.py
git commit -m "feat(api): drop locations/expected_ctc from ApplicantRead"
```

---

### Task 6: Drop `locations`/`expected_ctc` from `ProfileUpdate` + `update_profile`

**Files:**
- Modify: `api/src/jobify_api/routes/applicants.py`
- Modify: `tests/integration/test_profile_update.py`

**Interfaces:**
- Produces: `ProfileUpdate` with `full_name`, `notice_period_days`, `current_ctc`, `years_experience` only. `_MATCHING_FIELDS = {"years_experience"}`.

- [ ] **Step 1: Edit `applicants.py`**

Replace the module docstring, `_MATCHING_FIELDS`, and `ProfileUpdate` (currently lines 1-59):

```python
"""Applicant profile update — PATCH /v1/applicants/me.

The authenticated applicant edits their own profile fields. A change to
years_experience fires a fire-and-forget rescore post-commit (it feeds the
structured score). locations/expected_ctc moved to
applicant_preferences — see PATCH /v1/applicants/me/preferences below.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import ApplicantPreferences, RoleCategory, User
from jobify_api.auth.dependencies import (
    current_user,
)
from jobify_api.auth.dependencies import (
    require_applicant as _require_applicant,
)
from jobify_api.dependencies import get_session
from jobify_api.routes.me import ApplicantRead, MeResponse

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/applicants/me", tags=["applicants"])

# Fields whose change must trigger a rescore (they drive the structured score).
_MATCHING_FIELDS = {"years_experience"}
# Same list, for the preferences endpoint below.
_PREFERENCES_MATCHING_FIELDS = {"locations", "expected_ctc"}


class ProfileUpdate(BaseModel):
    """Partial profile update. Only keys present in the request are applied
    (`model_fields_set`); an explicit null clears a nullable column.
    `full_name` is non-nullable and rejects an explicit null."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    current_ctc: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))
    years_experience: Decimal | None = Field(default=None, ge=0, le=Decimal("60"))

    @model_validator(mode="after")
    def _no_null_for_required(self) -> ProfileUpdate:
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("full_name cannot be null")
        return self
```

`_dispatch_score` (lines 62-70) and the `update_profile` handler (lines 73-98) stay exactly as they are — they already only iterate `payload.model_fields_set`, so removing the two fields from `ProfileUpdate` automatically removes them from what can be set. Leave `_PREFERENCES_MATCHING_FIELDS` defined here for Task 7 to import.

- [ ] **Step 2: Run mypy + ruff to catch anything missed**

Run: `uv run ruff check api/src/jobify_api/routes/applicants.py && uv run mypy`
Expected: no errors (in particular, no leftover reference to `locations`/`expected_ctc` in this file).

- [ ] **Step 3: Fix `tests/integration/test_profile_update.py`**

Read the current file fully (already read during planning — 184 lines). Apply these changes:

`test_patch_partial_update` (lines 39-59): change to only exercise `notice_period_days`/`years_experience`/`current_ctc` (the `locations`/`expected_ctc` assertions move to the new preferences test file in Task 8):

```python
async def test_patch_partial_update(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]

    resp = await async_client.patch(
        "/v1/applicants/me",
        headers={"Authorization": f"Bearer {access}"},
        json={"years_experience": 4.5, "current_ctc": 1200000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicant"]["years_experience"] == "4.5"
    assert body["applicant"]["current_ctc"] == "1200000.00"
    assert body["applicant"]["full_name"] == "Alice"

    row = (
        await session.execute(select(Applicant).where(Applicant.user_id == signin["user"]["id"]))
    ).scalar_one()
    assert row.years_experience == Decimal("4.5")
```

Add `from decimal import Decimal` to the imports if not already present.

`test_patch_explicit_null_clears_nullable` and `test_patch_omitted_key_unchanged`: unchanged — they already only use `notice_period_days`.

`test_patch_validation_422` (lines 90-105): remove the 3 `locations`-specific cases (`{"locations": None}`, `{"locations": [""]}`, `{"locations": ["a"] * 11}`) — they move to the new preferences validation test in Task 8. Keep the rest.

`test_patch_recruiter_returns_403` (lines 113-136): change the PATCH body from `{"locations": ["Pune"]}` to `{"notice_period_days": 30}` (any valid field works; the point is exercising the 403 path).

`test_patch_matching_field_dispatches_rescore` (lines 139-159): change the PATCH body from `{"locations": ["Pune"]}` to `{"years_experience": 3}` — `years_experience` is now the only matching field left on this route.

`test_patch_non_matching_field_no_rescore` (lines 162-183): unchanged — already uses `notice_period_days`.

- [ ] **Step 4: Run the file**

Run: `uv run pytest tests/integration/test_profile_update.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/src/jobify_api/routes/applicants.py tests/integration/test_profile_update.py
git commit -m "feat(api): drop locations/expected_ctc from ProfileUpdate"
```

---

### Task 7: `GET`/`PATCH /v1/applicants/me/preferences`

**Files:**
- Modify: `api/src/jobify_api/routes/applicants.py`
- Create: `tests/integration/test_applicant_preferences.py`

**Interfaces:**
- Consumes: `ApplicantPreferences`, `RoleCategory` (Task 1); `_require_applicant` (`jobify_api.auth.dependencies`); `_dispatch_score` (already in this module, Task 6).
- Produces: `PreferencesRead`, `PreferencesUpdate` Pydantic models; `GET`/`PATCH /v1/applicants/me/preferences` routes on the same router.

- [ ] **Step 1: Add the schemas + routes to `applicants.py`**

Append to the end of `api/src/jobify_api/routes/applicants.py`:

```python
class PreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    desired_role: RoleCategory | None
    locations: list[str]
    expected_ctc: Decimal | None


class PreferencesUpdate(BaseModel):
    """Partial preferences update — same partial-update contract as
    ProfileUpdate. `desired_role`/`expected_ctc` are nullable and accept an
    explicit null to clear; `locations` is non-nullable (empty list clears
    it instead)."""

    model_config = ConfigDict(extra="forbid")

    desired_role: RoleCategory | None = Field(default=None)
    locations: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(
        default=None, max_length=10
    )
    expected_ctc: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))

    @model_validator(mode="after")
    def _no_null_for_locations(self) -> PreferencesUpdate:
        if "locations" in self.model_fields_set and self.locations is None:
            raise ValueError("locations cannot be null")
        return self


async def _get_or_404_preferences(
    applicant_id: UUID, session: AsyncSession
) -> ApplicantPreferences:
    """Every applicant gets a live preferences row eagerly at signup
    (AuthService._upsert_identity) — a missing row here is unreachable in
    the real system but guarded defensively, same shape as
    require_applicant's applicant_missing 500."""
    row = (
        await session.execute(
            select(ApplicantPreferences).where(
                ApplicantPreferences.applicant_id == applicant_id,
                ApplicantPreferences.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        _log.error("preferences.row-missing-for-applicant", applicant_id=str(applicant_id))
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="applicant_preferences_missing")
    return row


@router.get("/preferences", response_model=PreferencesRead, status_code=status.HTTP_200_OK)
async def get_preferences(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PreferencesRead:
    applicant = await _require_applicant(user, session)
    row = await _get_or_404_preferences(applicant.id, session)
    return PreferencesRead.model_validate(row, from_attributes=True)


@router.patch("/preferences", response_model=PreferencesRead, status_code=status.HTTP_200_OK)
async def update_preferences(
    payload: PreferencesUpdate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PreferencesRead:
    applicant = await _require_applicant(user, session)
    row = await _get_or_404_preferences(applicant.id, session)

    changed_matching = False
    for name in payload.model_fields_set:
        setattr(row, name, getattr(payload, name))
        if name in _PREFERENCES_MATCHING_FIELDS:
            changed_matching = True
    await session.flush()
    await session.commit()
    await session.refresh(row)

    if changed_matching:
        _dispatch_score(applicant.id)
    return PreferencesRead.model_validate(row, from_attributes=True)
```

- [ ] **Step 2: Write `tests/integration/test_applicant_preferences.py`**

```python
"""Integration tests for GET/PATCH /v1/applicants/me/preferences."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import ApplicantPreferences, User, UserRole
from jobify_api.auth.google_verifier import GoogleClaims
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32


def _claims() -> GoogleClaims:
    return GoogleClaims(
        sub="google-sub-prefs",
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email="prefs@example.com",
        email_verified=True,
        name="Prefs Test",
    )


async def _signin(client: httpx.AsyncClient, google_verifier) -> dict:
    google_verifier.canned["tok"] = _claims()
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert resp.status_code == 200
    return resp.json()


async def test_get_preferences_defaults_empty(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.get("/v1/applicants/me/preferences", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"desired_role": None, "locations": [], "expected_ctc": None}


async def test_patch_partial_update(
    async_client: httpx.AsyncClient, google_verifier, session: AsyncSession
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={
            "desired_role": "software_engineering",
            "locations": ["Pune", "Bengaluru"],
            "expected_ctc": 1800000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["desired_role"] == "software_engineering"
    assert body["locations"] == ["Pune", "Bengaluru"]
    assert body["expected_ctc"] == "1800000.00"

    row = (
        await session.execute(
            select(ApplicantPreferences).where(
                ApplicantPreferences.applicant_id == signin["user"]["applicant_id"]
            )
        )
    ).scalar_one()
    assert row.locations == ["Pune", "Bengaluru"]


async def test_patch_omitted_key_unchanged(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"expected_ctc": 1000000}
    )
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={"locations": ["Remote"]},
    )
    assert resp.status_code == 200
    assert resp.json()["expected_ctc"] == "1000000.00"


@pytest.mark.parametrize(
    "body",
    [
        {"desired_role": "not_a_real_role"},
        {"locations": None},
        {"locations": [""]},
        {"locations": ["a"] * 11},
        {"expected_ctc": -5},
        {"unknown_field": "x"},
    ],
)
async def test_patch_validation_422(
    async_client: httpx.AsyncClient, google_verifier, body
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json=body
    )
    assert resp.status_code == 422


async def test_patch_recruiter_returns_403(
    async_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    import uuid

    recruiter = User(email=f"recruiter-{uuid.uuid4()}@example.com", role=UserRole.RECRUITER)
    session.add(recruiter)
    await session.flush()
    access = mint_access_token(
        user_id=recruiter.id, role=recruiter.role.value, secret=_JWT_SECRET, ttl_seconds=600
    )
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers={"Authorization": f"Bearer {access}"},
        json={"expected_ctc": 1000000},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"


async def test_patch_matching_field_dispatches_rescore(
    async_client: httpx.AsyncClient, google_verifier, monkeypatch
) -> None:
    import jobify.celery_app as _celery_mod

    calls: list[str] = []

    def _spy_enqueue(name: str, *args: object) -> None:
        if name == "jobify.score_applicant":
            calls.extend(args)

    monkeypatch.setattr(_celery_mod, "enqueue", _spy_enqueue)

    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences", headers=headers, json={"locations": ["Pune"]}
    )
    assert resp.status_code == 200
    assert calls == [signin["user"]["applicant_id"]]


async def test_patch_desired_role_only_no_rescore(
    async_client: httpx.AsyncClient, google_verifier, monkeypatch
) -> None:
    import jobify.celery_app as _celery_mod

    calls: list[str] = []

    def _spy_enqueue(name: str, *args: object) -> None:
        if name == "jobify.score_applicant":
            calls.extend(args)

    monkeypatch.setattr(_celery_mod, "enqueue", _spy_enqueue)

    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch(
        "/v1/applicants/me/preferences",
        headers=headers,
        json={"desired_role": "design"},
    )
    assert resp.status_code == 200
    assert calls == []  # desired_role is capture-only, not a matching field
```

- [ ] **Step 3: Run the new test file**

Run: `uv run pytest tests/integration/test_applicant_preferences.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add api/src/jobify_api/routes/applicants.py tests/integration/test_applicant_preferences.py
git commit -m "feat(api): GET/PATCH /v1/applicants/me/preferences"
```

---

## Part C — Backend: repoint scoring workers

### Task 8: `score_applicant.py` reads locations/expected_ctc from `ApplicantPreferences`

**Files:**
- Modify: `worker/src/jobify_worker/tasks/score_applicant.py`
- Modify: `tests/integration/test_score_applicant_worker.py`

**Interfaces:**
- Consumes: `ApplicantPreferences` (Task 1).
- Produces: identical `score_match(...)` call shape as before; the only change is where `applicant_locs`/`applicant_ctc` are sourced from.

- [ ] **Step 1: Edit the Txn 1 query and variable extraction**

In `worker/src/jobify_worker/tasks/score_applicant.py`, add `ApplicantPreferences` to the model import (line 31-39), then replace the query + extraction block (currently lines 94-151):

```python
from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    ApplicantPreferences,
    Employer,
    Job,
    JobEmbedding,
    JobStatus,
    Match,
)
```

```python
    async with sm() as session:
        applicant_row = (
            await session.execute(
                select(Applicant, ApplicantEmbedding, ApplicantPreferences)
                .join(ApplicantEmbedding, ApplicantEmbedding.applicant_id == Applicant.id)
                .outerjoin(
                    ApplicantPreferences,
                    ApplicantPreferences.applicant_id == Applicant.id,
                )
                .where(
                    Applicant.id == applicant_id,
                    Applicant.deleted_at.is_(None),
                    ApplicantEmbedding.deleted_at.is_(None),
                    ApplicantPreferences.deleted_at.is_(None),
                )
            )
        ).first()
        if applicant_row is None:
            _log.info("score.applicant-skipped", applicant_id=str(applicant_id))
            return
        applicant, applicant_emb, applicant_prefs = applicant_row
```

(The `ApplicantPreferences.deleted_at.is_(None)` filter is safe on an outer join: for an applicant with no matching row, every `ApplicantPreferences` column — including `deleted_at` — comes back `NULL`, and `NULL IS NULL` evaluates true in SQL, so the row still passes the filter.)

Then, further down, replace the 3 lines that read applicant fields (currently lines 149-151):

```python
        applicant_locs = list(applicant_prefs.locations or []) if applicant_prefs else []
        applicant_years = applicant.years_experience
        applicant_ctc = applicant_prefs.expected_ctc if applicant_prefs else None
```

Everything below this (the `score_match(...)` call, `ExplainContext`, the UPSERT) is unchanged — it already just consumes `applicant_locs`/`applicant_years`/`applicant_ctc` by name.

- [ ] **Step 2: Update the test file's shared `_seed_applicant` helper**

In `tests/integration/test_score_applicant_worker.py`, add `ApplicantPreferences` to the model import, then replace `_seed_applicant` (currently lines 37-50) to accept and seed locations:

```python
async def _seed_applicant(
    session: AsyncSession, *, email: str = "s@example.com", locations: list[str] | None = None
) -> Applicant:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="S Test")
    session.add(applicant)
    await session.flush()
    session.add(
        ApplicantPreferences(applicant_id=applicant.id, locations=locations or ["Bangalore"])
    )
    session.add(
        ApplicantEmbedding(
            applicant_id=applicant.id,
            embedding=[1.0] * 1536,
            model_name="test-model",
            canonicalized_text_hash="a" * 64,
            input_tokens=10,
        )
    )
    await session.flush()
    return applicant
```

- [ ] **Step 3: Fix the one inline constructor that bypasses the helper**

`test_score_applicant_does_not_surface_below_threshold` (around line 203) directly constructs `Applicant(user_id=user.id, full_name="S2", locations=["Mumbai"])` instead of calling `_seed_applicant`. Read that test in full first (lines ~196-230), then replace the direct construction with:

```python
    user = User(email="s2@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="S2")
    session.add(applicant)
    await session.flush()
    session.add(ApplicantPreferences(applicant_id=applicant.id, locations=["Mumbai"]))
    session.add(
        ApplicantEmbedding(
            applicant_id=applicant.id,
            embedding=applicant_emb,  # keep whatever variable name this test already used
            model_name="test-model",
            canonicalized_text_hash="a" * 64,
            input_tokens=10,
        )
    )
    await session.flush()
```

(Match the exact embedding vector variable/value already used in this test — read the surrounding lines before editing so the embedding assertion this test is actually checking doesn't change.)

- [ ] **Step 4: Fix `test_score_applicant_skips_when_no_applicant_embedding`**

Around line 304, `Applicant(user_id=user.id, full_name="NoEmb", locations=["Bangalore"])` — this test is about a MISSING embedding, not location matching, so just drop the `locations=` kwarg (no paired `ApplicantPreferences` row needed — the outer join means an applicant with no preferences row still gets scored with empty defaults, and this test's whole point is that scoring is skipped due to the missing *embedding*, which is unaffected):

```python
    applicant = Applicant(user_id=user.id, full_name="NoEmb")
```

- [ ] **Step 5: Run the whole file**

Run: `uv run pytest tests/integration/test_score_applicant_worker.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add worker/src/jobify_worker/tasks/score_applicant.py tests/integration/test_score_applicant_worker.py
git commit -m "feat(worker): score_applicant reads locations/expected_ctc from ApplicantPreferences"
```

---

### Task 9: `score_job.py` reads locations/expected_ctc from `ApplicantPreferences`

**Files:**
- Modify: `worker/src/jobify_worker/tasks/score_job.py`
- Modify: `tests/integration/test_score_job_worker.py`

**Interfaces:**
- Mirror of Task 8, symmetric worker.

- [ ] **Step 1: Edit the Txn 1 query and extraction block**

In `worker/src/jobify_worker/tasks/score_job.py`, add `ApplicantPreferences` to the model import, then replace the query (currently around lines 107-135):

```python
        apps_stmt = (
            select(Applicant, ApplicantEmbedding, ApplicantPreferences)
            .join(ApplicantEmbedding, ApplicantEmbedding.applicant_id == Applicant.id)
            .outerjoin(
                ApplicantPreferences,
                ApplicantPreferences.applicant_id == Applicant.id,
            )
            .where(
                Applicant.deleted_at.is_(None),
                ApplicantEmbedding.deleted_at.is_(None),
                ApplicantPreferences.deleted_at.is_(None),
            )
            .order_by(Applicant.id.asc())
            .limit(limit + 1)
        )
        if after_applicant_id is not None:
            apps_stmt = apps_stmt.where(Applicant.id > after_applicant_id)
        app_rows = (await session.execute(apps_stmt)).all()
        has_more = len(app_rows) > limit
        app_rows = app_rows[:limit]
        next_after_applicant_id = app_rows[-1][0].id if has_more and app_rows else None
        scored_inputs = []
        for applicant, applicant_emb, applicant_prefs in app_rows:
            scored_inputs.append(
                (
                    applicant.id,
                    list(applicant_prefs.locations or []) if applicant_prefs else [],
                    applicant.years_experience,
                    applicant_prefs.expected_ctc if applicant_prefs else None,
                    list(applicant_emb.embedding),
                    applicant_emb.model_name,
                )
            )
```

Everything below (the `score_match(...)` loop, `ExplainContext`, UPSERT) is unchanged.

- [ ] **Step 2: Update `tests/integration/test_score_job_worker.py` fixtures**

Read the file fully first, then apply the same treatment as Task 8 Steps 2-4: find this file's applicant-seeding helper (mirror of `_seed_applicant`) and any inline `Applicant(..., locations=...)` constructions (per the earlier research, lines 39 and 156), and:
- add `ApplicantPreferences` to imports
- move any `locations=[...]` kwarg off the `Applicant(...)` constructor into a sibling `session.add(ApplicantPreferences(applicant_id=applicant.id, locations=[...]))` call
- for any construction that doesn't pass `locations=` at all, just drop nothing extra — the outer join defaults to `[]` regardless.

- [ ] **Step 3: Run the whole file**

Run: `uv run pytest tests/integration/test_score_job_worker.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add worker/src/jobify_worker/tasks/score_job.py tests/integration/test_score_job_worker.py
git commit -m "feat(worker): score_job reads locations/expected_ctc from ApplicantPreferences"
```

---

## Part D — Backend: DSR export, delete, coverage

### Task 10: Add `applicant_preferences` to the DSR export

**Files:**
- Modify: `api/src/jobify_api/dsr/__init__.py`
- Modify: `tests/unit/dsr/test_builder_signature.py`
- Modify: `tests/integration/test_dsr_export.py`

**Interfaces:**
- Produces: `UserExport.applicant_preferences: dict[str, Any] | None`.

- [ ] **Step 1: Edit `api/src/jobify_api/dsr/__init__.py`**

Add `ApplicantPreferences` to the model import (currently lines 22-39). Add the field to `UserExport` right after `applicant` (currently line 59):

```python
    applicant: dict[str, Any] | None = None
    applicant_preferences: dict[str, Any] | None = None
```

In `build_user_export`, inside the `if applicant_row is not None:` block (currently lines 233-275), add a query for the preferences row right after the `applicant_id = applicant_row.id` line:

```python
        applicant_preferences_row = (
            await session.execute(
                select(ApplicantPreferences).where(
                    ApplicantPreferences.applicant_id == applicant_id
                )
            )
        ).scalar_one_or_none()
```

Add `applicant_preferences_dict: dict[str, Any] | None = None` to the block of `None`-initialized locals right above (alongside `embedding_dict`, `applications`, etc.), and set it:

```python
        if applicant_preferences_row is not None:
            applicant_preferences_dict = _row_to_dict(applicant_preferences_row)
```

Finally, add `applicant_preferences=applicant_preferences_dict,` to the `UserExport(...)` construction at the end (right after `applicant=applicant_dict,`).

- [ ] **Step 2: Update the field-set pin**

In `tests/unit/dsr/test_builder_signature.py`, add `"applicant_preferences"` to the `expected` set in `test_user_export_top_level_fields` (right after `"applicant",`).

- [ ] **Step 3: Add an assertion to the happy-path export test**

In `tests/integration/test_dsr_export.py`, `test_applicant_export_happy_path` (lines 98-122), add right after `assert body["applicant"]["full_name"] == "DSR Test User"`:

```python
    assert body["applicant_preferences"] is not None
    assert body["applicant_preferences"]["locations"] == []
```

- [ ] **Step 4: Run**

Run: `uv run pytest tests/unit/dsr/test_builder_signature.py tests/integration/test_dsr_export.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/src/jobify_api/dsr/__init__.py tests/unit/dsr/test_builder_signature.py tests/integration/test_dsr_export.py
git commit -m "feat(api): wire applicant_preferences into the DSR export"
```

---

### Task 11: Hard-delete `ApplicantPreferences` on DSR delete

**Files:**
- Modify: `api/src/jobify_api/dsr/deleter.py`
- Modify: `tests/integration/test_dsr_delete.py`

**Interfaces:**
- Produces: `delete_user_data` hard-deletes the applicant's `ApplicantPreferences` row (same "hard-delete PII" pattern as `SavedJob`/`ApplicantEmbedding` — the row holds no anonymized-aggregate value once the applicant is gone), and no longer references `locations`/`expected_ctc` on `Applicant`.

- [ ] **Step 1: Edit `deleter.py`**

Add `ApplicantPreferences` to the model import (currently lines 25-39). In the `if applicant_id is not None:` block, add a delete step right after the saved-jobs delete (currently lines 172-176):

```python
        # 7b. Preferences row — hard-delete (same pattern as saved_jobs /
        # applicant_embeddings; nothing here is an anonymized aggregate
        # worth keeping once the applicant is scrubbed).
        r = await session.execute(  # type: ignore[assignment]
            delete(ApplicantPreferences).where(ApplicantPreferences.applicant_id == applicant_id)
        )
        counts["applicant_preferences"] = r.rowcount or 0
```

In the `else:` branch (currently lines 233-238, the no-applicant-row case), add the matching zero-count:

```python
        counts["applicant_preferences"] = 0
```

Finally, remove `locations=None` and `expected_ctc=None` from the `Applicant` scrub UPDATE (currently lines 217-232) — those columns no longer exist:

```python
        # 11. Applicant — scrub PII + tombstone.
        await session.execute(
            update(Applicant)
            .where(Applicant.id == applicant_id)
            .values(
                full_name=None,
                notice_period_days=None,
                current_ctc=None,
                expected_ctc=None,
                years_experience=None,
                deleted_at=now,
                updated_at=now,
            )
        )
```

Wait — `expected_ctc` must also be dropped from this list (it's no longer an `Applicant` column). The corrected block:

```python
        # 11. Applicant — scrub PII + tombstone.
        await session.execute(
            update(Applicant)
            .where(Applicant.id == applicant_id)
            .values(
                full_name=None,
                notice_period_days=None,
                current_ctc=None,
                years_experience=None,
                deleted_at=now,
                updated_at=now,
            )
        )
```

- [ ] **Step 2: Fix `test_dsr_delete.py`**

`test_applicant_happy_path_tombstones_and_clears` (lines 137-199): replace `applicant.expected_ctc = Decimal("1500000")` with creating a preferences row instead:

```python
    from jobify.db.models import ApplicantPreferences

    session.add(ApplicantPreferences(applicant_id=applicant.id, expected_ctc=Decimal("1500000")))
    applicant.years_experience = Decimal("4.5")
```

Add `assert body["section_counts"]["applicant_preferences"] == 1` alongside the other `section_counts` assertions (after `assert body["section_counts"]["resumes_scrubbed"] == 1`).

Replace `assert refetched_applicant.expected_ctc is None` with a check that the preferences row is gone:

```python
    refetched_prefs = (
        await session.execute(
            select(ApplicantPreferences).where(ApplicantPreferences.applicant_id == applicant.id)
        )
    ).scalar_one_or_none()
    assert refetched_prefs is None
```

- [ ] **Step 3: Run**

Run: `uv run pytest tests/integration/test_dsr_delete.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add api/src/jobify_api/dsr/deleter.py tests/integration/test_dsr_delete.py
git commit -m "feat(api): hard-delete ApplicantPreferences on DSR delete"
```

---

### Task 12: Update the DSR coverage-symmetry pin

**Files:**
- Modify: `tests/unit/dsr/test_dsr_coverage.py`

**Interfaces:**
- Consumes: Tasks 10 + 11 (both DSR modules must already import `ApplicantPreferences` — ruff F401 would otherwise fail on an unused import, which is exactly the invariant this test relies on).

- [ ] **Step 1: Add the table to `EXPECTED_PII_TABLES`**

In `tests/unit/dsr/test_dsr_coverage.py`, add `"applicant_preferences"` to the `EXPECTED_PII_TABLES` frozenset (currently lines 41-55) — alongside `"applicants"`.

- [ ] **Step 2: Run**

Run: `uv run pytest tests/unit/dsr/test_dsr_coverage.py -v`
Expected: all PASS. If it fails, the failure message names exactly what's missing from which module — fix Task 10 or 11 accordingly rather than editing this test further.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/dsr/test_dsr_coverage.py
git commit -m "test(dsr): pin applicant_preferences into the PII coverage contract"
```

---

## Part E — Backend: sweep remaining fixture breakage

### Task 13: Fix every other `Applicant(locations=..., expected_ctc=...)` constructor call

**Files:**
- Modify: `tests/integration/test_wire_shapes.py`
- Modify: `tests/integration/test_applications_list.py`
- Modify: `tests/integration/test_feed.py`
- Modify: `tests/integration/test_save_unsave.py`
- Modify: `tests/integration/test_apply_dispatches_notifications.py`
- Modify: `tests/integration/test_apply.py`
- Modify: `tests/integration/test_models.py`
- Modify: `tests/integration/test_job_detail.py`
- Modify: `tests/integration/test_notifications_inbox.py`

**Interfaces:**
- No new interfaces — purely mechanical: every `Applicant(...)` call in these files that currently passes `locations=` and/or `expected_ctc=` must drop those kwargs (the columns no longer exist on the model, so leaving them in place is a `TypeError` at test-collection/run time, not a soft failure).

- [ ] **Step 1: Confirm the exact call sites**

Run: `grep -n "Applicant(" tests/integration/test_wire_shapes.py tests/integration/test_applications_list.py tests/integration/test_feed.py tests/integration/test_save_unsave.py tests/integration/test_apply_dispatches_notifications.py tests/integration/test_apply.py tests/integration/test_models.py tests/integration/test_job_detail.py tests/integration/test_notifications_inbox.py`

- [ ] **Step 2: For each match, remove `locations=`/`expected_ctc=` kwargs**

For every constructor call the grep surfaced, open the file at that line, read enough surrounding context to confirm the test doesn't depend on a *specific* location/CTC value driving structured-score behavior (none of these files score anything — they test wire shapes, application/save flows, feed pagination, job detail, and notifications — so in every one of these 9 files the value is incidental, not load-bearing), and remove the kwarg. Example (`test_wire_shapes.py:130`):

```python
    applicant = Applicant(user_id=user.id, full_name="Wire Shape")
```

Apply the equivalent mechanical edit at each remaining call site found in Step 1. Do not remove `locations=` from `Job(...)` constructor calls — `Job.locations` is a separate, untouched column; only `Applicant(...)` calls are affected.

- [ ] **Step 3: Run each touched file**

Run: `uv run pytest tests/integration/test_wire_shapes.py tests/integration/test_applications_list.py tests/integration/test_feed.py tests/integration/test_save_unsave.py tests/integration/test_apply_dispatches_notifications.py tests/integration/test_apply.py tests/integration/test_models.py tests/integration/test_job_detail.py tests/integration/test_notifications_inbox.py -v`
Expected: all PASS. If any test fails on an assertion (not a `TypeError`), stop — that test *did* depend on the removed value, and needs a paired `ApplicantPreferences` row instead of a bare kwarg removal (follow the pattern from Task 8 Step 3).

- [ ] **Step 4: Full backend test sweep**

Run: `uv run pytest -v -m "not integration and not eval" && uv run pytest -v -m integration`
Expected: all PASS — this is the first point where the full suite has run since Task 1, so treat any remaining failure as a signal there's another `Applicant(locations=...)` call site the Step 1 grep didn't cover (broaden the grep to all of `tests/` if so).

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_wire_shapes.py tests/integration/test_applications_list.py tests/integration/test_feed.py tests/integration/test_save_unsave.py tests/integration/test_apply_dispatches_notifications.py tests/integration/test_apply.py tests/integration/test_models.py tests/integration/test_job_detail.py tests/integration/test_notifications_inbox.py
git commit -m "test: drop locations/expected_ctc kwargs from Applicant() fixture calls"
```

---

### Task 14: Full backend CI-verbatim gate

**Files:** none (verification-only task)

- [ ] **Step 1: Run every CI-verbatim command**

```bash
uv run ruff check core/src api/src worker/src tests
uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration
```

Expected: all green. `-m eval` should be unaffected by this whole plan (it only exercises the resume parser against gold-dataset text, not the DB), but run it anyway since it's part of the CI-verbatim gate.

- [ ] **Step 2: If anything is red, fix it before moving to the frontend**

The backend half of this feature must be fully green before Part F begins — the Flutter DTOs in Part F are hand-written to match today's *intended* wire shape, and a red backend means that shape isn't actually what ships.

(No commit — this task is a checkpoint, not a code change.)

---

## Part F — Frontend: data layer

### Task 15: `DesiredRole` enum + `PreferencesDto`/`PreferencesUpdateDto`

**Files:**
- Create: `app/lib/data/preferences/desired_role.dart`
- Create: `app/lib/data/preferences/preferences_dto.dart`
- Create: `app/lib/data/preferences/preferences_update_dto.dart`

**Interfaces:**
- Produces: `DesiredRole` enum (16 values + `unknown`, mirroring `RoleCategory` — Task 1), `PreferencesDto` (mirrors `PreferencesRead`), `PreferencesUpdateDto` (mirrors `PreferencesUpdate`).

- [ ] **Step 1: `desired_role.dart`**

```dart
import 'package:json_annotation/json_annotation.dart';

/// Mirrors the backend RoleCategory StrEnum (core/src/jobify/db/models.py).
/// `unknown` is the forward-compat sentinel for an unrecognised wire value.
enum DesiredRole {
  @JsonValue('software_engineering')
  softwareEngineering,
  @JsonValue('data_analytics')
  dataAnalytics,
  @JsonValue('product_management')
  productManagement,
  @JsonValue('design')
  design,
  @JsonValue('sales')
  sales,
  @JsonValue('marketing')
  marketing,
  @JsonValue('customer_support')
  customerSupport,
  @JsonValue('operations')
  operations,
  @JsonValue('finance_accounting')
  financeAccounting,
  @JsonValue('hr_recruiting')
  hrRecruiting,
  @JsonValue('legal')
  legal,
  @JsonValue('consulting')
  consulting,
  @JsonValue('business_development')
  businessDevelopment,
  @JsonValue('content_communications')
  contentCommunications,
  @JsonValue('administration')
  administration,
  @JsonValue('other')
  other,
  unknown,
}

extension DesiredRoleLabel on DesiredRole {
  /// Display label for the dropdown. `unknown` should never reach the UI
  /// (the form only ever sends a real value or null), but a label avoids a
  /// crash if it somehow does.
  String get label => switch (this) {
        DesiredRole.softwareEngineering => 'Software Engineering',
        DesiredRole.dataAnalytics => 'Data & Analytics',
        DesiredRole.productManagement => 'Product Management',
        DesiredRole.design => 'Design',
        DesiredRole.sales => 'Sales',
        DesiredRole.marketing => 'Marketing',
        DesiredRole.customerSupport => 'Customer Support',
        DesiredRole.operations => 'Operations',
        DesiredRole.financeAccounting => 'Finance & Accounting',
        DesiredRole.hrRecruiting => 'HR & Recruiting',
        DesiredRole.legal => 'Legal',
        DesiredRole.consulting => 'Consulting',
        DesiredRole.businessDevelopment => 'Business Development',
        DesiredRole.contentCommunications => 'Content & Communications',
        DesiredRole.administration => 'Administration',
        DesiredRole.other => 'Other',
        DesiredRole.unknown => 'Unknown',
      };
}
```

- [ ] **Step 2: `preferences_dto.dart`**

```dart
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:json_annotation/json_annotation.dart';

part 'preferences_dto.g.dart';

/// Mirrors api `PreferencesRead` (routes/applicants.py).
@JsonSerializable(createToJson: false)
class PreferencesDto {
  const PreferencesDto({
    required this.desiredRole,
    required this.locations,
    required this.expectedCtc,
  });

  factory PreferencesDto.fromJson(Map<String, dynamic> json) =>
      _$PreferencesDtoFromJson(json);

  @JsonKey(name: 'desired_role', unknownEnumValue: DesiredRole.unknown)
  final DesiredRole? desiredRole;
  final List<String> locations;
  // Pydantic v2 serializes Decimal as a JSON string.
  @JsonKey(name: 'expected_ctc')
  final String? expectedCtc;

  bool get isComplete =>
      desiredRole != null && locations.isNotEmpty && expectedCtc != null;
}
```

- [ ] **Step 3: `preferences_update_dto.dart`**

```dart
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:json_annotation/json_annotation.dart';

part 'preferences_update_dto.g.dart';

/// Request body for PATCH /v1/applicants/me/preferences. Only non-null
/// fields the caller actually set should be included — callers build this
/// with just the fields they're changing (unlike ProfileUpdateDto, this is
/// NOT a full-form-always-sends-every-key DTO, since PreferencesScreen and
/// EditProfileScreen both partially update this resource).
@JsonSerializable(createFactory: false, includeIfNull: false)
class PreferencesUpdateDto {
  const PreferencesUpdateDto({
    this.desiredRole,
    this.locations,
    this.expectedCtc,
  });

  @JsonKey(name: 'desired_role')
  final DesiredRole? desiredRole;
  final List<String>? locations;
  @JsonKey(name: 'expected_ctc')
  final num? expectedCtc;

  Map<String, dynamic> toJson() => _$PreferencesUpdateDtoToJson(this);
}
```

- [ ] **Step 4: Generate code**

Run: `cd app && dart run build_runner build --delete-conflicting-outputs`
Expected: `preferences_dto.g.dart` and `preferences_update_dto.g.dart` are generated with no errors.

- [ ] **Step 5: Commit**

```bash
git add app/lib/data/preferences/
git commit -m "feat(app): DesiredRole enum + PreferencesDto/PreferencesUpdateDto"
```

---

### Task 16: `PreferencesApi` + `PreferencesRepository`

**Files:**
- Create: `app/lib/data/preferences/preferences_api.dart`
- Create: `app/lib/data/preferences/preferences_repository.dart`
- Create: `app/lib/data/preferences/preferences_repository_impl.dart`

**Interfaces:**
- Consumes: `PreferencesDto`, `PreferencesUpdateDto` (Task 15); `dioProvider`, `mapDioException` (existing, `jobify_app/data/api/`).
- Produces: `preferencesRepositoryProvider` (keepAlive), matching the `meRepository`/`resumeRepository` pattern exactly.

- [ ] **Step 1: `preferences_api.dart`**

```dart
import 'package:dio/dio.dart';

import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';

class PreferencesApi {
  PreferencesApi(this._dio);
  final Dio _dio;

  Future<PreferencesDto> get() async {
    final res =
        await _dio.get<Map<String, dynamic>>('/v1/applicants/me/preferences');
    return PreferencesDto.fromJson(res.data!);
  }

  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/applicants/me/preferences',
      data: update.toJson(),
    );
    return PreferencesDto.fromJson(res.data!);
  }
}
```

- [ ] **Step 2: `preferences_repository.dart`**

```dart
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';

abstract interface class PreferencesRepository {
  Future<PreferencesDto> fetch();
  Future<PreferencesDto> update(PreferencesUpdateDto update);
}
```

- [ ] **Step 3: `preferences_repository_impl.dart`**

```dart
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/preferences/preferences_api.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';

part 'preferences_repository_impl.g.dart';

class PreferencesRepositoryImpl implements PreferencesRepository {
  PreferencesRepositoryImpl(this._api);
  final PreferencesApi _api;

  @override
  Future<PreferencesDto> fetch() async {
    try {
      return await _api.get();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    try {
      return await _api.update(update);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
PreferencesRepository preferencesRepository(Ref ref) =>
    PreferencesRepositoryImpl(PreferencesApi(ref.read(dioProvider)));
```

- [ ] **Step 4: Generate code**

Run: `cd app && dart run build_runner build --delete-conflicting-outputs`
Expected: `preferences_repository_impl.g.dart` generated, no errors.

- [ ] **Step 5: Commit**

```bash
git add app/lib/data/preferences/
git commit -m "feat(app): PreferencesApi + PreferencesRepository"
```

---

### Task 17: Add `parsedJson` to `ResumeDto`; drop `locations`/`expectedCtc` from `MeDto`/`ProfileUpdateDto`

**Files:**
- Modify: `app/lib/data/resume/resume_dto.dart`
- Modify: `app/lib/data/me/me_dto.dart`
- Modify: `app/lib/data/me/profile_update_dto.dart`
- Modify: `app/test/unit/data/me/profile_update_dto_test.dart`

**Interfaces:**
- Produces: `ResumeDto.parsedJson: Map<String, dynamic>?`. `ApplicantSummaryDto` without `locations`/`expectedCtc`. `ProfileUpdateDto` without `locations`/`expectedCtc`.

- [ ] **Step 1: `resume_dto.dart`**

Add a field after `parseStatus` (currently line 32):

```dart
  @JsonKey(name: 'parse_status', unknownEnumValue: ResumeParseStatus.unknown)
  final ResumeParseStatus parseStatus;
  @JsonKey(name: 'parsed_json')
  final Map<String, dynamic>? parsedJson;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
```

And add `this.parsedJson,` to the constructor (optional, defaults null — keep every existing call site in tests compiling unchanged):

```dart
  const ResumeDto({
    required this.id,
    required this.applicantId,
    required this.originalFilename,
    required this.contentType,
    required this.sizeBytes,
    required this.parseStatus,
    this.parsedJson,
    required this.createdAt,
  });
```

- [ ] **Step 2: `me_dto.dart`**

In `ApplicantSummaryDto`, remove `locations`/`expectedCtc` from the constructor and fields (currently lines 41-79):

```dart
@JsonSerializable()
class ApplicantSummaryDto {
  const ApplicantSummaryDto({
    required this.id,
    required this.fullName,
    this.noticePeriodDays,
    this.currentCtc,
    this.yearsExperience,
  });

  factory ApplicantSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicantSummaryDtoFromJson(json);

  final String id;

  @JsonKey(name: 'full_name')
  final String? fullName;

  @JsonKey(name: 'notice_period_days')
  final int? noticePeriodDays;

  @JsonKey(name: 'current_ctc')
  final String? currentCtc;

  @JsonKey(name: 'years_experience')
  final String? yearsExperience;

  Map<String, dynamic> toJson() => _$ApplicantSummaryDtoToJson(this);
}
```

- [ ] **Step 3: `profile_update_dto.dart`**

```dart
import 'package:json_annotation/json_annotation.dart';

part 'profile_update_dto.g.dart';

/// Request body for PATCH /v1/applicants/me. locations/expected_ctc moved
/// to PreferencesUpdateDto (PATCH /v1/applicants/me/preferences).
@JsonSerializable(createFactory: false, includeIfNull: true)
class ProfileUpdateDto {
  const ProfileUpdateDto({
    required this.fullName,
    this.noticePeriodDays,
    this.currentCtc,
    this.yearsExperience,
  });

  @JsonKey(name: 'full_name')
  final String fullName;
  @JsonKey(name: 'notice_period_days')
  final int? noticePeriodDays;
  @JsonKey(name: 'current_ctc')
  final num? currentCtc;
  @JsonKey(name: 'years_experience')
  final num? yearsExperience;

  Map<String, dynamic> toJson() => _$ProfileUpdateDtoToJson(this);
}
```

- [ ] **Step 4: Fix `app/test/unit/data/me/profile_update_dto_test.dart`**

Read the file first. Remove any `locations:`/`expectedCtc:` arguments from `ProfileUpdateDto(...)` construction and any assertion on a `'locations'`/`'expected_ctc'` JSON key.

- [ ] **Step 5: Generate code**

Run: `cd app && dart run build_runner build --delete-conflicting-outputs`
Expected: regenerates `resume_dto.g.dart`, `me_dto.g.dart`, `profile_update_dto.g.dart` with no errors.

- [ ] **Step 6: Run the unit test**

Run: `cd app && flutter test test/unit/data/me/profile_update_dto_test.dart`
Expected: PASS. (Other tests referencing the removed fields will fail here — that's expected; Tasks 18-20 fix them.)

- [ ] **Step 7: Commit**

```bash
git add app/lib/data/resume/resume_dto.dart app/lib/data/me/me_dto.dart app/lib/data/me/profile_update_dto.dart app/test/unit/data/me/profile_update_dto_test.dart
git commit -m "feat(app): parsedJson on ResumeDto; drop locations/expectedCtc from MeDto/ProfileUpdateDto"
```

---

## Part G — Frontend: controllers + existing screens

### Task 18: `PreferencesController`

**Files:**
- Create: `app/lib/presentation/preferences/preferences_controller.dart`

**Interfaces:**
- Consumes: `preferencesRepositoryProvider` (Task 16).
- Produces: `preferencesControllerProvider` (`AsyncValue<PreferencesDto>`), `.refresh()`, `.submit(PreferencesUpdateDto)` — mirrors `ResumeController`/`ProfileEditController` exactly.

- [ ] **Step 1: Write the controller**

```dart
import 'dart:async';

import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'preferences_controller.g.dart';

@riverpod
class PreferencesController extends _$PreferencesController {
  @override
  Future<PreferencesDto> build() async =>
      ref.read(preferencesRepositoryProvider).fetch();

  Future<bool> submit(PreferencesUpdateDto update) async {
    state = const AsyncValue.loading();
    final result = await AsyncValue.guard(
      () => ref.read(preferencesRepositoryProvider).update(update),
    );
    if (result.hasError) {
      state = AsyncValue.error(result.error!, result.stackTrace!);
      return false;
    }
    state = AsyncValue.data(result.value as PreferencesDto);
    return true;
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
```

- [ ] **Step 2: Generate code**

Run: `cd app && dart run build_runner build --delete-conflicting-outputs`
Expected: `preferences_controller.g.dart` generated, no errors.

- [ ] **Step 3: Commit**

```bash
git add app/lib/presentation/preferences/preferences_controller.dart app/lib/presentation/preferences/preferences_controller.g.dart
git commit -m "feat(app): PreferencesController"
```

---

### Task 19: `EditProfileScreen` splits save into profile + preferences; adds a desired-role dropdown

**Files:**
- Modify: `app/lib/presentation/profile/edit_profile_screen.dart`
- Modify: `app/test/widget/edit_profile_screen_test.dart`

**Interfaces:**
- Consumes: `preferencesControllerProvider` (Task 18), `ProfileEditController` (existing, unchanged), `DesiredRole`/`DesiredRoleLabel` (Task 15).
- Produces: on Save, the screen fires both `ref.read(profileEditControllerProvider.notifier).submit(...)` (full_name/notice/current_ctc/years_experience) and `ref.read(preferencesControllerProvider.notifier).submit(...)` (desired_role/locations/expected_ctc), and only pops on success of both.

- [ ] **Step 1: Rewrite `edit_profile_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/profile/me_controller.dart';
import 'package:jobify_app/presentation/profile/profile_edit_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});
  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _fullName;
  late final TextEditingController _experience;
  late final TextEditingController _notice;
  late final TextEditingController _currentCtc;
  late final TextEditingController _expectedCtc;
  final _locationInput = TextEditingController();
  late List<String> _locations;
  DesiredRole? _desiredRole;

  @override
  void initState() {
    super.initState();
    final a = ref.read(meControllerProvider).value?.applicant;
    final prefs = ref.read(preferencesControllerProvider).value;
    _fullName = TextEditingController(text: a?.fullName ?? '');
    _experience = TextEditingController(text: a?.yearsExperience ?? '');
    _notice =
        TextEditingController(text: a?.noticePeriodDays?.toString() ?? '');
    _currentCtc = TextEditingController(text: a?.currentCtc ?? '');
    _expectedCtc = TextEditingController(text: prefs?.expectedCtc ?? '');
    _locations = List<String>.from(prefs?.locations ?? const []);
    _desiredRole = prefs?.desiredRole;
  }

  @override
  void dispose() {
    _fullName.dispose();
    _experience.dispose();
    _notice.dispose();
    _currentCtc.dispose();
    _expectedCtc.dispose();
    _locationInput.dispose();
    super.dispose();
  }

  void _addLocation() {
    final v = _locationInput.text.trim();
    if (v.isEmpty || _locations.contains(v)) return;
    final messenger = ScaffoldMessenger.of(context);
    if (v.length > 100) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Location too long (max 100 chars).')),
      );
      return;
    }
    if (_locations.length >= 10) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Up to 10 locations.')),
      );
      return;
    }
    setState(() {
      _locations.add(v);
      _locationInput.clear();
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final profileUpdate = ProfileUpdateDto(
      fullName: _fullName.text.trim(),
      noticePeriodDays: int.tryParse(_notice.text.trim()),
      currentCtc: num.tryParse(_currentCtc.text.trim()),
      yearsExperience: num.tryParse(_experience.text.trim()),
    );
    final preferencesUpdate = PreferencesUpdateDto(
      desiredRole: _desiredRole,
      locations: _locations,
      expectedCtc: num.tryParse(_expectedCtc.text.trim()),
    );
    final profileOk =
        await ref.read(profileEditControllerProvider.notifier).submit(profileUpdate);
    final prefsOk = await ref
        .read(preferencesControllerProvider.notifier)
        .submit(preferencesUpdate);
    if (!mounted) return;
    if (profileOk && prefsOk) {
      if (context.canPop()) context.pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't save. Try again.")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final saving = ref.watch(profileEditControllerProvider).isLoading ||
        ref.watch(preferencesControllerProvider).isLoading;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit Profile'),
        actions: [
          TextButton(
            onPressed: saving ? null : _save,
            child: Text(saving ? 'Saving…' : 'Save'),
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          children: [
            TextFormField(
              controller: _fullName,
              decoration: const InputDecoration(labelText: 'Full name'),
              validator: (v) {
                final t = v?.trim() ?? '';
                if (t.isEmpty) return 'Required';
                if (t.length > 200) return 'Too long (max 200)';
                return null;
              },
            ),
            const SizedBox(height: JobifySpacing.lg),
            DropdownButtonFormField<DesiredRole>(
              initialValue: _desiredRole,
              decoration: const InputDecoration(labelText: 'Desired role'),
              items: [
                for (final role in DesiredRole.values.where((r) => r != DesiredRole.unknown))
                  DropdownMenuItem(value: role, child: Text(role.label)),
              ],
              onChanged: (role) => setState(() => _desiredRole = role),
            ),
            const SizedBox(height: JobifySpacing.lg),
            Text('Locations', style: Theme.of(context).textTheme.labelLarge),
            Wrap(
              spacing: JobifySpacing.sm,
              children: [
                for (final loc in _locations)
                  Chip(
                    label: Text(loc),
                    onDeleted: () => setState(() => _locations.remove(loc)),
                  ),
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _locationInput,
                    decoration:
                        const InputDecoration(labelText: 'Add location'),
                    onSubmitted: (_) => _addLocation(),
                  ),
                ),
                IconButton(
                  onPressed: _addLocation,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
            const SizedBox(height: JobifySpacing.lg),
            TextFormField(
              controller: _experience,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              decoration:
                  const InputDecoration(labelText: 'Years of experience'),
              validator: (v) =>
                  _validateOptionalNumber(v, min: 0, max: 60, maxDecimals: 1),
            ),
            TextFormField(
              controller: _notice,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Notice period (days)'),
              validator: (v) =>
                  _validateOptionalNumber(v, min: 0, max: 365, maxDecimals: 0),
            ),
            TextFormField(
              controller: _currentCtc,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Current CTC (₹/yr)'),
              validator: (v) => _validateOptionalNumber(
                v,
                min: 0,
                max: 9999999999.99,
                maxDecimals: 2,
              ),
            ),
            TextFormField(
              controller: _expectedCtc,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Expected CTC (₹/yr)'),
              validator: (v) => _validateOptionalNumber(
                v,
                min: 0,
                max: 9999999999.99,
                maxDecimals: 2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Validate an optional numeric form field against the backend's bounds.
/// Empty is allowed (the field clears). Returns an error message, or null when
/// valid. `maxDecimals` mirrors the column scale (e.g. Numeric(4,1) → 1) so the
/// user is told instead of the DB silently rounding.
String? _validateOptionalNumber(
  String? raw, {
  required num min,
  required num max,
  required int maxDecimals,
}) {
  final t = raw?.trim() ?? '';
  if (t.isEmpty) return null;
  final n = num.tryParse(t);
  if (n == null) return 'Enter a number';
  if (n < min || n > max) return 'Must be between $min and $max';
  final dot = t.indexOf('.');
  if (dot >= 0 && t.length - dot - 1 > maxDecimals) {
    return maxDecimals == 0
        ? 'Whole number only'
        : 'At most $maxDecimals decimal place${maxDecimals == 1 ? '' : 's'}';
  }
  return null;
}
```

(`initState` reads `ref.read(preferencesControllerProvider).value` synchronously — this only has data if something already warmed that provider before this screen mounted. `ProfileScreen`, Task 20, watches `preferencesControllerProvider` on the screen the user navigates from, so by the time they tap "Edit" the cache is warm. The widget test in Step 2 below warms it explicitly, matching the existing `meControllerProvider` warm-up pattern.)

- [ ] **Step 2: Rewrite `edit_profile_screen_test.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/profile/edit_profile_screen.dart';
import 'package:jobify_app/presentation/profile/me_controller.dart';

class _CapturingMeRepo implements MeRepository {
  ProfileUpdateDto? captured;
  @override
  Future<MeDto> fetch() async => const MeDto(
        id: 'u1',
        email: 'e@e.com',
        role: 'applicant',
        applicant: ApplicantSummaryDto(id: 'a1', fullName: 'Alice'),
      );
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    captured = update;
    return fetch();
  }
}

class _CapturingPrefsRepo implements PreferencesRepository {
  PreferencesUpdateDto? captured;
  @override
  Future<PreferencesDto> fetch() async => const PreferencesDto(
        desiredRole: null,
        locations: ['Pune'],
        expectedCtc: null,
      );
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    captured = update;
    return fetch();
  }
}

void main() {
  testWidgets('renders seeded values, adds a chip, saves both endpoints',
      (tester) async {
    final meRepo = _CapturingMeRepo();
    final prefsRepo = _CapturingPrefsRepo();
    final container = ProviderContainer(
      overrides: [
        meRepositoryProvider.overrideWithValue(meRepo),
        preferencesRepositoryProvider.overrideWithValue(prefsRepo),
      ],
    );
    addTearDown(container.dispose);
    await container.read(meControllerProvider.future);
    await container.read(preferencesControllerProvider.future);

    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const EditProfileScreen()),
      ],
    );

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Pune'), findsOneWidget); // seeded chip

    await tester.enterText(
      find.widgetWithText(TextField, 'Add location'),
      'Mumbai',
    );
    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    expect(find.text('Mumbai'), findsOneWidget);

    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(meRepo.captured, isNotNull);
    expect(meRepo.captured!.fullName, 'Alice');
    expect(prefsRepo.captured, isNotNull);
    expect(prefsRepo.captured!.locations, ['Pune', 'Mumbai']);
  });

  testWidgets('out-of-range experience blocks save', (tester) async {
    final meRepo = _CapturingMeRepo();
    final prefsRepo = _CapturingPrefsRepo();
    final container = ProviderContainer(
      overrides: [
        meRepositoryProvider.overrideWithValue(meRepo),
        preferencesRepositoryProvider.overrideWithValue(prefsRepo),
      ],
    );
    addTearDown(container.dispose);
    await container.read(meControllerProvider.future);
    await container.read(preferencesControllerProvider.future);

    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const EditProfileScreen()),
      ],
    );
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Years of experience'),
      '99', // exceeds max 60
    );
    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(find.text('Must be between 0 and 60'), findsOneWidget);
    expect(meRepo.captured, isNull); // save was blocked by validation
    expect(prefsRepo.captured, isNull);
  });
}
```

- [ ] **Step 3: Run**

Run: `cd app && flutter test test/widget/edit_profile_screen_test.dart`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/profile/edit_profile_screen.dart app/test/widget/edit_profile_screen_test.dart
git commit -m "feat(app): EditProfileScreen saves profile + preferences; adds desired-role dropdown"
```

---

### Task 20: `ProfileScreen` reads location/CTC/desired-role from `preferencesControllerProvider`

**Files:**
- Modify: `app/lib/presentation/profile/profile_screen.dart`
- Modify: `app/test/widget/profile_screen_test.dart`

**Interfaces:**
- Consumes: `preferencesControllerProvider` (Task 18).

- [ ] **Step 1: Edit `profile_screen.dart`**

Add the import:

```dart
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
```

In `build`, add a `preferences` watch alongside `me`:

```dart
    final me = ref.watch(meControllerProvider);
    final preferences = ref.watch(preferencesControllerProvider);
```

Replace the `if (data.applicant case final a?) ...[` block (currently lines 70-91) — the `Locations`/`Expected CTC` rows now read from `preferences.value`, and a `Desired role` row is added:

```dart
            if (data.applicant case final a?) ...[
              const SizedBox(height: JobifySpacing.xl),
              if (preferences.value case final p?) ...[
                _DetailRow(
                  label: 'Desired role',
                  value: p.desiredRole?.label ?? '—',
                ),
                _DetailRow(
                  label: 'Locations',
                  value: p.locations.isEmpty ? '—' : p.locations.join(', '),
                ),
              ],
              if (formatYears(a.yearsExperience) case final years?)
                _DetailRow(label: 'Experience', value: years),
              if (a.noticePeriodDays != null)
                _DetailRow(
                  label: 'Notice period',
                  value: '${a.noticePeriodDays} days',
                ),
              _DetailRow(
                label: 'Current CTC',
                value: formatCtc(a.currentCtc),
              ),
              if (preferences.value case final p?)
                _DetailRow(
                  label: 'Expected CTC',
                  value: formatCtc(p.expectedCtc),
                ),
            ],
```

Add `DesiredRoleLabel` import for the `.label` extension:

```dart
import 'package:jobify_app/data/preferences/desired_role.dart';
```

- [ ] **Step 2: Fix `profile_screen_test.dart`**

Read the file fully (already read during planning — 121 lines). It builds `ApplicantSummaryDto` with `locations: ['Pune']` and `expectedCtc: '1800000.00'` — those constructor args no longer exist on `ApplicantSummaryDto` (Task 17). Update:

```dart
const _me = MeDto(
  id: 'u1',
  email: 'eng@example.com',
  displayName: 'Eng U',
  role: 'applicant',
  applicant: ApplicantSummaryDto(id: 'a1', fullName: 'Eng U'),
);
```

Add a `_CapturingPrefsRepo`-style fake (or a minimal `_FakePrefsRepo`) and override `preferencesRepositoryProvider` in `_buildScope`:

```dart
class _FakePrefsRepo implements PreferencesRepository {
  @override
  Future<PreferencesDto> fetch() async => const PreferencesDto(
        desiredRole: null,
        locations: ['Pune'],
        expectedCtc: '1800000.00',
      );
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async => fetch();
}
```

Add the corresponding imports (`PreferencesDto`, `PreferencesRepository`, `PreferencesRepositoryImpl`'s `preferencesRepositoryProvider`, `PreferencesUpdateDto`), and add `preferencesRepositoryProvider.overrideWithValue(_FakePrefsRepo()),` to the `overrides` list in `_buildScope` (currently lines 41-53).

- [ ] **Step 3: Run**

Run: `cd app && flutter test test/widget/profile_screen_test.dart`
Expected: PASS (the existing `expect(find.text('Locations'), findsOneWidget); expect(find.text('Pune'), findsOneWidget);` assertions at lines 72-73 should still pass since `p.locations` still contains `'Pune'`, just sourced differently now).

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/profile/profile_screen.dart app/test/widget/profile_screen_test.dart
git commit -m "feat(app): ProfileScreen reads location/CTC/desired-role from preferences"
```

---

## Part H — Frontend: the new screen, navigation trigger, nudge banner

### Task 21: `PreferencesScreen`

**Files:**
- Create: `app/lib/presentation/preferences/preferences_screen.dart`
- Create: `app/test/widget/preferences_screen_test.dart`

**Interfaces:**
- Consumes: `preferencesControllerProvider` (Task 18), `ResumeDto.parsedJson` (Task 17) passed in as an optional constructor argument.
- Produces: a routable widget `PreferencesScreen({ResumeDto? resume})`.

- [ ] **Step 1: Write `preferences_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class PreferencesScreen extends ConsumerStatefulWidget {
  const PreferencesScreen({super.key, this.resume});

  final ResumeDto? resume;

  @override
  ConsumerState<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends ConsumerState<PreferencesScreen> {
  final _formKey = GlobalKey<FormState>();
  final _locationInput = TextEditingController();
  late final TextEditingController _expectedCtc;
  List<String> _locations = [];
  DesiredRole? _desiredRole;
  bool _seeded = false;

  @override
  void initState() {
    super.initState();
    _expectedCtc = TextEditingController();
  }

  void _seedFromPreferences(PreferencesDto? prefs) {
    if (_seeded || prefs == null) return;
    _seeded = true;
    _desiredRole = prefs.desiredRole;
    _locations = List<String>.from(prefs.locations);
    _expectedCtc.text = prefs.expectedCtc ?? '';
  }

  @override
  void dispose() {
    _locationInput.dispose();
    _expectedCtc.dispose();
    super.dispose();
  }

  void _addLocation() {
    final v = _locationInput.text.trim();
    if (v.isEmpty || _locations.contains(v) || v.length > 100 || _locations.length >= 10) {
      return;
    }
    setState(() {
      _locations.add(v);
      _locationInput.clear();
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final update = PreferencesUpdateDto(
      desiredRole: _desiredRole,
      locations: _locations,
      expectedCtc: num.tryParse(_expectedCtc.text.trim()),
    );
    final ok =
        await ref.read(preferencesControllerProvider.notifier).submit(update);
    if (!mounted) return;
    if (ok) {
      if (context.canPop()) context.pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't save. Try again.")),
      );
    }
  }

  void _skip() {
    if (context.canPop()) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final prefsState = ref.watch(preferencesControllerProvider);
    _seedFromPreferences(prefsState.value);
    final saving = prefsState.isLoading && _seeded;

    return Scaffold(
      appBar: AppBar(
        title: const Text("What are you looking for?"),
        actions: [
          TextButton(onPressed: _skip, child: const Text('Skip')),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          children: [
            _ResumeSummaryCard(resume: widget.resume),
            const SizedBox(height: JobifySpacing.xl),
            DropdownButtonFormField<DesiredRole>(
              initialValue: _desiredRole,
              decoration: const InputDecoration(labelText: 'Desired role'),
              items: [
                for (final role in DesiredRole.values.where((r) => r != DesiredRole.unknown))
                  DropdownMenuItem(value: role, child: Text(role.label)),
              ],
              onChanged: (role) => setState(() => _desiredRole = role),
            ),
            const SizedBox(height: JobifySpacing.lg),
            Text('Locations', style: Theme.of(context).textTheme.labelLarge),
            Wrap(
              spacing: JobifySpacing.sm,
              children: [
                for (final loc in _locations)
                  Chip(
                    label: Text(loc),
                    onDeleted: () => setState(() => _locations.remove(loc)),
                  ),
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _locationInput,
                    decoration:
                        const InputDecoration(labelText: 'Add location'),
                    onSubmitted: (_) => _addLocation(),
                  ),
                ),
                IconButton(onPressed: _addLocation, icon: const Icon(Icons.add)),
              ],
            ),
            const SizedBox(height: JobifySpacing.lg),
            TextFormField(
              controller: _expectedCtc,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Expected CTC (₹/yr)'),
            ),
            const SizedBox(height: JobifySpacing.xl),
            FilledButton(
              onPressed: saving ? null : _save,
              child: Text(saving ? 'Saving…' : 'Save'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResumeSummaryCard extends StatelessWidget {
  const _ResumeSummaryCard({required this.resume});
  final ResumeDto? resume;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final parsed = resume?.parsedJson;
    if (resume == null) return const SizedBox.shrink();
    if (parsed == null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          child: Text(
            "We couldn't read your résumé — tell us directly below.",
            style: theme.textTheme.bodyMedium,
          ),
        ),
      );
    }
    final name = parsed['name'] as String?;
    final skills = (parsed['skills'] as List?)?.cast<String>() ?? const [];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(JobifySpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Your résumé', style: theme.textTheme.titleMedium),
            const SizedBox(height: JobifySpacing.xs),
            if (name != null) Text(name, style: theme.textTheme.bodyMedium),
            if (skills.isNotEmpty) ...[
              const SizedBox(height: JobifySpacing.sm),
              Wrap(
                spacing: JobifySpacing.sm,
                children: [
                  for (final s in skills.take(10)) Chip(label: Text(s)),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Write `preferences_screen_test.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/data/resume/resume_parse_status.dart';
import 'package:jobify_app/presentation/preferences/preferences_screen.dart';

class _CapturingRepo implements PreferencesRepository {
  PreferencesUpdateDto? captured;
  @override
  Future<PreferencesDto> fetch() async =>
      const PreferencesDto(desiredRole: null, locations: [], expectedCtc: null);
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    captured = update;
    return fetch();
  }
}

ResumeDto _resumeWithParsed() => ResumeDto(
      id: 'r1',
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: ResumeParseStatus.parsed,
      parsedJson: const {
        'name': 'Ada Lovelace',
        'skills': ['Python', 'SQL'],
      },
      createdAt: DateTime(2026),
    );

Future<void> _pump(
  WidgetTester tester, {
  required PreferencesRepository repo,
  ResumeDto? resume,
}) async {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, __) => PreferencesScreen(resume: resume),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [preferencesRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows parsed résumé summary', (tester) async {
    await _pump(tester, repo: _CapturingRepo(), resume: _resumeWithParsed());
    expect(find.text('Ada Lovelace'), findsOneWidget);
    expect(find.text('Python'), findsOneWidget);
  });

  testWidgets('shows fallback when resume has no parsed data', (tester) async {
    final resume = ResumeDto(
      id: 'r1',
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: ResumeParseStatus.failed,
      createdAt: DateTime(2026),
    );
    await _pump(tester, repo: _CapturingRepo(), resume: resume);
    expect(find.textContaining("couldn't read your résumé"), findsOneWidget);
  });

  testWidgets('adds a location and saves', (tester) async {
    final repo = _CapturingRepo();
    await _pump(tester, repo: repo, resume: _resumeWithParsed());

    await tester.enterText(
      find.widgetWithText(TextField, 'Add location'),
      'Pune',
    );
    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    expect(find.text('Pune'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();

    expect(repo.captured, isNotNull);
    expect(repo.captured!.locations, ['Pune']);
  });

  testWidgets('skip navigates away without saving', (tester) async {
    final repo = _CapturingRepo();
    await _pump(tester, repo: repo, resume: _resumeWithParsed());
    await tester.tap(find.widgetWithText(TextButton, 'Skip'));
    await tester.pumpAndSettle();
    expect(repo.captured, isNull);
  });
}
```

- [ ] **Step 3: Run**

Run: `cd app && flutter test test/widget/preferences_screen_test.dart`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/preferences/preferences_screen.dart app/test/widget/preferences_screen_test.dart
git commit -m "feat(app): PreferencesScreen — resume summary + role/location/CTC form"
```

---

### Task 22: Route wiring

**Files:**
- Modify: `app/lib/presentation/routing/routes.dart`
- Modify: `app/lib/presentation/routing/router.dart`

**Interfaces:**
- Produces: `Routes.preferences = '/profile/preferences'`; a `GoRoute` reachable via `context.push('${Routes.profile}/preferences', extra: resume)`.

- [ ] **Step 1: Add the route constant**

In `app/lib/presentation/routing/routes.dart`, add after `static const resume = '/profile/resume';`:

```dart
  static const preferences = '/profile/preferences';
```

- [ ] **Step 2: Add the `GoRoute`**

In `app/lib/presentation/routing/router.dart`, add the import:

```dart
import 'package:jobify_app/presentation/preferences/preferences_screen.dart';
```

Insert a new `GoRoute` right after the `resume` route (currently lines 170-173), reading `ResumeDto` from `state.extra`:

```dart
                  GoRoute(
                    path: 'resume',
                    builder: (_, __) => const ResumeScreen(),
                  ),
                  GoRoute(
                    path: 'preferences',
                    builder: (_, s) =>
                        PreferencesScreen(resume: s.extra as ResumeDto?),
                  ),
```

Add the `ResumeDto` import if not already present in this file:

```dart
import 'package:jobify_app/data/resume/resume_dto.dart';
```

- [ ] **Step 3: Verify it compiles**

Run: `cd app && flutter analyze`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/routing/routes.dart app/lib/presentation/routing/router.dart
git commit -m "feat(app): route /profile/preferences"
```

---

### Task 23: `ResumeScreen` navigates to `PreferencesScreen` once parsing settles and preferences are incomplete

**Files:**
- Modify: `app/lib/presentation/resume/resume_screen.dart`
- Modify: `app/test/widget/resume_screen_test.dart`

**Interfaces:**
- Consumes: `preferencesControllerProvider` (Task 18), `Routes.preferences` (Task 22).
- Produces: after either of the existing 2s/5s delayed refreshes observes `parseStatus` in `{parsed, failed}`, and the cached preferences are incomplete, the screen pushes `Routes.preferences` with the resume attached — exactly once (a `_navigatedForResumeId` guard prevents re-navigating on every subsequent refresh once the user has already been sent there or the resume settles again).

- [ ] **Step 1: Edit `resume_screen.dart`**

Add imports:

```dart
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
```

Add a guard field and change `_refreshIfMounted` to check completeness after refreshing:

```dart
class _ResumeScreenState extends ConsumerState<ResumeScreen> {
  String? _navigatedForResumeId;

  Future<void> _pickAndUpload() async {
    ...
  }

  Future<void> _refreshIfMounted() async {
    if (!mounted) return;
    await ref.read(resumeControllerProvider.notifier).refresh();
    if (!mounted) return;
    await _maybeNavigateToPreferences();
  }

  Future<void> _maybeNavigateToPreferences() async {
    final resume = ref.read(resumeControllerProvider).value;
    if (resume == null) return;
    if (resume.parseStatus != ResumeParseStatus.parsed &&
        resume.parseStatus != ResumeParseStatus.failed) {
      return;
    }
    if (_navigatedForResumeId == resume.id) return;

    final prefs = await AsyncValue.guard(
      () => ref.read(preferencesControllerProvider.future),
    ).then((r) => r.valueOrNull);
    if (!mounted || prefs == null || prefs.isComplete) return;

    _navigatedForResumeId = resume.id;
    context.push(Routes.preferences, extra: resume);
  }
```

Change the two `Future.delayed(...)` calls in `_pickAndUpload` (currently lines 53-54) to call the now-`Future<void>`-returning `_refreshIfMounted` the same way (no change needed there — `Future.delayed` accepts any zero-arg callback and ignores the returned future, which is fine here since nothing awaits it).

- [ ] **Step 2: Add a navigation test to `resume_screen_test.dart`**

Read the existing file fully first (already read during planning). Add:

```dart
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/presentation/preferences/preferences_screen.dart';
```

```dart
class _IncompletePrefsRepo implements PreferencesRepository {
  @override
  Future<PreferencesDto> fetch() async =>
      const PreferencesDto(desiredRole: null, locations: [], expectedCtc: null);
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async => fetch();
}
```

```dart
  testWidgets('navigates to preferences after parse settles when incomplete',
      (tester) async {
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const ResumeScreen()),
        GoRoute(
          path: '/profile/preferences',
          builder: (_, s) => PreferencesScreen(resume: s.extra as ResumeDto?),
        ),
      ],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          resumeRepositoryProvider
              .overrideWithValue(_Repo(_dto(ResumeParseStatus.parsed))),
          preferencesRepositoryProvider
              .overrideWithValue(_IncompletePrefsRepo()),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final state = tester.state<State<ResumeScreen>>(find.byType(ResumeScreen));
    // ignore: invalid_use_of_protected_member
    await (state as dynamic)._maybeNavigateToPreferences() as Future<void>;
    await tester.pumpAndSettle();

    expect(find.byType(PreferencesScreen), findsOneWidget);
  });
```

(Calling `_maybeNavigateToPreferences` directly via `dynamic` — rather than waiting out the real 2s/5s `Future.delayed` timers — keeps the test fast and deterministic; `flutter_test`'s fake async clock doesn't play well with real `Future.delayed` chains mixed with `pumpAndSettle`. This mirrors how the codebase already avoids real timers in widget tests elsewhere.)

- [ ] **Step 3: Run**

Run: `cd app && flutter test test/widget/resume_screen_test.dart`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/resume/resume_screen.dart app/test/widget/resume_screen_test.dart
git commit -m "feat(app): ResumeScreen navigates to PreferencesScreen once parse settles"
```

---

### Task 24: Feed nudge banner

**Files:**
- Create: `app/lib/presentation/feed/feed_nudge_banner.dart`
- Modify: `app/lib/presentation/feed/feed_screen.dart`
- Modify: `app/test/widget/feed_screen_test.dart`

**Interfaces:**
- Consumes: `resumeControllerProvider` (existing), `preferencesControllerProvider` (Task 18).
- Produces: `FeedNudgeBanner` widget — renders one of 3 states (no resume / resume-but-incomplete-preferences / nothing) with no dismiss control, purely derived from provider state.

- [ ] **Step 1: Write `feed_nudge_banner.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/resume/resume_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

/// Derived, non-dismissible nudge shown above the feed. Fully computed from
/// resume + preferences state — no stored "dismissed" flag, so it simply
/// stops rendering once the underlying data is complete.
class FeedNudgeBanner extends ConsumerWidget {
  const FeedNudgeBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resume = ref.watch(resumeControllerProvider).value;
    if (resume == null) {
      return _Banner(
        text: 'Upload your résumé so we can find you better roles.',
        actionLabel: 'Upload',
        onTap: () => context.push(Routes.resume),
      );
    }
    final prefs = ref.watch(preferencesControllerProvider).value;
    if (prefs != null && !prefs.isComplete) {
      return _Banner(
        text: "Tell us what you're looking for.",
        actionLabel: 'Answer',
        onTap: () => context.push(Routes.preferences, extra: resume),
      );
    }
    return const SizedBox.shrink();
  }
}

class _Banner extends StatelessWidget {
  const _Banner({
    required this.text,
    required this.actionLabel,
    required this.onTap,
  });

  final String text;
  final String actionLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: JobifySpacing.md),
      color: theme.colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(JobifySpacing.md),
        child: Row(
          children: [
            Expanded(
              child: Text(
                text,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onPrimaryContainer),
              ),
            ),
            TextButton(onPressed: onTap, child: Text(actionLabel)),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Insert the banner into `feed_screen.dart`**

Add the import:

```dart
import 'package:jobify_app/presentation/feed/feed_nudge_banner.dart';
```

Wrap the `AsyncValueWidget<FeedState>` (currently lines 53-109) inside a `Column`, with the banner above it:

```dart
      child: Column(
        children: [
          const FeedNudgeBanner(),
          Expanded(
            child: AsyncValueWidget<FeedState>(
              value: value,
              onRetry: () => ref.read(feedControllerProvider.notifier).refresh(),
              isEmpty: (s) => s.items.isEmpty,
              empty: () => const JobifyEmptyState(
                headline: "We're still looking for matches",
                body: 'Upload a resume to help us find you better roles.',
                icon: Icons.search_off,
              ),
              data: (s) => RefreshIndicator(
                onRefresh: () =>
                    ref.read(feedControllerProvider.notifier).refresh(),
                child: ListView.separated(
                  controller: _scroll,
                  padding: const EdgeInsets.all(JobifySpacing.lg),
                  itemCount: s.items.length + 1,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: JobifySpacing.md),
                  itemBuilder: (context, i) {
                    if (i == s.items.length) {
                      if (s.isLoadingMore) {
                        return const Padding(
                          padding: EdgeInsets.all(JobifySpacing.lg),
                          child: JobifyLoadingView(),
                        );
                      }
                      if (!s.hasMore) {
                        return Padding(
                          padding: const EdgeInsets.all(JobifySpacing.lg),
                          child: Center(
                            child: Text(
                              "You're all caught up",
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                            ),
                          ),
                        );
                      }
                      return const SizedBox.shrink();
                    }
                    final item = s.items[i];
                    return Arrive(
                      index: i,
                      child: FeedItemCard(
                        job: item.job,
                        employer: item.employer,
                        onTap: () =>
                            context.go('${Routes.feed}/jobs/${item.job.id}'),
                        match: item.match,
                        explanation: item.match.explanation,
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
```

(The banner sits outside the `padding: JobifySpacing.lg` `ListView`, so give `FeedNudgeBanner`'s own `_Banner` its own horizontal margin if it looks flush against the screen edge in a manual check — not required for the tests below, but worth a visual check per this repo's "test the golden path in a browser/emulator" convention.)

- [ ] **Step 3: Update `feed_screen_test.dart`**

The existing `_wrap` helper only overrides `feedRepositoryProvider`. Add overrides for the two new providers so the banner renders deterministically:

```dart
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/data/resume/resume_parse_status.dart';
import 'package:jobify_app/data/resume/resume_repository.dart';
import 'package:jobify_app/data/resume/resume_repository_impl.dart';
```

```dart
class _FakeResumeRepo implements ResumeRepository {
  _FakeResumeRepo(this._current);
  final ResumeDto? _current;
  @override
  Future<ResumeDto?> current() async => _current;
  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async =>
      throw UnimplementedError();
}

class _FakePrefsRepo implements PreferencesRepository {
  _FakePrefsRepo(this._dto);
  final PreferencesDto _dto;
  @override
  Future<PreferencesDto> fetch() async => _dto;
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async => _dto;
}

const _completeResume = ResumeDto(
  id: 'r1',
  applicantId: 'a1',
  originalFilename: 'cv.pdf',
  contentType: 'application/pdf',
  sizeBytes: 1,
  parseStatus: ResumeParseStatus.parsed,
  createdAt: null, // set below — DateTime isn't const-constructible with a literal here
);
```

(Since `DateTime` isn't `const`-constructible inline, drop the `const` and build `_completeResume` as a plain top-level `final` using `DateTime(2026)`, matching `resume_screen_test.dart`'s `_dto` helper pattern.)

```dart
final _completeResumeDto = ResumeDto(
  id: 'r1',
  applicantId: 'a1',
  originalFilename: 'cv.pdf',
  contentType: 'application/pdf',
  sizeBytes: 1,
  parseStatus: ResumeParseStatus.parsed,
  createdAt: DateTime(2026),
);

const _completePrefs = PreferencesDto(
  desiredRole: DesiredRole.softwareEngineering,
  locations: ['Pune'],
  expectedCtc: '1800000.00',
);

const _incompletePrefs =
    PreferencesDto(desiredRole: null, locations: [], expectedCtc: null);
```

Update `_wrap` to accept and apply resume/preferences overrides, defaulting to the "everything complete, no banner" case so the two pre-existing tests keep passing unchanged:

```dart
Widget _wrap(
  Widget child, {
  required FeedRepository repo,
  ResumeDto? resume = _completeResumeDto,
  PreferencesDto prefs = _completePrefs,
}) {
  return ProviderScope(
    overrides: [
      feedRepositoryProvider.overrideWithValue(repo),
      resumeRepositoryProvider.overrideWithValue(_FakeResumeRepo(resume)),
      preferencesRepositoryProvider.overrideWithValue(_FakePrefsRepo(prefs)),
    ],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: child,
    ),
  );
}
```

Add `DesiredRole` import (`package:jobify_app/data/preferences/desired_role.dart`) for `_completePrefs`.

Add 2 new tests at the end of `main()`:

```dart
  testWidgets('shows upload nudge when no resume', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        resume: null,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Upload your résumé'), findsOneWidget);
  });

  testWidgets('shows preferences nudge when resume exists but incomplete',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        prefs: _incompletePrefs,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining("what you're looking for"), findsOneWidget);
  });

  testWidgets('no banner when resume and preferences are complete',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Upload your résumé'), findsNothing);
    expect(find.textContaining("what you're looking for"), findsNothing);
  });
```

- [ ] **Step 4: Run**

Run: `cd app && flutter test test/widget/feed_screen_test.dart`
Expected: all PASS (including the 4 pre-existing tests, now exercising the default complete-state overrides).

- [ ] **Step 5: Commit**

```bash
git add app/lib/presentation/feed/feed_nudge_banner.dart app/lib/presentation/feed/feed_screen.dart app/test/widget/feed_screen_test.dart
git commit -m "feat(app): feed nudge banner for missing resume / incomplete preferences"
```

---

### Task 25: Full frontend CI-verbatim gate

**Files:** none (verification-only task)

- [ ] **Step 1: Run every CI-verbatim command**

```bash
cd app
dart format --set-exit-if-changed lib test
flutter analyze
flutter test
```

Expected: all green.

- [ ] **Step 2: Manual golden-path check**

Per this repo's convention, verify the change with a real running app before calling it done: start the backend + web app (`scripts/start-all.sh`, or the individual `api`/`worker`/`app` run commands from their READMEs), sign in as a fresh applicant, upload a resume, wait for it to parse, confirm the `PreferencesScreen` appears with the parsed summary, save the 3 answers, confirm the feed banner is gone, then sign in as a second fresh applicant and confirm the feed shows the "upload your résumé" banner before any upload.

(No commit — this task is a checkpoint, not a code change.)

---

## Part I — Wrap-up

### Task 26: Regenerate the OpenAPI snapshot pin (if this repo has one)

**Files:**
- Check for: an OpenAPI snapshot file referenced by `jobify-arch-hardening-guards` (per `core/CLAUDE.md` / project memory) — grep for it before assuming its path.

- [ ] **Step 1: Locate the snapshot**

Run: `grep -rl "openapi.json\|app.openapi()" tests/ core/ api/ --include="*.py" | grep -i snapshot`

- [ ] **Step 2: Regenerate it**

If a snapshot test/fixture exists, follow whatever regeneration command its own test docstring or a nearby README section specifies (this plan intentionally does not guess the exact command — verify it first). Expected: the diff shows exactly the new routes/schemas this plan added (`/v1/applicants/me/preferences` GET+PATCH, `ResumeRead.parsed_json`, `UserExport.applicant_preferences`, `ApplicantRead` losing 2 fields, `ProfileUpdate` losing 2 fields) — a large unrelated diff means something broke.

- [ ] **Step 3: Commit**

```bash
git add <snapshot-file>
git commit -m "chore: regenerate OpenAPI snapshot for the preferences feature"
```

---

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** every section of `docs/superpowers/specs/2026-07-01-resume-review-preferences-design.md` maps to a task — data model (Tasks 1-3), API (Tasks 4, 6-7), scoring repoint (Tasks 8-9), DSR (Tasks 10-12), frontend flow (Tasks 15-24), out-of-scope items (matching/scoring wiring for `desired_role`, profile-edit-routes-through-guided-flow, backfill) are deliberately absent from this plan, matching the spec's "Explicitly out of scope" section.
- **Ground truth corrections made during planning** (not in the original spec, discovered by reading real code): `ResumeRead` did not already expose `parsed_json` (Task 4 adds it); `score_applicant.py`/`score_job.py` read `Applicant.locations`/`expected_ctc` directly as scoring inputs, not via the embedding (Tasks 8-9); the eager-provisioning pattern (`_upsert_identity` already seeds consents at signup) is reused for `ApplicantPreferences` rather than inventing a lazy-create-on-GET path (Task 3) — this also simplifies the scoring workers' join logic.
- **If a grep in Task 13 or Task 9 Step 2 turns up a test file not explicitly enumerated here**, treat that as the plan being incomplete for that file, not a signal to skip it — apply the same mechanical fix pattern shown for the enumerated files.
