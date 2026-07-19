# Match Feedback Capture + Admin Match QA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Applicants rate surfaced matches thumbs up/down (down hides the job from their feed); admins get a Match QA console page with the relevance metric and a filterable rated-matches list.

**Architecture:** New `match_feedback` table keyed on `(applicant_id, job_id)` (survives match-row rescore UPSERTs), wired into DSR export+delete. Applicant PUT/DELETE routes mirror the saved-jobs precedent; the feed query grows one outer join that both excludes thumbs-down jobs and surfaces `my_feedback`; admin list/summary follow the existing admin cursor pattern. Flutter adds thumbs to feed cards (optimistic removal + Undo) and a rating row in job detail; the console gets a Match QA page.

**Tech Stack:** SQLAlchemy 2 async + Alembic (hand-written), FastAPI + Pydantic v2, pytest (unit/integration markers), Flutter + Riverpod 4 codegen + json_serializable (`field_rename: snake`), React/Vite console.

**Spec:** `docs/superpowers/specs/2026-07-19-match-feedback-design.md`

## Global Constraints

- All backend commands run from the **repo root** with `uv run …`; Alembic runs from `core/` (`cd core && uv run alembic upgrade head`).
- CI verbatim gates (run before claiming any task green): `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -m integration` (integration needs local Postgres; `jobify_test` DB). Flutter: `dart format --set-exit-if-changed lib test` · `flutter analyze` · `flutter test` (from `app/`). Frontend: `npm run build` (from `frontend/`).
- Soft delete everywhere: `deleted_at TIMESTAMPTZ NULL`, live queries filter it, uniqueness via partial index `WHERE deleted_at IS NULL`, reuse the `Annotated` types in `core/src/jobify/db/models.py`.
- Hand-written migrations only (autogenerate off); both `upgrade` and `downgrade`.
- `structlog.get_logger(__name__)` only; all handlers `async def`; SQLAlchemy models never used as response schemas.
- Wire format is snake_case; Flutter DTOs get it automatically from `app/build.yaml` (`field_rename: snake`) — only add `@JsonKey(name:)` when the wire key ≠ snake_case of the field.
- Any OpenAPI-visible change requires `JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py` and committing the snapshot diff.
- Rating vocabulary is exactly `"up"` / `"down"` (varchar+CHECK in DB, `Literal`/enum at boundaries). Never a native PG enum.
- Commit after every task (at minimum); `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

---

### Task 1: Branch, `MatchFeedback` model, migration 0025

**Files:**
- Modify: `core/src/jobify/db/models.py` (add enum + model after `SavedJob`, which ends near line 770)
- Create: `core/src/jobify/db/migrations/versions/0025_match_feedback.py`

**Interfaces:**
- Produces: `jobify.db.models.MatchFeedback` (columns: `id`, `applicant_id`, `job_id`, `rating: str`, `created_at`, `updated_at`, `deleted_at`) and `jobify.db.models.MatchFeedbackRating` (`StrEnum`: `UP = "up"`, `DOWN = "down"`). Table name `match_feedback`. Later tasks import both from `jobify.db.models`.

- [ ] **Step 1: Start the feature branch**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
scripts/new-feature.sh match-feedback
```
Expected: on branch `feat/match-feedback` (or the script's naming), clean tree, based on latest `origin/main`.

- [ ] **Step 2: Add the enum + model to `core/src/jobify/db/models.py`**

Insert directly after the `SavedJob` class (its `__table_args__` block ends around line 770). Follow `SavedJob`'s shape exactly:

```python
class MatchFeedbackRating(StrEnum):
    """Applicant verdict on a surfaced match. Stored as varchar+CHECK (the
    consent-scope / desired_role precedent — adding a value is a Python edit,
    not a PG-enum migration)."""

    UP = "up"
    DOWN = "down"


class MatchFeedback(Base):
    """Applicant thumbs up/down on a surfaced match — see the 2026-07-19
    match-feedback design doc.

    Keyed on (applicant_id, job_id) — the same stable identity ``matches``
    uses — NOT match_id, so a rating survives match-row rescore UPSERTs.
    One live row per pair (partial unique); re-rating UPDATEs the row;
    clearing soft-deletes it (a re-rate after clear inserts a fresh row,
    like saved_jobs). ``rating='down'`` excludes the job from that
    applicant's /v1/feed.
    """

    __tablename__ = "match_feedback"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobify.applicants.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobify.jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        CheckConstraint(
            "rating IN ('up', 'down')",
            name="ck_match_feedback_rating",
        ),
        Index(
            "ix_match_feedback_applicant_job_live",
            "applicant_id",
            "job_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_match_feedback_rating_created_at",
            "rating",
            text("created_at DESC"),
            postgresql_where="deleted_at IS NULL",
        ),
        {"schema": "jobify"},
    )
```

All names used (`CheckConstraint`, `Index`, `String`, `text`, `UUID`, `ForeignKey`, `StrEnum`) are already imported at the top of `models.py` — add nothing to the imports.

- [ ] **Step 3: Write migration `core/src/jobify/db/migrations/versions/0025_match_feedback.py`**

```python
"""match_feedback: applicant thumbs up/down on surfaced matches

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-19

Adds jobify.match_feedback — one live row per (applicant_id, job_id), rating
varchar+CHECK ('up'/'down') per the consent-scope/desired_role precedent (no
native PG enum). 'down' rows exclude the job from that applicant's feed.
Partial-unique on the pair; (rating, created_at DESC) partial index serves the
admin Match QA list + summary. See docs/superpowers/specs/
2026-07-19-match-feedback-design.md.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_feedback",
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
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.String(8), nullable=False),
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
        sa.CheckConstraint("rating IN ('up', 'down')", name="ck_match_feedback_rating"),
        schema="jobify",
    )
    op.create_index(
        "ix_match_feedback_applicant_job_live",
        "match_feedback",
        ["applicant_id", "job_id"],
        unique=True,
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_match_feedback_rating_created_at",
        "match_feedback",
        ["rating", sa.text("created_at DESC")],
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_match_feedback_rating_created_at",
        table_name="match_feedback",
        schema="jobify",
    )
    op.drop_index(
        "ix_match_feedback_applicant_job_live",
        table_name="match_feedback",
        schema="jobify",
    )
    op.drop_table("match_feedback", schema="jobify")
```

- [ ] **Step 4: Migrate the local dev DB (and exercise downgrade)**

```bash
cd core
uv run alembic upgrade head
uv run alembic downgrade 0024
uv run alembic upgrade head
cd ..
```
Expected: all three succeed; `psql jobify -c "\d jobify.match_feedback"` shows the table + both partial indexes + the CHECK.

- [ ] **Step 5: Run the unit suite — the soft-delete invariant test must auto-cover the new model**

```bash
uv run pytest -v -m "not integration and not eval" tests/unit/test_soft_delete_invariant.py
uv run ruff check core/src api/src worker/src tests && uv run mypy
```
Expected: PASS (the invariant test discovers `MatchFeedback` via `Base` and finds `deleted_at`). ruff/mypy clean.

- [ ] **Step 6: Commit**

```bash
git add core/src/jobify/db/models.py core/src/jobify/db/migrations/versions/0025_match_feedback.py
git commit -m "feat(core): match_feedback table — applicant thumbs on surfaced matches

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: DSR wiring — export + delete + contract pins

**Files:**
- Modify: `tests/unit/dsr/test_dsr_coverage.py` (`EXPECTED_PII_TABLES`, near line 41)
- Modify: `api/src/jobify_api/dsr/__init__.py` (UserExport field ~line 69, gather block ~lines 234-290, constructor kwargs ~line 389)
- Modify: `api/src/jobify_api/dsr/deleter.py` (hard-delete in the applicant branch ~line 172, zero-count in the no-applicant branch ~line 235)
- Modify: whichever export-shape pin tests fail by name (`tests/integration/test_dsr_export.py` top-level-fields pin; `tests/unit/dsr/test_builder_signature.py` if present)

**Interfaces:**
- Consumes: `MatchFeedback` from Task 1.
- Produces: DSR export envelope gains top-level `match_feedback: list[dict]`; `delete_user_data` counts gain `"match_feedback"`. `EXPECTED_PII_TABLES` includes `"match_feedback"`.

- [ ] **Step 1 (TDD): Add `"match_feedback"` to `EXPECTED_PII_TABLES` in `tests/unit/dsr/test_dsr_coverage.py` and run the test**

In the `EXPECTED_PII_TABLES` frozenset (alongside `"saved_jobs"`), add `"match_feedback"`.

```bash
uv run pytest -v tests/unit/dsr/test_dsr_coverage.py
```
Expected: **FAIL twice** — `missing from export={'match_feedback'}` and `missing from deleter={'match_feedback'}` (the coverage test derives coverage from ORM classes imported into each module).

- [ ] **Step 2: Wire the export in `api/src/jobify_api/dsr/__init__.py`**

Three edits, following the `saved_jobs` pattern exactly:

1. Import `MatchFeedback` in the existing `from jobify.db.models import (...)` block.
2. Add the field to the `UserExport` Pydantic model next to `saved_jobs` (~line 69):

```python
    match_feedback: list[dict[str, Any]] = []
```

3. In `build_user_export`, inside the `if applicant is not None:` gather block, next to the `saved_jobs` query (~line 277) — export convention includes ALL rows, **no `deleted_at` filter**:

```python
        match_feedback = [
            _row_to_dict(r)
            for r in (
                await session.execute(
                    select(MatchFeedback).where(MatchFeedback.applicant_id == applicant.id)
                )
            )
            .scalars()
            .all()
        ]
```

Initialize `match_feedback: list[dict[str, Any]] = []` beside the other pre-declarations (~line 234) and pass `match_feedback=match_feedback` in the `UserExport(...)` constructor call (~line 389).

- [ ] **Step 3: Wire the deleter in `api/src/jobify_api/dsr/deleter.py`**

Import `MatchFeedback` in the models import block. In the applicant branch, next to the `SavedJob` hard-delete (~line 172):

```python
        r = await session.execute(
            delete(MatchFeedback).where(MatchFeedback.applicant_id == applicant_id)
        )
        counts["match_feedback"] = r.rowcount or 0
```

In the `else` (no applicant row) branch beside `counts["saved_jobs"] = 0` (~line 235): `counts["match_feedback"] = 0`.

- [ ] **Step 4: Run the coverage pin — now green — then fix any export-shape pins that fail by name**

```bash
uv run pytest -v tests/unit/dsr/
uv run pytest -v -m integration tests/integration/test_dsr_export.py tests/integration/test_dsr_delete.py
```
Expected: `test_dsr_coverage.py` PASSES. If `test_dsr_export.py`'s top-level-fields pin or `test_builder_signature.py` fail, they fail **naming the missing `match_feedback` key** — add it to their expected sets. No other failures.

- [ ] **Step 5: Full unit suite + gates**

```bash
uv run pytest -v -m "not integration and not eval" && uv run ruff check core/src api/src worker/src tests && uv run mypy
```
Expected: PASS/clean.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/dsr/ api/src/jobify_api/dsr/ tests/integration/test_dsr_export.py
git commit -m "feat(api): DSR export+delete cover match_feedback (PII contract pin)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: PUT/DELETE `/v1/jobs/{job_id}/match-feedback` routes

**Files:**
- Create: `api/src/jobify_api/routes/match_feedback.py`
- Modify: `api/src/jobify_api/app_factory.py` (add `match_feedback` to the `from jobify_api.routes import (...)` list ~line 24 and `app.include_router(match_feedback.router)` after the `saved_jobs` line ~107)
- Create: `tests/integration/test_match_feedback.py`
- Modify: `tests/unit/openapi_snapshot.json` (regenerated)

**Interfaces:**
- Consumes: `MatchFeedback`, `MatchFeedbackRating` (Task 1); `current_user`, `require_applicant`, `get_session` (existing).
- Produces: `PUT /v1/jobs/{job_id}/match-feedback` body `{"rating": "up"|"down"}` → 200 `MatchFeedbackRead {id, job_id, rating, created_at, updated_at}`; `DELETE /v1/jobs/{job_id}/match-feedback` → 204 (no-op if absent). 404 `match_not_found` when the applicant has no live **surfaced** match on a live job. Flutter (Task 6) and tests consume these exact shapes.

- [ ] **Step 1 (TDD): Write `tests/integration/test_match_feedback.py`**

Reuse the helper style from `tests/integration/test_feed.py` (`_make_applicant`, `_make_job_and_employer`, `_make_match`, `_token_headers` — copy those helpers in; they are module-local there, not shared fixtures):

```python
"""Integration tests for PUT/DELETE /v1/jobs/{job_id}/match-feedback."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Employer,
    Job,
    JobStatus,
    Match,
    MatchFeedback,
    User,
    UserRole,
)
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32

# ... copy _make_applicant / _make_job_and_employer / _make_match /
# _token_headers verbatim from tests/integration/test_feed.py ...


async def _setup(session: AsyncSession) -> tuple[User, Applicant, Job]:
    user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job, _ = await _make_job_and_employer(session)
    await _make_match(
        session, applicant_id=applicant.id, job_id=job.id, total_score=0.8, surfaced=True
    )
    await session.commit()
    return user, applicant, job


async def test_put_creates_rating(async_client: AsyncClient, session: AsyncSession) -> None:
    user, _, job = await _setup(session)
    r = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback",
        json={"rating": "down"},
        headers=_token_headers(user),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rating"] == "down"
    assert body["job_id"] == str(job.id)


async def test_put_rerate_updates_same_row(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, job = await _setup(session)
    h = _token_headers(user)
    r1 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "down"}, headers=h
    )
    r2 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "up"}, headers=h
    )
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]  # same live row, rating flipped
    rows = (
        (
            await session.execute(
                select(MatchFeedback).where(MatchFeedback.applicant_id == applicant.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1 and rows[0].rating == "up"


async def test_delete_soft_deletes_and_reput_creates_fresh_row(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, job = await _setup(session)
    h = _token_headers(user)
    r1 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "down"}, headers=h
    )
    rd = await async_client.delete(f"/v1/jobs/{job.id}/match-feedback", headers=h)
    assert rd.status_code == 204
    r2 = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback", json={"rating": "down"}, headers=h
    )
    assert r2.status_code == 200
    assert r2.json()["id"] != r1.json()["id"]  # fresh row after soft-delete
    rows = (
        (
            await session.execute(
                select(MatchFeedback).where(MatchFeedback.applicant_id == applicant.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert sum(1 for x in rows if x.deleted_at is None) == 1


async def test_delete_absent_is_204_noop(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _, job = await _setup(session)
    r = await async_client.delete(
        f"/v1/jobs/{job.id}/match-feedback", headers=_token_headers(user)
    )
    assert r.status_code == 204


async def test_put_404_when_match_not_surfaced(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job, _ = await _make_job_and_employer(session)
    await _make_match(
        session, applicant_id=applicant.id, job_id=job.id, total_score=0.3, surfaced=False
    )
    await session.commit()
    r = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback",
        json={"rating": "up"},
        headers=_token_headers(user),
    )
    assert r.status_code == 404


async def test_put_404_when_no_match_at_all(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _ = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    r = await async_client.put(
        f"/v1/jobs/{uuid.uuid4()}/match-feedback",
        json={"rating": "up"},
        headers=_token_headers(user),
    )
    assert r.status_code == 404


async def test_put_rejects_bad_rating(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _, job = await _setup(session)
    r = await async_client.put(
        f"/v1/jobs/{job.id}/match-feedback",
        json={"rating": "meh"},
        headers=_token_headers(user),
    )
    assert r.status_code == 422


async def test_requires_auth(async_client: AsyncClient) -> None:
    r = await async_client.put(
        f"/v1/jobs/{uuid.uuid4()}/match-feedback", json={"rating": "up"}
    )
    assert r.status_code == 401
```

(Verify the shared fixture is named `async_client` in `tests/integration/conftest.py`; if the feed tests use `client`, match them.)

- [ ] **Step 2: Run — expect 404-from-router failures**

```bash
uv run pytest -v -m integration tests/integration/test_match_feedback.py
```
Expected: FAIL — routes don't exist yet (FastAPI returns 404/405 for every call).

- [ ] **Step 3: Implement `api/src/jobify_api/routes/match_feedback.py`**

```python
"""Match feedback — applicant thumbs up/down on a surfaced match.

PUT    /v1/jobs/{job_id}/match-feedback  {"rating": "up"|"down"} → 200 stored row.
DELETE /v1/jobs/{job_id}/match-feedback  → 204 (soft-delete; no-op if absent).

A rating requires a live, SURFACED match on a live job — uniform 404 otherwise
(never leaks job existence). rating='down' excludes the job from /v1/feed
(see routes/feed.py). Keyed on (applicant_id, job_id): re-rate UPDATEs the
live row; re-rate after DELETE inserts a fresh row (saved_jobs precedent).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Job, Match, MatchFeedback, User
from jobify_api.auth.dependencies import current_user
from jobify_api.auth.dependencies import require_applicant as _require_applicant
from jobify_api.dependencies import get_session

_log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["match_feedback"])


class MatchFeedbackWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Literal["up", "down"]


class MatchFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    rating: Literal["up", "down"]
    created_at: datetime
    updated_at: datetime


async def _load_surfaced_match(
    session: AsyncSession, *, applicant_id: uuid.UUID, job_id: uuid.UUID
) -> Match | None:
    """The applicant's live surfaced match on a live job — or None (→ 404)."""
    return (
        await session.execute(
            select(Match)
            .join(Job, Job.id == Match.job_id)
            .where(
                Match.applicant_id == applicant_id,
                Match.job_id == job_id,
                Match.deleted_at.is_(None),
                Match.surfaced_at.is_not(None),
                Job.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


@router.put(
    "/jobs/{job_id}/match-feedback",
    status_code=status.HTTP_200_OK,
    response_model=MatchFeedbackRead,
)
async def put_match_feedback(
    job_id: uuid.UUID,
    body: MatchFeedbackWrite,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MatchFeedbackRead:
    """Rate the current applicant's surfaced match for this job (idempotent upsert).

    Error ladder: 401 (auth) → 403 (role) → 404 (no live surfaced match).
    """
    applicant = await _require_applicant(user, session)

    match = await _load_surfaced_match(session, applicant_id=applicant.id, job_id=job_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="match_not_found")

    existing = (
        await session.execute(
            select(MatchFeedback).where(
                MatchFeedback.applicant_id == applicant.id,
                MatchFeedback.job_id == job_id,
                MatchFeedback.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.rating = body.rating
        await session.commit()
        await session.refresh(existing)
        row = existing
    else:
        row = MatchFeedback(applicant_id=applicant.id, job_id=job_id, rating=body.rating)
        session.add(row)
        await session.commit()
        await session.refresh(row)

    _log.info(
        "match_feedback.rated",
        job_id=str(job_id),
        rating=body.rating,
    )
    return MatchFeedbackRead.model_validate(row)


@router.delete(
    "/jobs/{job_id}/match-feedback",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_match_feedback(
    job_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Clear the rating (soft-delete). 204 whether or not a live row existed —
    the UI calls this optimistically (Undo). Error ladder: 401 → 403 only."""
    applicant = await _require_applicant(user, session)

    existing = (
        await session.execute(
            select(MatchFeedback).where(
                MatchFeedback.applicant_id == applicant.id,
                MatchFeedback.job_id == job_id,
                MatchFeedback.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.execute(
            update(MatchFeedback)
            .where(MatchFeedback.id == existing.id)
            .values(deleted_at=func.now(), updated_at=func.now())
        )
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Register the router in `api/src/jobify_api/app_factory.py`**

Add `match_feedback` to the `from jobify_api.routes import (...)` tuple (alphabetical slot) and, after `app.include_router(saved_jobs.router)`:

```python
    app.include_router(match_feedback.router)
```

- [ ] **Step 5: Run the integration tests — green**

```bash
uv run pytest -v -m integration tests/integration/test_match_feedback.py
```
Expected: all PASS.

- [ ] **Step 6: Regenerate the OpenAPI snapshot + full unit gates**

```bash
JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py
uv run pytest -v -m "not integration and not eval"
uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests && uv run mypy
```
Expected: snapshot diff shows exactly the two new paths + two new schemas; everything green.

- [ ] **Step 7: Commit**

```bash
git add api/src/jobify_api/routes/match_feedback.py api/src/jobify_api/app_factory.py tests/integration/test_match_feedback.py tests/unit/openapi_snapshot.json
git commit -m "feat(api): PUT/DELETE /v1/jobs/{id}/match-feedback

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Feed exclusion + `my_feedback` on feed and job detail

**Files:**
- Modify: `api/src/jobify_api/routes/schemas.py` (`MatchRead`, ~line 19)
- Modify: `api/src/jobify_api/routes/feed.py` (query ~lines 84-127)
- Modify: `api/src/jobify_api/routes/jobs/applicant.py` (detail handler, match load ~line 60, ETag ~line 99, response ~line 117)
- Modify: `tests/integration/test_feed.py` + `tests/integration/test_job_detail.py` (new tests appended)
- Modify: `tests/unit/openapi_snapshot.json` (regenerated)

**Interfaces:**
- Consumes: `MatchFeedback`, `MatchFeedbackRating` (Task 1).
- Produces: `MatchRead` gains `my_feedback: Literal["up", "down"] | None = None` — appears in `/v1/feed` items (`match.my_feedback`, only `"up"` or `null` there) and `/v1/jobs/{id}` (`match.my_feedback`, any value). Feed excludes jobs whose live feedback row is `down`. Flutter (Task 6) reads `my_feedback`.

- [ ] **Step 1 (TDD): Append tests to `tests/integration/test_feed.py`**

```python
async def _make_feedback(
    session: AsyncSession,
    *,
    applicant_id: uuid.UUID,
    job_id: uuid.UUID,
    rating: str,
    soft_deleted: bool = False,
) -> MatchFeedback:
    fb = MatchFeedback(
        applicant_id=applicant_id,
        job_id=job_id,
        rating=rating,
        deleted_at=datetime.now(UTC) if soft_deleted else None,
    )
    session.add(fb)
    await session.flush()
    return fb


async def test_feed_hides_thumbs_down_job(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job_a, _ = await _make_job_and_employer(session, title="A", employer_name=f"E{uuid.uuid4()}")
    job_b, _ = await _make_job_and_employer(session, title="B", employer_name=f"E{uuid.uuid4()}")
    await _make_match(session, applicant_id=applicant.id, job_id=job_a.id, total_score=0.9)
    await _make_match(session, applicant_id=applicant.id, job_id=job_b.id, total_score=0.8)
    await _make_feedback(session, applicant_id=applicant.id, job_id=job_a.id, rating="down")
    await session.commit()

    r = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert r.status_code == 200
    titles = [it["job"]["title"] for it in r.json()["items"]]
    assert titles == ["B"]


async def test_feed_keeps_job_when_down_feedback_is_soft_deleted(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    """Outer-join degrade path: a CLEARED thumbs-down must not hide the job."""
    user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job, _ = await _make_job_and_employer(session, employer_name=f"E{uuid.uuid4()}")
    await _make_match(session, applicant_id=applicant.id, job_id=job.id, total_score=0.9)
    await _make_feedback(
        session, applicant_id=applicant.id, job_id=job.id, rating="down", soft_deleted=True
    )
    await session.commit()

    r = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["match"]["my_feedback"] is None


async def test_feed_surfaces_my_feedback_up(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    job, _ = await _make_job_and_employer(session, employer_name=f"E{uuid.uuid4()}")
    await _make_match(session, applicant_id=applicant.id, job_id=job.id, total_score=0.9)
    await _make_feedback(session, applicant_id=applicant.id, job_id=job.id, rating="up")
    await session.commit()

    r = await async_client.get("/v1/feed", headers=_token_headers(user))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["match"]["my_feedback"] == "up"
```

Add `MatchFeedback` to the test module's models import and `datetime`/`UTC` if not present.

Append to `tests/integration/test_job_detail.py` (mirror its local setup helpers — same style as feed's):

```python
async def test_job_detail_surfaces_my_feedback_down(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    # ...create user/applicant, open job, surfaced match with the module's helpers...
    fb = MatchFeedback(applicant_id=applicant.id, job_id=job.id, rating="down")
    session.add(fb)
    await session.commit()

    r = await async_client.get(f"/v1/jobs/{job.id}", headers=_token_headers(user))
    assert r.status_code == 200
    assert r.json()["match"]["my_feedback"] == "down"
```

- [ ] **Step 2: Run — expect failures**

```bash
uv run pytest -v -m integration tests/integration/test_feed.py tests/integration/test_job_detail.py
```
Expected: new tests FAIL (`my_feedback` key absent / down job still present); pre-existing tests PASS.

- [ ] **Step 3: Add the field to `MatchRead` in `api/src/jobify_api/routes/schemas.py`**

Add `Literal` to the module's `typing` import if absent, then inside `MatchRead`, after `explanation`:

```python
    # The CURRENT applicant's rating on this match; None = unrated. Populated
    # by /v1/feed (only "up"/None survive there — "down" is excluded) and
    # /v1/jobs/{id} (any value). Absent from any recruiter/admin reuse.
    my_feedback: Literal["up", "down"] | None = None
```

- [ ] **Step 4: Modify the feed query in `api/src/jobify_api/routes/feed.py`**

Imports: add `and_`, `or_` to the `sqlalchemy` import; add `MatchFeedback`, `MatchFeedbackRating` to the models import. Replace the `stmt = (...)` block:

```python
    # Query: match JOIN job JOIN employer; surfaced + live + open. One outer
    # join to the live feedback row does double duty: rating='down' EXCLUDES
    # the job; rating='up' is surfaced as match.my_feedback. The deleted_at
    # and key predicates MUST stay in the ON clause — in WHERE they would
    # turn the outer join inner and a soft-deleted (cleared) rating would
    # silently drop the row.
    stmt = (
        select(Match, Job, Employer, MatchFeedback.rating)
        .join(Job, Job.id == Match.job_id)
        .join(Employer, Employer.id == Job.employer_id)
        .outerjoin(
            MatchFeedback,
            and_(
                MatchFeedback.applicant_id == Match.applicant_id,
                MatchFeedback.job_id == Match.job_id,
                MatchFeedback.deleted_at.is_(None),
            ),
        )
        .where(
            Match.applicant_id == applicant.id,
            Match.deleted_at.is_(None),
            Match.surfaced_at.is_not(None),
            Job.deleted_at.is_(None),
            Job.status == JobStatus.OPEN,
            Employer.deleted_at.is_(None),
            or_(
                MatchFeedback.id.is_(None),
                MatchFeedback.rating != MatchFeedbackRating.DOWN.value,
            ),
        )
        .order_by(Match.total_score.desc(), Match.id.desc())
        .limit(limit + 1)  # peek-one
    )
```

Then update the row unpacking + item construction (the loop at ~line 114):

```python
    for match, job, employer, my_rating in rows:
        match_read = MatchRead.model_validate(match).model_copy(
            update={"my_feedback": my_rating}
        )
        items.append(
            FeedItemRead(
                match=match_read,
                job=JobRead.from_job_and_employer(job, employer),
                employer=EmployerRead(
                    id=employer.id,
                    name=employer.name,
                    verified=employer.verified_at is not None,
                ),
            )
        )
```

The `next_cursor` block reads `rows[-1][0]` — unchanged (the tuple grew but index 0 is still the Match).

- [ ] **Step 5: Modify the job detail handler in `api/src/jobify_api/routes/jobs/applicant.py`**

Add `MatchFeedback` to the models import. After the `match = (...)` load (~line 68), add:

```python
    my_feedback_row = None
    if match is not None:
        my_feedback_row = (
            await session.execute(
                select(MatchFeedback).where(
                    MatchFeedback.applicant_id == applicant.id,
                    MatchFeedback.job_id == job_id,
                    MatchFeedback.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
```

In the ETag block, after the `if match is not None:` append (a rating change must not 304):

```python
    if my_feedback_row is not None:
        etag_parts.append(my_feedback_row.updated_at)
```

Replace the `match=` kwarg in the `JobDetailResponse(...)` construction:

```python
        match=(
            MatchRead.model_validate(match).model_copy(
                update={
                    "my_feedback": my_feedback_row.rating
                    if my_feedback_row is not None
                    else None
                }
            )
            if match is not None
            else None
        ),
```

- [ ] **Step 6: Run tests — green — then snapshot + gates**

```bash
uv run pytest -v -m integration tests/integration/test_feed.py tests/integration/test_job_detail.py tests/integration/test_match_feedback.py
JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py
uv run pytest -v -m "not integration and not eval"
uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests && uv run mypy
```
Expected: all green; snapshot diff = `my_feedback` added to the `MatchRead` component only.

- [ ] **Step 7: Commit**

```bash
git add api/src/jobify_api/routes/schemas.py api/src/jobify_api/routes/feed.py api/src/jobify_api/routes/jobs/applicant.py tests/integration/test_feed.py tests/integration/test_job_detail.py tests/unit/openapi_snapshot.json
git commit -m "feat(api): feed hides thumbs-down jobs; my_feedback on feed + job detail

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Admin Match QA endpoints — list + summary

**Files:**
- Create: `api/src/jobify_api/routes/admin/match_feedback.py`
- Modify: `api/src/jobify_api/routes/admin/__init__.py` (import + `router.include_router(match_feedback.router)`)
- Create: `tests/integration/test_admin_match_feedback.py`
- Modify: `tests/unit/openapi_snapshot.json` (regenerated)

**Interfaces:**
- Consumes: `MatchFeedback`, `MatchFeedbackRating`, `Match`, `Job`, `Employer`, `Applicant`; `_require_admin`; `decode_admin_cursor`/`encode_admin_cursor` from `routes/admin/_common.py`.
- Produces: `GET /v1/admin/match-feedback?rating=&cursor=&limit=` → `{items: AdminMatchFeedbackRead[], next_cursor}`; `GET /v1/admin/match-feedback/summary` → `{all_time: {up, down, share}, last_30d: {up, down, share}}` (`share` null when up+down == 0). Console (Task 9) consumes both verbatim.

- [ ] **Step 1 (TDD): Write `tests/integration/test_admin_match_feedback.py`**

Model the admin-auth setup on `tests/integration/test_admin_audit_logs.py` (admin user created directly + `mint_access_token`), and the data helpers on `test_feed.py`:

```python
"""Integration tests for the admin Match QA endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import MatchFeedback, User, UserRole
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32

# ... copy _make_applicant / _make_job_and_employer / _make_match /
# _token_headers from tests/integration/test_feed.py ...


async def _make_admin(session: AsyncSession) -> User:
    admin = User(email=f"admin-{uuid.uuid4()}@example.com", role=UserRole.ADMIN)
    session.add(admin)
    await session.flush()
    return admin


async def _seed_ratings(session: AsyncSession, *, up: int, down: int) -> None:
    for i in range(up + down):
        user, applicant = await _make_applicant(
            session, email=f"{uuid.uuid4()}@example.com"
        )
        job, _ = await _make_job_and_employer(
            session, title=f"J{i}", employer_name=f"E{uuid.uuid4()}"
        )
        await _make_match(
            session, applicant_id=applicant.id, job_id=job.id, total_score=0.8
        )
        session.add(
            MatchFeedback(
                applicant_id=applicant.id,
                job_id=job.id,
                rating="up" if i < up else "down",
            )
        )
    await session.flush()


async def test_admin_required(async_client: AsyncClient, session: AsyncSession) -> None:
    user, _ = await _make_applicant(session, email=f"{uuid.uuid4()}@example.com")
    await session.commit()
    r = await async_client.get(
        "/v1/admin/match-feedback", headers=_token_headers(user)
    )
    assert r.status_code == 403


async def test_list_returns_joined_rows_and_filter(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _make_admin(session)
    await _seed_ratings(session, up=2, down=1)
    await session.commit()
    h = _token_headers(admin)

    r = await async_client.get("/v1/admin/match-feedback", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    row = body["items"][0]
    for key in (
        "id", "rating", "created_at", "job_id", "job_title", "employer_name",
        "applicant_id", "applicant_name", "total_score", "explanation",
    ):
        assert key in row

    r_down = await async_client.get("/v1/admin/match-feedback?rating=down", headers=h)
    assert [it["rating"] for it in r_down.json()["items"]] == ["down"]


async def test_list_paginates(async_client: AsyncClient, session: AsyncSession) -> None:
    admin = await _make_admin(session)
    await _seed_ratings(session, up=3, down=0)
    await session.commit()
    h = _token_headers(admin)

    r1 = await async_client.get("/v1/admin/match-feedback?limit=2", headers=h)
    assert len(r1.json()["items"]) == 2
    cursor = r1.json()["next_cursor"]
    assert cursor is not None
    r2 = await async_client.get(
        f"/v1/admin/match-feedback?limit=2&cursor={cursor}", headers=h
    )
    assert len(r2.json()["items"]) == 1
    assert r2.json()["next_cursor"] is None


async def test_summary_counts_and_share(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _make_admin(session)
    await _seed_ratings(session, up=3, down=1)
    await session.commit()

    r = await async_client.get(
        "/v1/admin/match-feedback/summary", headers=_token_headers(admin)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["all_time"] == {"up": 3, "down": 1, "share": 0.75}
    # Everything just seeded is inside the 30-day window too.
    assert body["last_30d"] == {"up": 3, "down": 1, "share": 0.75}


async def test_summary_zero_denominator_share_is_null(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _make_admin(session)
    await session.commit()
    r = await async_client.get(
        "/v1/admin/match-feedback/summary", headers=_token_headers(admin)
    )
    assert r.status_code == 200
    assert r.json()["all_time"]["share"] is None
```

- [ ] **Step 2: Run — expect route-missing failures**

```bash
uv run pytest -v -m integration tests/integration/test_admin_match_feedback.py
```
Expected: FAIL (404s).

- [ ] **Step 3: Implement `api/src/jobify_api/routes/admin/match_feedback.py`**

```python
"""Admin Match QA — the relevance metric + the rated-matches list.

GET /v1/admin/match-feedback          — keyset-paginated rated matches
                                        (?rating=up|down filter).
GET /v1/admin/match-feedback/summary  — up-share all-time + rolling 30d;
                                        this is the BRD "match relevance"
                                        number (share = up / (up + down)).

Gated by _require_admin AFTER current_user (401 → 403 ladder), like every
admin route. Match join is OUTER (deleted_at in the ON clause) so a rating
whose match row was since soft-deleted still lists, with null score.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    Employer,
    Job,
    Match,
    MatchFeedback,
    MatchFeedbackRating,
    User,
)
from jobify_api.auth.dependencies import _require_admin, current_user
from jobify_api.dependencies import get_session
from jobify_api.routes.admin._common import decode_admin_cursor, encode_admin_cursor

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class AdminMatchFeedbackRead(BaseModel):
    id: uuid.UUID
    rating: Literal["up", "down"]
    created_at: datetime
    updated_at: datetime
    job_id: uuid.UUID
    job_title: str
    employer_name: str
    applicant_id: uuid.UUID
    applicant_name: str | None  # null once DSR-tombstoned
    total_score: float | None  # null if the match row was soft-deleted since
    explanation: dict[str, str] | None


class AdminMatchFeedbackListResponse(BaseModel):
    items: list[AdminMatchFeedbackRead]
    next_cursor: str | None


class FeedbackWindowStats(BaseModel):
    up: int
    down: int
    share: float | None  # up / (up + down); null when nothing rated


class AdminMatchFeedbackSummary(BaseModel):
    all_time: FeedbackWindowStats
    last_30d: FeedbackWindowStats


@router.get("/match-feedback", response_model=AdminMatchFeedbackListResponse)
async def list_match_feedback(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    rating: Literal["up", "down"] | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AdminMatchFeedbackListResponse:
    await _require_admin(user)

    stmt = (
        select(MatchFeedback, Job, Employer, Applicant, Match)
        .join(Job, Job.id == MatchFeedback.job_id)
        .join(Employer, Employer.id == Job.employer_id)
        .join(Applicant, Applicant.id == MatchFeedback.applicant_id)
        .outerjoin(
            Match,
            and_(
                Match.applicant_id == MatchFeedback.applicant_id,
                Match.job_id == MatchFeedback.job_id,
                Match.deleted_at.is_(None),
            ),
        )
        .where(MatchFeedback.deleted_at.is_(None))
    )
    if rating is not None:
        stmt = stmt.where(MatchFeedback.rating == rating)
    if cursor is not None:
        cursor_created, cursor_id = decode_admin_cursor(cursor)
        stmt = stmt.where(
            (MatchFeedback.created_at < cursor_created)
            | (
                (MatchFeedback.created_at == cursor_created)
                & (MatchFeedback.id < cursor_id)
            )
        )
    stmt = stmt.order_by(
        MatchFeedback.created_at.desc(), MatchFeedback.id.desc()
    ).limit(limit + 1)

    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [
        AdminMatchFeedbackRead(
            id=fb.id,
            rating=fb.rating,  # type: ignore[arg-type]  # DB CHECK pins the vocab
            created_at=fb.created_at,
            updated_at=fb.updated_at,
            job_id=job.id,
            job_title=job.title,
            employer_name=employer.name,
            applicant_id=applicant.id,
            applicant_name=applicant.full_name,
            total_score=float(match.total_score) if match is not None else None,
            explanation=match.explanation if match is not None else None,
        )
        for fb, job, employer, applicant, match in rows
    ]
    next_cursor = (
        encode_admin_cursor(rows[-1][0].created_at, rows[-1][0].id) if has_more else None
    )
    return AdminMatchFeedbackListResponse(items=items, next_cursor=next_cursor)


def _stats(up: int, down: int) -> FeedbackWindowStats:
    total = up + down
    return FeedbackWindowStats(
        up=up, down=down, share=round(up / total, 4) if total else None
    )


@router.get("/match-feedback/summary", response_model=AdminMatchFeedbackSummary)
async def match_feedback_summary(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AdminMatchFeedbackSummary:
    await _require_admin(user)

    cutoff = datetime.now(UTC) - timedelta(days=30)
    up_v = MatchFeedbackRating.UP.value
    down_v = MatchFeedbackRating.DOWN.value
    row = (
        await session.execute(
            select(
                func.count(case((MatchFeedback.rating == up_v, 1))),
                func.count(case((MatchFeedback.rating == down_v, 1))),
                func.count(
                    case(
                        (
                            and_(
                                MatchFeedback.rating == up_v,
                                MatchFeedback.created_at >= cutoff,
                            ),
                            1,
                        )
                    )
                ),
                func.count(
                    case(
                        (
                            and_(
                                MatchFeedback.rating == down_v,
                                MatchFeedback.created_at >= cutoff,
                            ),
                            1,
                        )
                    )
                ),
            ).where(MatchFeedback.deleted_at.is_(None))
        )
    ).one()
    return AdminMatchFeedbackSummary(
        all_time=_stats(row[0], row[1]),
        last_30d=_stats(row[2], row[3]),
    )
```

- [ ] **Step 4: Register in `api/src/jobify_api/routes/admin/__init__.py`**

```python
from jobify_api.routes.admin import analytics, employers, match_feedback, users
...
router.include_router(match_feedback.router)
```
(Also mention the new module in the package docstring list.)

- [ ] **Step 5: Run tests — green — then snapshot + gates**

```bash
uv run pytest -v -m integration tests/integration/test_admin_match_feedback.py
JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py
uv run pytest -v -m "not integration and not eval"
uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests && uv run mypy
```
Expected: all green; snapshot adds the two admin paths + 4 schemas.

- [ ] **Step 6: Commit**

```bash
git add api/src/jobify_api/routes/admin/ tests/integration/test_admin_match_feedback.py tests/unit/openapi_snapshot.json
git commit -m "feat(api): admin Match QA — rated-matches list + relevance summary

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Flutter data layer — enum, DTO fields, API + repository methods

**Files (all under `app/`):**
- Create: `lib/data/feed/match_feedback_rating.dart`
- Create: `lib/data/feed/match_feedback_dto.dart` (+ generated `.g.dart`)
- Modify: `lib/data/feed/feed_dto.dart` (`MatchSummaryDto` gains `myFeedback`)
- Modify: `lib/data/jobs/jobs_api.dart`, `lib/data/jobs/jobs_repository.dart`, `lib/data/jobs/jobs_repository_impl.dart`
- Test: `test/unit/data/feed/match_feedback_test.dart`

Check first whether `JobDetailDto`'s `match` field (in `lib/data/jobs/jobs_dto.dart`) is `MatchSummaryDto` — it imports the feed DTO. If it has its own match DTO instead, apply the same `myFeedback` addition there.

**Interfaces:**
- Consumes: wire shapes from Tasks 3-4 (`my_feedback`, `MatchFeedbackRead`).
- Produces: `MatchFeedbackRating {up, down, unknown}` + `MatchFeedbackRatingWire.wireValue` (throws on `unknown`); `MatchSummaryDto.myFeedback: MatchFeedbackRating?`; `JobsRepository.rateMatch(String jobId, MatchFeedbackRating rating) → Future<MatchFeedbackDto>` and `JobsRepository.clearMatchFeedback(String jobId) → Future<void>`. Tasks 7-8 consume these.

- [ ] **Step 1 (TDD): Write `test/unit/data/feed/match_feedback_test.dart`**

Mirror the round-trip style of `test/unit/data/preferences/` (literal-JSON fixtures):

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_rating.dart';

void main() {
  group('MatchFeedbackRating wire map', () {
    test('round-trips every real value', () {
      expect(MatchFeedbackRating.up.wireValue, 'up');
      expect(MatchFeedbackRating.down.wireValue, 'down');
    });

    test('unknown never serializes', () {
      expect(() => MatchFeedbackRating.unknown.wireValue, throwsStateError);
    });
  });

  group('MatchSummaryDto.my_feedback', () {
    Map<String, dynamic> matchJson(Object? myFeedback) => {
          'id': 'm1',
          'total_score': 0.8,
          'components': {'location': 1.0},
          'explanation': null,
          'surfaced_at': '2026-07-19T00:00:00Z',
          'my_feedback': myFeedback,
        };

    test('null stays null', () {
      expect(MatchSummaryDto.fromJson(matchJson(null)).myFeedback, isNull);
    });

    test('up parses', () {
      expect(
        MatchSummaryDto.fromJson(matchJson('up')).myFeedback,
        MatchFeedbackRating.up,
      );
    });

    test('unrecognised server value degrades to unknown, not a throw', () {
      expect(
        MatchSummaryDto.fromJson(matchJson('meh')).myFeedback,
        MatchFeedbackRating.unknown,
      );
    });
  });

  group('MatchFeedbackDto', () {
    test('parses the PUT response shape', () {
      final dto = MatchFeedbackDto.fromJson({
        'id': 'f1',
        'job_id': 'j1',
        'rating': 'down',
        'created_at': '2026-07-19T00:00:00Z',
        'updated_at': '2026-07-19T00:00:00Z',
      });
      expect(dto.rating, MatchFeedbackRating.down);
      expect(dto.jobId, 'j1');
    });
  });
}
```

Run: `cd app && flutter test test/unit/data/feed/match_feedback_test.dart` — Expected: FAIL (files don't exist).

- [ ] **Step 2: Create `lib/data/feed/match_feedback_rating.dart`**

```dart
import 'package:json_annotation/json_annotation.dart';

/// Applicant verdict on a surfaced match.
///
/// Mirrors backend `MatchFeedbackRating` in `core/src/jobify/db/models.py`
/// (wire: "up" / "down"); pinned by test/unit/data/feed/match_feedback_test.dart.
/// `unknown` is the unrecognised-server-value sentinel — it must NEVER
/// serialize (wireValue throws), same contract as DesiredRole.
enum MatchFeedbackRating {
  @JsonValue('up')
  up,
  @JsonValue('down')
  down,
  unknown,
}

extension MatchFeedbackRatingWire on MatchFeedbackRating {
  String get wireValue => switch (this) {
        MatchFeedbackRating.up => 'up',
        MatchFeedbackRating.down => 'down',
        MatchFeedbackRating.unknown =>
          throw StateError('MatchFeedbackRating.unknown is not a wire value'),
      };
}
```

- [ ] **Step 3: Create `lib/data/feed/match_feedback_dto.dart`**

```dart
import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:json_annotation/json_annotation.dart';

part 'match_feedback_dto.g.dart';

/// Mirrors backend `MatchFeedbackRead` in
/// `api/src/jobify_api/routes/match_feedback.py`.
@JsonSerializable()
class MatchFeedbackDto {
  const MatchFeedbackDto({
    required this.id,
    required this.jobId,
    required this.rating,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MatchFeedbackDto.fromJson(Map<String, dynamic> json) =>
      _$MatchFeedbackDtoFromJson(json);

  final String id;
  final String jobId;
  @JsonKey(unknownEnumValue: MatchFeedbackRating.unknown)
  final MatchFeedbackRating rating;
  final DateTime createdAt;
  final DateTime updatedAt;

  Map<String, dynamic> toJson() => _$MatchFeedbackDtoToJson(this);
}
```

- [ ] **Step 4: Add `myFeedback` to `MatchSummaryDto` in `lib/data/feed/feed_dto.dart`**

Import `match_feedback_rating.dart`; add to the constructor `this.myFeedback,` and to the fields:

```dart
  /// The current applicant's rating; null = unrated. Only `up`/null appear in
  /// the feed (down is server-excluded); job detail may carry `down`.
  @JsonKey(unknownEnumValue: MatchFeedbackRating.unknown)
  final MatchFeedbackRating? myFeedback;
```

If `JobDetailDto.match` is not `MatchSummaryDto`, make the identical addition to its match DTO.

- [ ] **Step 5: Add API + repository methods**

`lib/data/jobs/jobs_api.dart` (import the two new files):

```dart
  Future<MatchFeedbackDto> rateMatch(String jobId, String rating) async {
    final res = await _dio.put<Map<String, dynamic>>(
      '/v1/jobs/$jobId/match-feedback',
      data: {'rating': rating},
    );
    return MatchFeedbackDto.fromJson(res.data!);
  }

  Future<void> clearMatchFeedback(String jobId) async {
    await _dio.delete<dynamic>('/v1/jobs/$jobId/match-feedback');
  }
```

`lib/data/jobs/jobs_repository.dart` — extend the interface:

```dart
  Future<MatchFeedbackDto> rateMatch(String jobId, MatchFeedbackRating rating);
  Future<void> clearMatchFeedback(String jobId);
```

`lib/data/jobs/jobs_repository_impl.dart` — implement following the existing `save`/`unsave` error-mapping style (wrap in the same try/catch the neighbors use):

```dart
  @override
  Future<MatchFeedbackDto> rateMatch(
    String jobId,
    MatchFeedbackRating rating,
  ) async {
    try {
      return await _api.rateMatch(jobId, rating.wireValue);
    } on DioException catch (e) {
      throw mapDioException(e); // ← use the SAME helper/pattern save() uses
    }
  }

  @override
  Future<void> clearMatchFeedback(String jobId) async {
    try {
      await _api.clearMatchFeedback(jobId);
    } on DioException catch (e) {
      throw mapDioException(e); // ← same pattern as unsave()
    }
  }
```
(Open the impl first and copy its exact catch/mapping idiom — do not invent a new one.)

- [ ] **Step 6: Regenerate codegen + run tests**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
flutter test test/unit/data/feed/match_feedback_test.dart
flutter test test/unit/data/feed/
dart format --set-exit-if-changed lib test && flutter analyze
```
Expected: all PASS. If an existing feed DTO fixture test fails because `my_feedback` is absent from its fixture JSON — that's fine only if the field is nullable-optional; json_serializable treats a missing key as null. It should NOT fail; investigate if it does.

- [ ] **Step 7: Commit**

```bash
git add app/lib/data app/test/unit/data/feed
git commit -m "feat(app): match-feedback data layer — rating enum, DTOs, repo methods

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Flutter feed — thumbs on cards, optimistic hide + Undo

**Files (all under `app/`):**
- Modify: `lib/presentation/feed/feed_controller.dart` (mutation methods)
- Modify: `lib/presentation/feed/feed_item_card.dart` (thumb controls)
- Modify: `lib/presentation/feed/feed_screen.dart` (wire callbacks + snackbar)
- Test: `test/widget/feed_screen_test.dart` (extend)

**Interfaces:**
- Consumes: `JobsRepository.rateMatch`/`clearMatchFeedback` (Task 6); `PagedState.copyWith` (freezed, existing).
- Produces: `FeedController.rateUp(String jobId)`, `rateDown(String jobId)` (optimistic removal, restores state and rethrows on error), `undoDown(String jobId)` (clear + refresh). `FeedItemCard` gains optional `myFeedback`, `onThumbUp`, `onThumbDown` params (all nullable — other card call sites unaffected).

- [ ] **Step 1 (TDD): Extend `test/widget/feed_screen_test.dart`**

Follow the file's existing fake-repository + pump pattern (fakes in `test/helpers/fake_repositories.dart`; remember `ProviderContainer(retry: (_, __) => null)` / the file's existing override style). Add:

```dart
  testWidgets('thumb-down removes the card and shows Undo snackbar',
      (tester) async {
    // Arrange: fake feed repo returns 2 items (job ids j1, j2); fake jobs repo
    // records rateMatch calls. Pump FeedScreen per this file's harness.
    // Act:
    await tester.tap(find.byTooltip('Not interested').first);
    await tester.pumpAndSettle();
    // Assert: only one FeedItemCard remains; snackbar visible with Undo.
    expect(find.byType(FeedItemCard), findsOneWidget);
    expect(find.text('Hidden from your feed'), findsOneWidget);
    expect(find.text('Undo'), findsOneWidget);
    expect(fakeJobsRepo.ratedDown, contains('j1'));
  });

  testWidgets('thumb-down restores the card when the API call fails',
      (tester) async {
    // Arrange: fake jobs repo throws on rateMatch.
    await tester.tap(find.byTooltip('Not interested').first);
    await tester.pumpAndSettle();
    expect(find.byType(FeedItemCard), findsNWidgets(2)); // rolled back
  });

  testWidgets('thumb-up fills the icon and keeps the card', (tester) async {
    await tester.tap(find.byTooltip('Good match').first);
    await tester.pumpAndSettle();
    expect(find.byType(FeedItemCard), findsNWidgets(2));
    expect(find.byIcon(Icons.thumb_up), findsOneWidget); // filled variant
  });
```

Extend the fake jobs repository in `test/helpers/fake_repositories.dart` with `rateMatch`/`clearMatchFeedback` (record calls; configurable throw), since the interface grew in Task 6 — the fakes MUST be updated in the same commit or every jobs-repo test breaks.

Run: `flutter test test/widget/feed_screen_test.dart` — Expected: FAIL (no thumbs yet).

- [ ] **Step 2: Add mutation methods to `FeedController`** (`lib/presentation/feed/feed_controller.dart`)

```dart
  /// Optimistic thumbs-down: remove the card immediately, roll back on error.
  Future<void> rateDown(String jobId) async {
    final prev = state;
    final s = state.valueOrNull;
    if (s != null) {
      state = AsyncData(
        s.copyWith(
          items: [
            for (final it in s.items)
              if (it.job.id != jobId) it,
          ],
        ),
      );
    }
    try {
      await ref
          .read(jobsRepositoryProvider)
          .rateMatch(jobId, MatchFeedbackRating.down);
    } catch (_) {
      state = prev; // restore — the card comes back
      rethrow;
    }
  }

  /// Thumbs-up: persist, then patch the item in place (card stays).
  Future<void> rateUp(String jobId) async {
    await ref
        .read(jobsRepositoryProvider)
        .rateMatch(jobId, MatchFeedbackRating.up);
    final s = state.valueOrNull;
    if (s == null) return;
    state = AsyncData(
      s.copyWith(
        items: [
          for (final it in s.items)
            if (it.job.id != jobId)
              it
            else
              FeedItemDto(
                match: MatchSummaryDto(
                  id: it.match.id,
                  totalScore: it.match.totalScore,
                  scoreComponents: it.match.scoreComponents,
                  explanation: it.match.explanation,
                  surfacedAt: it.match.surfacedAt,
                  myFeedback: MatchFeedbackRating.up,
                ),
                job: it.job,
                employer: it.employer,
              ),
        ],
      ),
    );
  }

  /// Undo a thumbs-down: clear the rating server-side, refetch page 1.
  Future<void> undoDown(String jobId) async {
    await ref.read(jobsRepositoryProvider).clearMatchFeedback(jobId);
    await refresh();
  }
```

Imports: `jobs_repository_impl.dart` (for `jobsRepositoryProvider`), `match_feedback_rating.dart`. Verify `MatchSummaryDto`'s constructor parameter list against Task 6's final shape before writing the rebuild.

- [ ] **Step 3: Add thumb controls to `FeedItemCard`** (`lib/presentation/feed/feed_item_card.dart`)

New optional params: `this.myFeedback, this.onThumbUp, this.onThumbDown` (`final MatchFeedbackRating? myFeedback; final VoidCallback? onThumbUp; final VoidCallback? onThumbDown;`). Replace the bottom meta `Text` with a `Row` — meta text expanded left, thumbs right (rendered only when both callbacks are non-null and the job is open):

```dart
              Row(
                children: [
                  Expanded(
                    child: Text(
                      meta,
                      style: JobifyTypography.mono(
                        fontSize: 12,
                        fontWeight: FontWeight.w400,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                  if (!isClosed && onThumbUp != null && onThumbDown != null) ...[
                    IconButton(
                      tooltip: 'Good match',
                      visualDensity: VisualDensity.compact,
                      icon: Icon(
                        myFeedback == MatchFeedbackRating.up
                            ? Icons.thumb_up
                            : Icons.thumb_up_outlined,
                        size: 18,
                      ),
                      onPressed: onThumbUp,
                    ),
                    IconButton(
                      tooltip: 'Not interested',
                      visualDensity: VisualDensity.compact,
                      icon: const Icon(Icons.thumb_down_outlined, size: 18),
                      onPressed: onThumbDown,
                    ),
                  ],
                ],
              ),
```

- [ ] **Step 4: Wire callbacks + snackbar in `feed_screen.dart`** (itemBuilder, ~line 171)

```dart
                    return Arrive(
                      index: i,
                      child: FeedItemCard(
                        job: item.job,
                        employer: item.employer,
                        onTap: () =>
                            context.go('${Routes.feed}/jobs/${item.job.id}'),
                        match: item.match,
                        explanation: item.match.explanation,
                        myFeedback: item.match.myFeedback,
                        onThumbUp: () => _rateUp(item.job.id),
                        onThumbDown: () => _rateDown(item.job.id),
                      ),
                    );
```

Add to the screen's `State` class:

```dart
  Future<void> _rateUp(String jobId) async {
    try {
      await ref.read(feedControllerProvider.notifier).rateUp(jobId);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't save your rating")),
      );
    }
  }

  Future<void> _rateDown(String jobId) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(feedControllerProvider.notifier).rateDown(jobId);
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(content: Text("Couldn't save your rating")),
      );
      return;
    }
    messenger.showSnackBar(
      SnackBar(
        content: const Text('Hidden from your feed'),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () =>
              ref.read(feedControllerProvider.notifier).undoDown(jobId),
        ),
      ),
    );
  }
```

(Capture the messenger BEFORE the await — the card may unmount context mid-flight.)

- [ ] **Step 5: Run tests + gates**

```bash
cd app
flutter test test/widget/feed_screen_test.dart && flutter test
dart format --set-exit-if-changed lib test && flutter analyze
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/lib/presentation/feed app/test
git commit -m "feat(app): feed card thumbs — optimistic hide with Undo

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Flutter job detail — rating row beside the explanation

**Files (all under `app/`):**
- Create: `lib/presentation/job_detail/match_feedback_controller.dart` (+ `.g.dart`)
- Modify: `lib/presentation/job_detail/job_detail_screen.dart` (rating row under the explanation block, which starts at the `final exp = match.explanation;` section ~line 145)
- Test: `test/widget/job_detail_feedback_test.dart`

**Interfaces:**
- Consumes: Task 6 repo methods; `jobDetailControllerProvider(jobId)`, `feedControllerProvider` (existing).
- Produces: `matchFeedbackControllerProvider(jobId)` with `rate(MatchFeedbackRating)` and `clear()`; a `Was this match right for you?` row rendered whenever the detail payload has a match.

- [ ] **Step 1 (TDD): Write `test/widget/job_detail_feedback_test.dart`**

Follow the harness of the existing job-detail widget tests (fake repos, pump the screen with a `JobDetailDto` whose match has `myFeedback: null`):

```dart
  testWidgets('rating row renders and persists a thumbs-up', (tester) async {
    // pump JobDetailScreen with a match payload, myFeedback null
    expect(find.text('Was this match right for you?'), findsOneWidget);
    await tester.tap(find.byTooltip('Good match'));
    await tester.pumpAndSettle();
    expect(fakeJobsRepo.ratedUp, contains('j1'));
  });

  testWidgets('detail shows current rating state (down)', (tester) async {
    // pump with myFeedback: MatchFeedbackRating.down
    expect(find.byIcon(Icons.thumb_down), findsOneWidget); // filled
  });
```

Run: `flutter test test/widget/job_detail_feedback_test.dart` — Expected: FAIL.

- [ ] **Step 2: Create `lib/presentation/job_detail/match_feedback_controller.dart`**

Mirror `save_job_controller.dart` exactly:

```dart
import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_controller.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'match_feedback_controller.g.dart';

/// Rates / clears the match rating from job detail.
///
/// DELIBERATE exception to the "never invalidate the feed on mutation" rule
/// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
/// kept-alive feed list must refetch or it keeps showing the hidden job.
@riverpod
class MatchFeedbackController extends _$MatchFeedbackController {
  @override
  FutureOr<void> build(String jobId) {}

  Future<void> rate(MatchFeedbackRating rating) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(jobsRepositoryProvider).rateMatch(jobId, rating);
      ref
        ..invalidate(jobDetailControllerProvider(jobId))
        ..invalidate(feedControllerProvider);
    });
  }

  Future<void> clear() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(jobsRepositoryProvider).clearMatchFeedback(jobId);
      ref
        ..invalidate(jobDetailControllerProvider(jobId))
        ..invalidate(feedControllerProvider);
    });
  }
}
```

- [ ] **Step 3: Add the rating row to `job_detail_screen.dart`**

Directly after the explanation block (the section using `match.explanation` ~line 145), inside the same `if match != null` region, add a `_MatchFeedbackRow` widget instance: `_MatchFeedbackRow(jobId: job.id, current: match.myFeedback)`, and define at the bottom of the file:

```dart
class _MatchFeedbackRow extends ConsumerWidget {
  const _MatchFeedbackRow({required this.jobId, required this.current});

  final String jobId;
  final MatchFeedbackRating? current;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final pending =
        ref.watch(matchFeedbackControllerProvider(jobId)).isLoading;
    final notifier = ref.read(matchFeedbackControllerProvider(jobId).notifier);

    void toggle(MatchFeedbackRating rating) {
      if (pending) return;
      if (current == rating) {
        notifier.clear(); // tapping the active thumb clears the rating
      } else {
        notifier.rate(rating);
      }
    }

    return Padding(
      padding: const EdgeInsets.only(top: JobifySpacing.md),
      child: Row(
        children: [
          Expanded(
            child: Text(
              'Was this match right for you?',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ),
          IconButton(
            tooltip: 'Good match',
            visualDensity: VisualDensity.compact,
            icon: Icon(
              current == MatchFeedbackRating.up
                  ? Icons.thumb_up
                  : Icons.thumb_up_outlined,
              size: 20,
            ),
            onPressed: pending ? null : () => toggle(MatchFeedbackRating.up),
          ),
          IconButton(
            tooltip: 'Not interested',
            visualDensity: VisualDensity.compact,
            icon: Icon(
              current == MatchFeedbackRating.down
                  ? Icons.thumb_down
                  : Icons.thumb_down_outlined,
              size: 20,
            ),
            onPressed: pending ? null : () => toggle(MatchFeedbackRating.down),
          ),
        ],
      ),
    );
  }
}
```

Add the needed imports (`ConsumerWidget` comes with the existing riverpod import style of the file; `match_feedback_rating.dart`, `match_feedback_controller.dart`).

- [ ] **Step 4: Codegen + tests + gates**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
flutter test
dart format --set-exit-if-changed lib test && flutter analyze
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/lib/presentation/job_detail app/test
git commit -m "feat(app): job-detail match rating row

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Console — Match QA admin page

**Files (all under `frontend/`):**
- Modify: `src/sites/console/api/types.ts` (new shapes; header comment cites `api/src/jobify_api/routes/admin/match_feedback.py`)
- Modify: `src/sites/console/api/client.ts` (interface + `HttpClient` methods)
- Modify: `src/sites/console/api/demo.ts` (`DemoClient` fixtures — it `implements ConsoleClient`, so the build FAILS until it grows the two methods)
- Create: `src/sites/console/pages/admin/MatchQA.tsx`
- Modify: `src/sites/console/ConsoleRoutes.tsx` (route) and `src/sites/console/components/Shell.tsx` (`NAV` entry)

**Interfaces:**
- Consumes: Task 5 endpoints verbatim; `usePagedFetch` (`Page<T> = {items, next_cursor}`), `bits.tsx` components, `useSession`.
- Produces: `/console/admin/match-qa` page; `ConsoleClient.listMatchFeedback(rating, cursor)` + `matchFeedbackSummary()`.

- [ ] **Step 1: Add types to `src/sites/console/api/types.ts`**

```ts
// --- Match QA (admin) — mirrors api/src/jobify_api/routes/admin/match_feedback.py ---

export type MatchFeedbackRating = "up" | "down";

export interface AdminMatchFeedbackRow {
  id: string;
  rating: MatchFeedbackRating;
  created_at: string;
  updated_at: string;
  job_id: string;
  job_title: string;
  employer_name: string;
  applicant_id: string;
  applicant_name: string | null;
  total_score: number | null;
  explanation: { fit?: string; caveat?: string } | null;
}

export interface AdminMatchFeedbackPage {
  items: AdminMatchFeedbackRow[];
  next_cursor: string | null;
}

export interface MatchFeedbackWindowStats {
  up: number;
  down: number;
  /** up / (up + down); null when nothing rated yet. */
  share: number | null;
}

export interface AdminMatchFeedbackSummary {
  all_time: MatchFeedbackWindowStats;
  last_30d: MatchFeedbackWindowStats;
}
```

- [ ] **Step 2: Extend `ConsoleClient` + `HttpClient` in `src/sites/console/api/client.ts`**

Interface additions (with the type imports):

```ts
  listMatchFeedback(
    rating: MatchFeedbackRating | "all",
    cursor?: string,
  ): Promise<AdminMatchFeedbackPage>;
  matchFeedbackSummary(): Promise<AdminMatchFeedbackSummary>;
```

`HttpClient` impls:

```ts
  listMatchFeedback(
    rating: MatchFeedbackRating | "all",
    cursor?: string,
  ): Promise<AdminMatchFeedbackPage> {
    const params = new URLSearchParams();
    if (rating !== "all") params.set("rating", rating);
    if (cursor) params.set("cursor", cursor);
    const qs = params.toString();
    return this.request("GET", `/v1/admin/match-feedback${qs ? `?${qs}` : ""}`);
  }

  matchFeedbackSummary(): Promise<AdminMatchFeedbackSummary> {
    return this.request("GET", "/v1/admin/match-feedback/summary");
  }
```

- [ ] **Step 3: Give `DemoClient` (`src/sites/console/api/demo.ts`) matching fixtures**

Follow the file's existing fixture style — a dozen plausible rows (mixed ratings, one `applicant_name: null`, one `total_score: null`), rating-filtered + cursor-sliced in memory; summary computed from the fixture rows so the numbers agree with the list.

- [ ] **Step 4: Create `src/sites/console/pages/admin/MatchQA.tsx`**

Model structure/classNames on `Verification.tsx` (chips row, table, `usePagedFetch`, `EmptyState`/`ErrorNotice` from `bits.tsx`):

```tsx
import { useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import type {
  AdminMatchFeedbackRow,
  AdminMatchFeedbackSummary,
  MatchFeedbackRating,
} from "../../api/types";
import { EmptyState, ErrorNotice, ShortId } from "../../components/bits";
import { usePagedFetch } from "../../paging/usePagedFetch";
import { useSession } from "../../session";

const FILTERS: Array<MatchFeedbackRating | "all"> = ["all", "up", "down"];

/** n below which the relevance % is statistically meaningless. */
const BELIEVABLE_N = 500;

function pct(share: number | null): string {
  return share == null ? "—" : `${(share * 100).toFixed(1)}%`;
}

export function MatchQA() {
  const { client } = useSession();
  const [filter, setFilter] = useState<MatchFeedbackRating | "all">("all");
  const [summary, setSummary] = useState<AdminMatchFeedbackSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    client
      .matchFeedbackSummary()
      .then((s) => alive && setSummary(s))
      .catch((e) => alive && setSummaryError(errorMessage(e)));
    return () => {
      alive = false;
    };
  }, [client]);

  const { rows, nextCursor, busy, error, loadMore } =
    usePagedFetch<AdminMatchFeedbackRow>(
      (cursor) => client.listMatchFeedback(filter, cursor),
      filter,
    );

  const totalRated = summary ? summary.all_time.up + summary.all_time.down : 0;

  return (
    <div className="content">
      <div className="headline">
        <h1>
          MATCH <span className="ghost">QA</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            Applicant verdicts on surfaced matches — the relevance metric and
            the receipts behind it.
          </span>
        </div>
      </div>

      {summaryError && <ErrorNotice message={summaryError} />}
      {summary && (
        <div className="stat-row">
          <div className="stat">
            <div className="k">relevance · all time</div>
            <div className="v">{pct(summary.all_time.share)}</div>
            <div className="k">
              {summary.all_time.up}▲ / {summary.all_time.down}▼
            </div>
          </div>
          <div className="stat">
            <div className="k">relevance · last 30d</div>
            <div className="v">{pct(summary.last_30d.share)}</div>
            <div className="k">
              {summary.last_30d.up}▲ / {summary.last_30d.down}▼
            </div>
          </div>
          {totalRated < BELIEVABLE_N && (
            <div className="stat">
              <div className="k">confidence</div>
              <div className="v">n={totalRated}</div>
              <div className="k">below n={BELIEVABLE_N} — not yet believable</div>
            </div>
          )}
        </div>
      )}

      <div className="chip-row">
        {FILTERS.map((f) => (
          <button
            key={f}
            className={f === filter ? "chip acc" : "chip"}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "All" : f === "up" ? "▲ Up" : "▼ Down"}
          </button>
        ))}
      </div>

      {error && <ErrorNotice message={error} />}
      {!busy && rows.length === 0 && !error && (
        <EmptyState message="No ratings yet — the metric starts when applicants start voting." />
      )}

      {rows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Verdict</th>
              <th>Job</th>
              <th>Employer</th>
              <th>Applicant</th>
              <th>Score</th>
              <th>Why it was surfaced</th>
              <th>Rated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>
                  <span className={r.rating === "up" ? "chip ok" : "chip danger"}>
                    {r.rating === "up" ? "▲ up" : "▼ down"}
                  </span>
                </td>
                <td>{r.job_title}</td>
                <td>{r.employer_name}</td>
                <td>
                  {r.applicant_name ?? <ShortId id={r.applicant_id} />}
                </td>
                <td>{r.total_score == null ? "—" : r.total_score.toFixed(2)}</td>
                <td className="wrap">
                  {r.explanation?.fit ?? "—"}
                  {r.explanation?.caveat ? ` · caveat: ${r.explanation.caveat}` : ""}
                </td>
                <td>{r.created_at.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {nextCursor && (
        <button className="btn" disabled={busy} onClick={loadMore}>
          {busy ? "Loading…" : "Load more"}
        </button>
      )}
    </div>
  );
}
```

Adapt classNames/`bits` component props to what `Verification.tsx`/`Analytics.tsx` actually use (open them side-by-side; the house classes like `stat-row`/`chip`/`data-table` must match the real CSS in `styles/console.css` — reuse existing classes, add no new CSS unless a class is genuinely missing). Dates shown through `shared/format.ts` if the other pages do so — mirror them.

- [ ] **Step 5: Route + nav**

`ConsoleRoutes.tsx`: `import { MatchQA } from "./pages/admin/MatchQA";` and inside `<Route element={<RequireAdmin />}>`:

```tsx
          <Route path={`${CONSOLE_BASE}/admin/match-qa`} element={<MatchQA />} />
```

`Shell.tsx` `NAV`:

```ts
  { to: `${CONSOLE_BASE}/admin/match-qa`, idx: "04", label: "Match QA" },
```

- [ ] **Step 6: Build gate**

```bash
cd frontend && npm run build
```
Expected: `tsc -b && vite build` green (a missing DemoClient method fails here — that's the type system doing its job).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/sites/console
git commit -m "feat(console): Match QA page — relevance metric + rated-matches list

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Docs, full verification sweep, PR

**Files:**
- Modify: `core/CLAUDE.md` (new invariant section), `api/CLAUDE.md` (feed + new-route bullets)

**Interfaces:** none — verification + documentation only.

- [ ] **Step 1: Add the invariant docs**

`core/CLAUDE.md`, new section after "Applicant preferences" (keep it tight):

```markdown
## Match feedback (`match_feedback`) — spec `2026-07-19-match-feedback-design.md`

- **Keyed on `(applicant_id, job_id)`, NOT match_id** — ratings must survive match-row rescore UPSERTs. One live row per pair (partial-unique `ix_match_feedback_applicant_job_live`); re-rate UPDATEs, clear soft-deletes, re-rate-after-clear inserts fresh (saved_jobs precedent).
- **`rating` is varchar+CHECK (`'up'/'down'`), `MatchFeedbackRating` StrEnum at the boundary** — same no-PG-enum precedent as consent scopes/desired_role.
- **PII: DSR-wired** — exported AND hard-deleted; pinned in `EXPECTED_PII_TABLES` (`tests/unit/dsr/test_dsr_coverage.py`).
- `rating='down'` excludes the job from that applicant's `/v1/feed` (see `api/CLAUDE.md`).
```

`api/CLAUDE.md`, append to the "Feed + job detail" section:

```markdown
- **Feed excludes thumbs-down jobs via ONE outer join** to the live `match_feedback` row — key + `deleted_at IS NULL` predicates live in the JOIN's **ON clause** (WHERE would turn it inner: a cleared rating would silently drop the row). The same join surfaces `MatchRead.my_feedback` (only `"up"`/null can appear in feed; job detail may carry `"down"` — rated jobs stay reachable via saved/applications). Job detail's ETag includes the feedback row's `updated_at` so a rating change isn't served a 304.
- **`PUT/DELETE /v1/jobs/{id}/match-feedback`** (`routes/match_feedback.py`): rating requires a live SURFACED match on a live job — uniform 404 otherwise; DELETE is 204 always (optimistic Undo). **Admin Match QA** (`routes/admin/match_feedback.py`): list uses the `_common` admin cursor; `summary.share = up/(up+down)`, null on zero.
```

- [ ] **Step 2: Full verification sweep — the exact CI commands**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
uv run ruff check core/src api/src worker/src tests
uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration
cd app && dart format --set-exit-if-changed lib test && flutter analyze && flutter test && cd ..
cd frontend && npm run build && cd ..
```
Expected: everything green. Also confirm the snapshot is stable: `uv run pytest tests/unit/test_openapi_contract.py` passes WITHOUT the update env var.

- [ ] **Step 3: Commit docs, push, open the PR**

```bash
git add core/CLAUDE.md api/CLAUDE.md
git commit -m "docs: match-feedback invariants in core/api CLAUDE.md

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git push -u origin HEAD
gh pr create --title "Match feedback capture + admin Match QA (roadmap slice 1)" --body "$(cat <<'EOF'
Implements docs/superpowers/specs/2026-07-19-match-feedback-design.md — roadmap slice 1 (starts the match-relevance data clock).

- `match_feedback` table (applicant×job, varchar+CHECK rating, soft-delete, partial-unique) + DSR export/delete wiring + contract pins
- `PUT/DELETE /v1/jobs/{id}/match-feedback`; feed excludes thumbs-down via ON-clause outer join; `my_feedback` on feed + job detail
- Admin `GET /v1/admin/match-feedback` (+`/summary` — the BRD relevance metric)
- Flutter: thumbs on feed cards (optimistic hide + Undo) and a job-detail rating row
- Console: Match QA page (relevance % + filterable rated list)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review notes (resolved during authoring)

- **Spec coverage:** storage decision → T1; DSR → T2; PUT/DELETE + 404 semantics → T3; feed exclusion + both degrade paths + `my_feedback` → T4; admin list/summary + n<500 caption → T5/T9; Flutter placements + optimistic/Undo + DTO sentinel rules → T6-T8; OpenAPI regen → T3/4/5; error-handling section → T3 (uniform 404, idempotent upsert), T4 (degrade tests), T7 (rollback + snackbar). No gaps found.
- **Type consistency:** `MatchFeedbackRating.DOWN.value` used against the `str`-typed column everywhere; `my_feedback` is `Literal["up","down"] | None` in Python, `MatchFeedbackRating?` in Dart, `MatchFeedbackRating` union in TS; repo method names `rateMatch`/`clearMatchFeedback` are identical across Tasks 6-8.
- **Known adaptation points (deliberate, not placeholders):** test helper copies come verbatim from named existing files; `mapDioException` stands for "the impl's existing catch idiom — copy it"; console classNames must be reconciled against `console.css` via the two named sibling pages.
