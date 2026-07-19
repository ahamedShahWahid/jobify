# Application Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recruiters move candidates through a hiring pipeline (shortlist → interview → offer → hired/rejected) and applicants see a notified, visible progress timeline — closing the post-apply black hole.

**Architecture:** `applications.stage` column (varchar+CHECK) for cheap current-state reads + `application_stage_events` history table for the applicant timeline. Recruiter `PATCH …/stage` runs guards → structlog → audit → event → dual-channel notification in ONE transaction. Applicant payloads gain `stage`; a new timeline endpoint serves the event list. Three client surfaces: Flutter applicant (chip + timeline + inbox copy), Flutter recruiter (stage menu), web employers (dropdown in Applicants.tsx).

**Tech Stack:** SQLAlchemy 2 async + Alembic (hand-written), FastAPI + Pydantic v2, existing notifications outbox (EMAIL + IN_APP rows, `sweep_notifications` dispatch, SES `_render`), Flutter + Riverpod 4 codegen, React/Vite employers surface.

**Spec:** `docs/superpowers/specs/2026-07-19-application-stages-design.md`

## Global Constraints

- Backend commands from repo root with `uv run …`; alembic from `core/` with `uv run --env-file=../.env alembic …`.
- CI verbatim gates: `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -m integration`. Flutter (from `app/`): `dart format --set-exit-if-changed lib test` · `flutter analyze` · `flutter test`. Frontend (from `frontend/`): `npm run build`.
- Stage vocabulary EXACTLY: `applied, shortlisted, interview, offer, hired, rejected`. Stage is varchar(16)+CHECK — NEVER a native PG enum (`ApplicationStatus`'s native enum is legacy; do not copy it). `ApplicationStage` StrEnum at the boundary.
- Recruiter-settable targets EXACTLY: `shortlisted, interview, offer, hired, rejected` (never `applied` — only re-apply resets to it). Free movement among the 5; same-stage PATCH = 200 no-op (no event, no notification, no audit).
- Error ladder order: 401 → 403 → 404 (uniform, never leaks existence) → 409 `application_withdrawn` → 422.
- Every real transition in ONE transaction, in this order: structlog (`recruiter.application-stage-changed`) → `audit_log(action="application.stage_changed", actor=recruiter_user)` → stage event row → Notification rows (kind `application_stage_changed`, BOTH `NotificationChannel.EMAIL` and `NotificationChannel.IN_APP`, mirroring `application_received`).
- Rejection copy (verbatim): body line "The employer moved forward with other candidates for {job_title} at {employer_name}." — neutral, no "rejected" in applicant-facing copy; the applicant-facing stage label is "Not selected".
- Soft delete conventions everywhere; hand-written migration 0026 (revises 0025) with upgrade AND downgrade.
- Any OpenAPI-visible change: `JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py`, review + commit the diff, update wire pins + hand-written clients in lockstep.
- Flutter wire enums carry an `unknown` sentinel that NEVER serializes; snake_case wire mapping is automatic via `app/build.yaml`.
- Commit per task with trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Branch, `ApplicationStage` + stage column + `ApplicationStageEvent`, migration 0026

**Files:**
- Modify: `core/src/jobify/db/models.py` (enum above `Application` ~line 670; column + CHECK inside `Application`; new model after `Application` ~line 730)
- Create: `core/src/jobify/db/migrations/versions/0026_application_stages.py`

**Interfaces:**
- Produces: `jobify.db.models.ApplicationStage` (StrEnum: APPLIED/SHORTLISTED/INTERVIEW/OFFER/HIRED/REJECTED, values lowercase); `Application.stage: str` (default `"applied"`); `jobify.db.models.ApplicationStageEvent` (columns: `id, application_id, from_stage, to_stage, actor_user_id, created_at, updated_at, deleted_at`), table `application_stage_events`. Every later task imports these from `jobify.db.models`.

- [ ] **Step 1: Start the feature branch**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
scripts/new-feature.sh application-stages
```
Expected: on branch `application-stages` off latest `origin/main`, clean tree.

- [ ] **Step 2: Add the enum + column + model to `core/src/jobify/db/models.py`**

Directly BEFORE `class Application(Base):` (next to `ApplicationStatus`):

```python
class ApplicationStage(StrEnum):
    """Recruiter-owned hiring pipeline stage — see the 2026-07-19
    application-stages design doc. ``status`` stays the applicant-owned
    lifecycle (applied/withdrawn); ``stage`` is the recruiter pipeline.
    varchar+CHECK in DB (house rule — no new native PG enums)."""

    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"


_STAGE_VOCAB_SQL = "('applied','shortlisted','interview','offer','hired','rejected')"
```

Inside `Application`, after the `source` column:

```python
    stage: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ApplicationStage.APPLIED.value,
        server_default=ApplicationStage.APPLIED.value,
    )
```

Add to `Application.__table_args__` (inside the existing tuple, before the two `Index` entries):

```python
        CheckConstraint(
            f"stage IN {_STAGE_VOCAB_SQL}",
            name="ck_applications_stage",
        ),
```

Directly AFTER the `Application` class:

```python
class ApplicationStageEvent(Base):
    """One row per stage transition — powers the applicant's timeline.

    Append-only in practice (soft-delete columns exist per house convention;
    live reads still filter ``deleted_at IS NULL``). ``actor_user_id`` is
    ``SET NULL`` on user deletion (survives DSR like audit rows) and is NEVER
    exposed to the applicant. Re-apply after withdraw writes a
    ``(<old> -> applied)`` event with the applicant as actor.
    """

    __tablename__ = "application_stage_events"

    id: Mapped[UuidPK]
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobify.applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_stage: Mapped[str] = mapped_column(String(16), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobify.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        CheckConstraint(
            f"from_stage IN {_STAGE_VOCAB_SQL}",
            name="ck_application_stage_events_from",
        ),
        CheckConstraint(
            f"to_stage IN {_STAGE_VOCAB_SQL}",
            name="ck_application_stage_events_to",
        ),
        Index(
            "ix_application_stage_events_app_created",
            "application_id",
            text("created_at DESC"),
            postgresql_where="deleted_at IS NULL",
        ),
        {"schema": "jobify"},
    )
```

All names (`CheckConstraint`, `Index`, `String`, `text`, `UUID`, `ForeignKey`) are already imported in `models.py` — add nothing to imports.

- [ ] **Step 3: Write `core/src/jobify/db/migrations/versions/0026_application_stages.py`**

```python
"""application stages: pipeline column on applications + stage-events history

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-19

Adds applications.stage (varchar+CHECK, default 'applied' — existing rows are
backfilled by the server default) and jobify.application_stage_events (the
applicant-timeline history; actor_user_id SET NULL survives DSR). Vocabulary
'applied','shortlisted','interview','offer','hired','rejected'. See
docs/superpowers/specs/2026-07-19-application-stages-design.md.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

_VOCAB = "('applied','shortlisted','interview','offer','hired','rejected')"


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "stage",
            sa.String(16),
            nullable=False,
            server_default="applied",
        ),
        schema="jobify",
    )
    op.create_check_constraint(
        "ck_applications_stage",
        "applications",
        f"stage IN {_VOCAB}",
        schema="jobify",
    )

    op.create_table(
        "application_stage_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_stage", sa.String(16), nullable=False),
        sa.Column("to_stage", sa.String(16), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.CheckConstraint(
            f"from_stage IN {_VOCAB}", name="ck_application_stage_events_from"
        ),
        sa.CheckConstraint(
            f"to_stage IN {_VOCAB}", name="ck_application_stage_events_to"
        ),
        schema="jobify",
    )
    op.create_index(
        "ix_application_stage_events_app_created",
        "application_stage_events",
        ["application_id", sa.text("created_at DESC")],
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_stage_events_app_created",
        table_name="application_stage_events",
        schema="jobify",
    )
    op.drop_table("application_stage_events", schema="jobify")
    op.drop_constraint(
        "ck_applications_stage", "applications", schema="jobify", type_="check"
    )
    op.drop_column("applications", "stage", schema="jobify")
```

- [ ] **Step 4: Migrate dev DB, exercise downgrade, re-upgrade**

```bash
cd core
uv run --env-file=../.env alembic upgrade head
uv run --env-file=../.env alembic downgrade 0025
uv run --env-file=../.env alembic upgrade head
cd ..
psql jobify -c "\d jobify.application_stage_events" | head -20
psql jobify -tAc "SELECT count(*) FROM jobify.applications WHERE stage <> 'applied'"
```
Expected: migrations clean; table + index + CHECKs present; count = 0 (backfill via default worked).

- [ ] **Step 5: Unit gates (soft-delete invariant auto-covers the new model)**

```bash
uv run pytest -v tests/unit/test_soft_delete_invariant.py
uv run pytest -q -m "not integration and not eval"
uv run ruff check core/src api/src worker/src tests && uv run mypy
```
Expected: all green. (If the DSR coverage test fails here, STOP — it shouldn't until Task 2 touches the pins.)

- [ ] **Step 6: Commit**

```bash
git add core/src/jobify/db/models.py core/src/jobify/db/migrations/versions/0026_application_stages.py
git commit -m "feat(core): application stage column + stage-events history table

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: DSR wiring — stage events are export-only

**Files:**
- Modify: `tests/unit/dsr/test_dsr_coverage.py` (`_EXPORT_ONLY_TABLES`, ~line 65)
- Modify: `api/src/jobify_api/dsr/__init__.py` (import, `UserExport` field, gather block, constructor kwarg)
- Modify: whichever export-shape pin fails by name (`tests/unit/dsr/test_builder_signature.py` top-level-fields pin)

**Interfaces:**
- Consumes: `ApplicationStageEvent` (Task 1).
- Produces: export envelope gains top-level `application_stage_events: list[dict]` (events for the applicant's applications, ALL rows, no `deleted_at` filter). Deleter is NOT touched — the table is kept on delete (CASCADE-safe: `applications` are kept/anonymized, `actor_user_id` nulls via FK).

- [ ] **Step 1 (TDD): Add `"application_stage_events"` to `_EXPORT_ONLY_TABLES` in `tests/unit/dsr/test_dsr_coverage.py` (alongside `"applications"`) and run**

```bash
uv run pytest -v tests/unit/dsr/test_dsr_coverage.py
```
Expected: FAIL once — the export module doesn't reference `ApplicationStageEvent` yet (the deleter check must stay green: export-only tables are excluded from it).

- [ ] **Step 2: Wire the export in `api/src/jobify_api/dsr/__init__.py`**

Add `ApplicationStageEvent` to the models import block. Add to `UserExport` next to `applications`:

```python
    application_stage_events: list[dict[str, Any]] = []
```

In `build_user_export`'s `if applicant is not None:` gather block, next to the applications query (rows joined via the applicant's applications; ALL rows, no `deleted_at` filter — export convention):

```python
        application_stage_events = [
            _row_to_dict(r)
            for r in (
                await session.execute(
                    select(ApplicationStageEvent)
                    .join(
                        Application,
                        Application.id == ApplicationStageEvent.application_id,
                    )
                    .where(Application.applicant_id == applicant.id)
                    .order_by(ApplicationStageEvent.created_at)
                )
            )
            .scalars()
            .all()
        ]
```

Pre-declare `application_stage_events: list[dict[str, Any]] = []` beside the other pre-declarations and pass `application_stage_events=application_stage_events` in the `UserExport(...)` constructor. (`Application` and `select` are already imported.)

- [ ] **Step 3: Run pins — fix the top-level-fields pin that fails by name**

```bash
uv run pytest -v tests/unit/dsr/
uv run pytest -v -m integration tests/integration/test_dsr_export.py tests/integration/test_dsr_delete.py
```
Expected: coverage test green; if `test_builder_signature.py`'s top-level pin fails naming `application_stage_events`, add the key to its expected set. DSR delete tests stay green untouched.

- [ ] **Step 4: Full unit gates + commit**

```bash
uv run pytest -q -m "not integration and not eval" && uv run ruff check api/src tests && uv run mypy
git add tests/unit/dsr/ api/src/jobify_api/dsr/__init__.py
git commit -m "feat(api): DSR export covers application_stage_events (export-only class)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Stage-change service + recruiter PATCH endpoint + notifications

**Files:**
- Modify: `api/src/jobify_api/applications/service.py` (new `change_application_stage` + stage-notification helper)
- Modify: `api/src/jobify_api/routes/jobs/recruiter.py` (PATCH route after the applicants list, ~line 395)
- Modify: `core/src/jobify/integrations/notifications/ses.py` (`_render` branch, ~line 82)
- Modify: `app/../..` — nothing Flutter here (Task 6+)
- Create: `tests/integration/test_application_stage.py`
- Modify: `tests/unit/openapi_snapshot.json` (regenerated)

**Interfaces:**
- Consumes: `ApplicationStage`, `ApplicationStageEvent` (Task 1); `_load_recruiter_job` (existing recruiter guard: role + employer membership + job existence, uniform 404); `audit_log(session, *, action, actor, resource_type, resource_id, context)`; `Notification`/`NotificationChannel` dual-channel pattern from `apply_to_open_job`.
- Produces: `PATCH /v1/jobs/{job_id}/applications/{application_id}/stage` body `{"stage": Literal["shortlisted","interview","offer","hired","rejected"]}` → 200 `{application_id, stage, updated_at}` (`StageChangeRead`). 404 uniform / 409 `application_withdrawn` / 422 bad stage. Notification kind `application_stage_changed`, payload `{kind, application_id, job_id, job_title, employer_name, stage}` on EMAIL + IN_APP. Service raises `StageChangeError(status_code, detail)`.

- [ ] **Step 1 (TDD): Write `tests/integration/test_application_stage.py`**

Copy the recruiter/job/application fixture helpers from `tests/integration/test_jobs_create_recruiter.py` or `test_applications_list.py` (open them; use their real `_make_*` style — recruiter user + employer + `EmployerUser` row + job + applicant + application). Then:

```python
"""Integration tests for PATCH /v1/jobs/{job_id}/applications/{id}/stage."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Application,
    ApplicationStageEvent,
    ApplicationStatus,
    AuditLog,
    Notification,
)

pytestmark = pytest.mark.integration

# ... fixture helpers copied per the note above; each returns
# (recruiter_user, employer, job, applicant_user, applicant, application) ...


async def test_stage_change_happy_path(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 200
    assert r.json()["stage"] == "shortlisted"

    events = (
        (
            await session.execute(
                select(ApplicationStageEvent).where(
                    ApplicationStageEvent.application_id == application.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert [(e.from_stage, e.to_stage) for e in events] == [("applied", "shortlisted")]
    assert events[0].actor_user_id == recruiter.id

    notifs = (
        (
            await session.execute(
                select(Notification).where(
                    Notification.kind == "application_stage_changed"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 2  # EMAIL + IN_APP
    assert {n.channel.value for n in notifs} == {"email", "in_app"}
    assert notifs[0].payload["stage"] == "shortlisted"
    assert notifs[0].payload["job_title"] == job.title

    audit = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "application.stage_changed")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1


async def test_same_stage_noop_writes_nothing(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    h = _token_headers(recruiter)
    await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "interview"},
        headers=h,
    )
    r2 = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "interview"},
        headers=h,
    )
    assert r2.status_code == 200
    events = (
        (
            await session.execute(
                select(ApplicationStageEvent).where(
                    ApplicationStageEvent.application_id == application.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1  # second call wrote no event


async def test_free_movement_including_backwards(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    h = _token_headers(recruiter)
    for stage in ("offer", "interview", "rejected", "shortlisted"):
        r = await async_client.patch(
            f"/v1/jobs/{job.id}/applications/{application.id}/stage",
            json={"stage": stage},
            headers=h,
        )
        assert r.status_code == 200, stage


async def test_applied_not_a_settable_target(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "applied"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 422


async def test_withdrawn_application_409(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, application = await _setup(session)
    application.status = ApplicationStatus.WITHDRAWN
    await session.commit()
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "application_withdrawn"


async def test_uniform_404_other_employers_application(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    recruiter, _, job, _, _, _ = await _setup(session)
    # An application under a DIFFERENT employer's job:
    _, _, other_job, _, _, other_app = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{other_app.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(recruiter),
    )
    assert r.status_code == 404


async def test_applicant_role_gets_403_or_404(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    _, _, job, applicant_user, _, application = await _setup(session)
    r = await async_client.patch(
        f"/v1/jobs/{job.id}/applications/{application.id}/stage",
        json={"stage": "shortlisted"},
        headers=_token_headers(applicant_user),
    )
    assert r.status_code in (403, 404)  # match _load_recruiter_job's real ladder
```

Run: `uv run pytest -v -m integration tests/integration/test_application_stage.py` — Expected: FAIL (405/404 route missing).

- [ ] **Step 2: Add `change_application_stage` to `api/src/jobify_api/applications/service.py`**

Follow the module's existing error style (`ApplicationError`-like exception with `status_code`/`detail` — open the file's existing exception class and mirror it):

```python
RECRUITER_SETTABLE_STAGES: frozenset[str] = frozenset(
    {"shortlisted", "interview", "offer", "hired", "rejected"}
)


class StageChangeError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _stage_notification_payload(
    *, application: Application, job: Job, employer: Employer, stage: str
) -> dict[str, str]:
    return {
        "kind": "application_stage_changed",
        "application_id": str(application.id),
        "job_id": str(job.id),
        "job_title": job.title,
        "employer_name": employer.name,
        "stage": stage,
    }


async def change_application_stage(
    session: AsyncSession,
    *,
    job: Job,
    application_id: uuid.UUID,
    actor: User,
    target_stage: str,
) -> Application:
    """Move an application to ``target_stage`` (recruiter pipeline).

    Caller has already validated recruiter membership + job ownership
    (``_load_recruiter_job``). One transaction: structlog -> audit ->
    stage event -> dual-channel notification. Same-stage = no-op.
    Raises StageChangeError(404/409).
    """
    row = (
        await session.execute(
            select(Application, Applicant, Employer)
            .join(Applicant, Applicant.id == Application.applicant_id)
            .join(Job, Job.id == Application.job_id)
            .join(Employer, Employer.id == Job.employer_id)
            .where(
                Application.id == application_id,
                Application.job_id == job.id,
                Application.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise StageChangeError(404, "application_not_found")
    application, applicant, employer = row

    if application.status == ApplicationStatus.WITHDRAWN:
        raise StageChangeError(409, "application_withdrawn")

    if application.stage == target_stage:
        return application  # no-op: no event, no notification, no audit

    from_stage = application.stage
    _log.info(
        "recruiter.application-stage-changed",
        application_id=str(application.id),
        job_id=str(job.id),
        from_stage=from_stage,
        to_stage=target_stage,
    )
    await audit_log(
        session,
        action="application.stage_changed",
        actor=actor,
        resource_type="application",
        resource_id=application.id,
        context={"from_stage": from_stage, "to_stage": target_stage},
    )
    application.stage = target_stage
    session.add(
        ApplicationStageEvent(
            application_id=application.id,
            from_stage=from_stage,
            to_stage=target_stage,
            actor_user_id=actor.id,
        )
    )
    payload = _stage_notification_payload(
        application=application, job=job, employer=employer, stage=target_stage
    )
    session.add_all(
        [
            Notification(
                user_id=applicant.user_id,
                kind="application_stage_changed",
                channel=channel,
                payload=payload,
            )
            for channel in (NotificationChannel.EMAIL, NotificationChannel.IN_APP)
        ]
    )
    await session.commit()
    await session.refresh(application)
    return application
```

Add the needed imports (`Applicant`, `ApplicationStageEvent`, `Employer`, `audit_log` from `jobify.audit`, `structlog` logger `_log = structlog.get_logger(__name__)` if the module lacks one — check first).

- [ ] **Step 3: Add the route to `api/src/jobify_api/routes/jobs/recruiter.py`** (after the applicants list endpoint)

```python
class StageChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["shortlisted", "interview", "offer", "hired", "rejected"]


class StageChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    stage: str
    updated_at: datetime


@router.patch(
    "/jobs/{job_id}/applications/{application_id}/stage",
    response_model=StageChangeRead,
)
async def change_stage(
    job_id: uuid.UUID,
    application_id: uuid.UUID,
    body: StageChangeRequest,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> StageChangeRead:
    """Move a candidate through the hiring pipeline.

    Ladder: 401 -> 403/404 (_load_recruiter_job, uniform) -> 404 (application
    not under this job) -> 409 application_withdrawn -> 422 (Literal).
    Same-stage PATCH is a 200 no-op.
    """
    job = await _load_recruiter_job(job_id, user, session)
    try:
        application = await change_application_stage(
            session,
            job=job,
            application_id=application_id,
            actor=user,
            target_stage=body.stage,
        )
    except StageChangeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return StageChangeRead(
        application_id=application.id,
        stage=application.stage,
        updated_at=application.updated_at,
    )
```

Import `change_application_stage`, `StageChangeError` from `jobify_api.applications.service`; add `Literal`/`ConfigDict` if absent.

- [ ] **Step 4: SES copy — add the `_render` branch in `core/src/jobify/integrations/notifications/ses.py`** (before the fallback return)

```python
    if kind == "application_stage_changed":
        title = str(payload.get("job_title", "the role"))
        employer = str(payload.get("employer_name", "the employer"))
        stage = str(payload.get("stage", ""))
        if stage == "rejected":
            return (
                f"Update on your application — {title}",
                f"The employer moved forward with other candidates for {title} at {employer}.",
            )
        if stage == "hired":
            return (
                f"Congratulations — {title} at {employer}",
                f"You've been hired for {title} at {employer}. The employer will be in touch with next steps.",
            )
        _STAGE_LINE = {
            "shortlisted": "You've been shortlisted",
            "interview": "You've moved to the interview stage",
            "offer": "You have an offer",
        }
        line = _STAGE_LINE.get(stage, "Your application was updated")
        return (
            f"{line} — {title}",
            f"{line} for {title} at {employer}. Open Jobify for details.",
        )
```

- [ ] **Step 5: Run tests green, snapshot, gates, commit**

```bash
uv run pytest -v -m integration tests/integration/test_application_stage.py
JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py
uv run pytest -q -m "not integration and not eval"
uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests && uv run mypy
git add api/src/jobify_api/applications/service.py api/src/jobify_api/routes/jobs/recruiter.py core/src/jobify/integrations/notifications/ses.py tests/integration/test_application_stage.py tests/unit/openapi_snapshot.json
git commit -m "feat(api): recruiter stage PATCH — pipeline transitions, audit, dual-channel notification

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
Expected snapshot delta: 1 new path + 2 new schemas only.

---

### Task 4: `stage` on applicant + recruiter payloads; re-apply resets stage

**Files:**
- Modify: `api/src/jobify_api/routes/applications_schemas.py` (`ApplicationRead`, ~line 18)
- Modify: `api/src/jobify_api/routes/schemas.py` (`JobDetailApplicationRead`)
- Modify: `api/src/jobify_api/routes/jobs/recruiter.py` (`ApplicantOfJobRow` + its construction)
- Modify: `api/src/jobify_api/applications/service.py` (`apply_to_open_job` re-apply branch, ~line 69)
- Modify: `tests/integration/test_wire_shapes.py` (three key-set pins), `tests/integration/test_apply.py` (append re-apply-reset test)
- Modify: `tests/unit/openapi_snapshot.json` (regenerated)

**Interfaces:**
- Consumes: Task 1 model, Task 3 event conventions.
- Produces: `ApplicationRead.stage: str`, `JobDetailApplicationRead.stage: str`, `ApplicantOfJobRow.stage: str` — all serialized on the wire as `stage`. Re-apply after withdraw resets `stage='applied'` and writes a `(<old> → applied)` event with the applicant as actor. Flutter (Task 6) and employers TS (Task 9) mirror these.

- [ ] **Step 1 (TDD): Pin the new key in `tests/integration/test_wire_shapes.py`**

Add `"stage"` to `_APPLICATION_READ_KEYS` (~line 91), `_JOB_DETAIL_APPLICATION_KEYS` (~line 75). Run:

```bash
uv run pytest -v -m integration tests/integration/test_wire_shapes.py
```
Expected: the applications + job-detail wire tests FAIL (missing `stage`).

Append to `tests/integration/test_apply.py` (mirror its helpers):

```python
async def test_reapply_resets_stage_and_records_event(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    # apply -> recruiter-side stage bump (write directly) -> withdraw -> re-apply
    user, applicant, job = await _setup_open_job_and_applicant(session)  # module's real helper names
    h = _token_headers(user)
    r1 = await async_client.post(f"/v1/jobs/{job.id}/apply", json={"source": "feed"}, headers=h)
    app_id = r1.json()["id"]
    await session.execute(
        update(Application).where(Application.id == uuid.UUID(app_id)).values(stage="interview")
    )
    await session.commit()
    await async_client.patch(
        f"/v1/applications/{app_id}/status", json={"status": "withdrawn"}, headers=h
    )
    r2 = await async_client.post(f"/v1/jobs/{job.id}/apply", json={"source": "feed"}, headers=h)
    assert r2.status_code == 200  # same-row re-apply
    assert r2.json()["stage"] == "applied"
    events = (
        (
            await session.execute(
                select(ApplicationStageEvent).where(
                    ApplicationStageEvent.application_id == uuid.UUID(app_id)
                )
            )
        )
        .scalars()
        .all()
    )
    assert ("interview", "applied") in [(e.from_stage, e.to_stage) for e in events]
```

(Adapt helper names/response codes to the file's real ones — open it first; the assertions are the contract.)

- [ ] **Step 2: Add the field to the three read models**

`applications_schemas.py` `ApplicationRead`, after `status`:

```python
    stage: str  # recruiter pipeline: applied|shortlisted|interview|offer|hired|rejected
```

`routes/schemas.py` `JobDetailApplicationRead`: same line after `status`.

`routes/jobs/recruiter.py` `ApplicantOfJobRow`: add `stage: str` after `status`, and in the row construction add `stage=app_row.stage,`.

- [ ] **Step 3: Re-apply reset in `apply_to_open_job`** (the existing-row branch that flips WITHDRAWN → APPLIED)

In the branch that updates the existing withdrawn row (currently sets `status=ApplicationStatus.APPLIED` + refreshed `created_at`): also capture `old_stage = existing.stage` BEFORE the update, include `stage=ApplicationStage.APPLIED.value` in the update's `.values(...)`, and when `old_stage != "applied"` add:

```python
        if old_stage != ApplicationStage.APPLIED.value:
            session.add(
                ApplicationStageEvent(
                    application_id=existing.id,
                    from_stage=old_stage,
                    to_stage=ApplicationStage.APPLIED.value,
                    actor_user_id=user_id,
                )
            )
```

(Import `ApplicationStage`, `ApplicationStageEvent`.)

- [ ] **Step 4: Run green, snapshot, gates, commit**

```bash
uv run pytest -v -m integration tests/integration/test_wire_shapes.py tests/integration/test_apply.py tests/integration/test_applications_list.py tests/integration/test_job_detail.py
JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py
uv run pytest -q -m "not integration and not eval"
uv run ruff check api/src tests && uv run ruff format --check api/src tests && uv run mypy
git add api/src/jobify_api/routes/applications_schemas.py api/src/jobify_api/routes/schemas.py api/src/jobify_api/routes/jobs/recruiter.py api/src/jobify_api/applications/service.py tests/integration/test_wire_shapes.py tests/integration/test_apply.py tests/unit/openapi_snapshot.json
git commit -m "feat(api): stage on application payloads; re-apply resets stage with event

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
Expected snapshot delta: `stage` added to the three components only.

---

### Task 5: Applicant timeline endpoint

**Files:**
- Modify: `api/src/jobify_api/routes/applications.py` (new GET after the existing routes)
- Create/extend: `tests/integration/test_application_timeline.py`
- Modify: `tests/unit/openapi_snapshot.json` (regenerated)

**Interfaces:**
- Consumes: `ApplicationStageEvent` (Task 1); `require_applicant` shared guard.
- Produces: `GET /v1/applications/{application_id}/timeline` → 200 `{"items": [{"from_stage", "to_stage", "created_at"}]}` ascending by `created_at`; owner-only, uniform 404; actor NEVER exposed. Flutter Task 6 consumes this exact shape.

- [ ] **Step 1 (TDD): Write `tests/integration/test_application_timeline.py`**

```python
"""Integration tests for GET /v1/applications/{id}/timeline."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import ApplicationStageEvent

pytestmark = pytest.mark.integration

# ... copy applicant+job+application helpers from tests/integration/test_applications_list.py ...


async def test_timeline_orders_events_and_hides_actor(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, job, application = await _setup(session)
    for pair in (("applied", "shortlisted"), ("shortlisted", "interview")):
        session.add(
            ApplicationStageEvent(
                application_id=application.id,
                from_stage=pair[0],
                to_stage=pair[1],
                actor_user_id=user.id,
            )
        )
    await session.commit()
    r = await async_client.get(
        f"/v1/applications/{application.id}/timeline", headers=_token_headers(user)
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert [(i["from_stage"], i["to_stage"]) for i in items] == [
        ("applied", "shortlisted"),
        ("shortlisted", "interview"),
    ]
    assert all(set(i.keys()) == {"from_stage", "to_stage", "created_at"} for i in items)


async def test_timeline_uniform_404_for_other_applicants_application(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _, _, _ = await _setup(session)
    _, _, _, other_application = await _setup(session)
    r = await async_client.get(
        f"/v1/applications/{other_application.id}/timeline",
        headers=_token_headers(user),
    )
    assert r.status_code == 404


async def test_timeline_unknown_id_404(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _, _, _ = await _setup(session)
    r = await async_client.get(
        f"/v1/applications/{uuid.uuid4()}/timeline", headers=_token_headers(user)
    )
    assert r.status_code == 404
```

Run — Expected: FAIL (404 from router on all).

- [ ] **Step 2: Implement in `api/src/jobify_api/routes/applications.py`**

```python
class StageEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_stage: str
    to_stage: str
    created_at: datetime


class ApplicationTimelineResponse(BaseModel):
    items: list[StageEventRead]


@router.get(
    "/applications/{application_id}/timeline",
    response_model=ApplicationTimelineResponse,
)
async def get_application_timeline(
    application_id: uuid.UUID,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ApplicationTimelineResponse:
    """The applicant's stage journey. Owner-only (token identity), uniform
    404 across unknown-id and other-owner; actor identity never exposed."""
    applicant = await _require_applicant(user, session)
    owned = (
        await session.execute(
            select(Application.id).where(
                Application.id == application_id,
                Application.applicant_id == applicant.id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if owned is None:
        raise HTTPException(status_code=404, detail="application_not_found")

    events = (
        (
            await session.execute(
                select(ApplicationStageEvent)
                .where(
                    ApplicationStageEvent.application_id == application_id,
                    ApplicationStageEvent.deleted_at.is_(None),
                )
                .order_by(ApplicationStageEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return ApplicationTimelineResponse(
        items=[StageEventRead.model_validate(e) for e in events]
    )
```

(Match the module's real import aliases — it already has `current_user`/`require_applicant`/`get_session`; add `ApplicationStageEvent` to the models import.)

- [ ] **Step 3: Green + snapshot + gates + commit**

```bash
uv run pytest -v -m integration tests/integration/test_application_timeline.py
JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py
uv run pytest -q -m "not integration and not eval"
uv run ruff check api/src tests && uv run ruff format --check api/src tests && uv run mypy
git add api/src/jobify_api/routes/applications.py tests/integration/test_application_timeline.py tests/unit/openapi_snapshot.json
git commit -m "feat(api): applicant application timeline endpoint

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Flutter data layer — stage enum, DTO fields, timeline + setStage methods

**Files (under `app/`):**
- Create: `lib/data/jobs/application_stage.dart`
- Modify: `lib/data/jobs/jobs_dto.dart` (`ApplicationDto.stage`; new `StageEventDto` + `ApplicationTimelineDto`)
- Modify: `lib/data/jobs/recruiter_job_dto.dart` (applicant row gains `stage`)
- Modify: `lib/data/jobs/applications_api.dart` + the applications repository interface/impl it serves (timeline fetch)
- Modify: `lib/data/jobs/recruiter_jobs_api.dart` + `recruiter_jobs_repository.dart` + `_impl` (`setStage`)
- Modify: `test/helpers/fake_repositories.dart` (new methods on fakes)
- Test: `test/unit/data/jobs/application_stage_test.dart`

**Interfaces:**
- Consumes: wire shapes from Tasks 3-5.
- Produces: `ApplicationStage {applied, shortlisted, interview, offer, hired, rejected, unknown}` (+ `wireValue` throwing on `unknown`); `ApplicationDto.stage: ApplicationStage`; `StageEventDto {fromStage, toStage, createdAt}`; `ApplicationsRepository.fetchTimeline(String applicationId) → Future<List<StageEventDto>>`; `RecruiterJobsRepository.setStage(String jobId, String applicationId, ApplicationStage stage) → Future<void>`; recruiter applicant row DTO gains `stage`. Tasks 7-8 consume these exact names.

- [ ] **Step 1 (TDD): Write `test/unit/data/jobs/application_stage_test.dart`**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';

void main() {
  group('ApplicationStage wire map', () {
    test('round-trips every real value', () {
      const wire = {
        ApplicationStage.applied: 'applied',
        ApplicationStage.shortlisted: 'shortlisted',
        ApplicationStage.interview: 'interview',
        ApplicationStage.offer: 'offer',
        ApplicationStage.hired: 'hired',
        ApplicationStage.rejected: 'rejected',
      };
      for (final e in wire.entries) {
        expect(e.key.wireValue, e.value);
      }
    });

    test('unknown never serializes', () {
      expect(() => ApplicationStage.unknown.wireValue, throwsStateError);
    });
  });

  group('ApplicationDto.stage', () {
    Map<String, dynamic> appJson(String stage) => {
          'id': 'a1',
          'job_id': 'j1',
          'status': 'applied',
          'source': 'feed',
          'stage': stage,
          'created_at': '2026-07-19T00:00:00Z',
          'updated_at': '2026-07-19T00:00:00Z',
        };

    test('parses a real stage', () {
      expect(ApplicationDto.fromJson(appJson('interview')).stage,
          ApplicationStage.interview);
    });

    test('unrecognised server value degrades to unknown', () {
      expect(ApplicationDto.fromJson(appJson('meh')).stage,
          ApplicationStage.unknown);
    });
  });

  group('StageEventDto', () {
    test('parses the timeline item shape', () {
      final dto = StageEventDto.fromJson({
        'from_stage': 'applied',
        'to_stage': 'shortlisted',
        'created_at': '2026-07-19T00:00:00Z',
      });
      expect(dto.fromStage, ApplicationStage.applied);
      expect(dto.toStage, ApplicationStage.shortlisted);
    });
  });
}
```

Run `cd app && flutter test test/unit/data/jobs/application_stage_test.dart` — Expected: FAIL.

- [ ] **Step 2: Create `lib/data/jobs/application_stage.dart`** (mirror `lib/data/feed/match_feedback_rating.dart`'s pattern exactly)

```dart
import 'package:json_annotation/json_annotation.dart';

/// Recruiter hiring-pipeline stage.
///
/// Mirrors backend `ApplicationStage` in `core/src/jobify/db/models.py`;
/// pinned by test/unit/data/jobs/application_stage_test.dart. `unknown` is
/// the unrecognised-server-value sentinel — it must NEVER serialize.
enum ApplicationStage {
  @JsonValue('applied')
  applied,
  @JsonValue('shortlisted')
  shortlisted,
  @JsonValue('interview')
  interview,
  @JsonValue('offer')
  offer,
  @JsonValue('hired')
  hired,
  @JsonValue('rejected')
  rejected,
  unknown,
}

extension ApplicationStageWire on ApplicationStage {
  String get wireValue => switch (this) {
        ApplicationStage.applied => 'applied',
        ApplicationStage.shortlisted => 'shortlisted',
        ApplicationStage.interview => 'interview',
        ApplicationStage.offer => 'offer',
        ApplicationStage.hired => 'hired',
        ApplicationStage.rejected => 'rejected',
        ApplicationStage.unknown =>
          throw StateError('ApplicationStage.unknown is not a wire value'),
      };
}
```

- [ ] **Step 3: Extend the DTOs in `lib/data/jobs/jobs_dto.dart`**

`ApplicationDto`: add to the constructor `required this.stage,` and the field (after `source`):

```dart
  @JsonKey(unknownEnumValue: ApplicationStage.unknown)
  final ApplicationStage stage;
```

New DTOs in the same file:

```dart
@JsonSerializable()
class StageEventDto {
  const StageEventDto({
    required this.fromStage,
    required this.toStage,
    required this.createdAt,
  });

  factory StageEventDto.fromJson(Map<String, dynamic> json) =>
      _$StageEventDtoFromJson(json);

  @JsonKey(unknownEnumValue: ApplicationStage.unknown)
  final ApplicationStage fromStage;
  @JsonKey(unknownEnumValue: ApplicationStage.unknown)
  final ApplicationStage toStage;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => _$StageEventDtoToJson(this);
}

@JsonSerializable()
class ApplicationTimelineDto {
  const ApplicationTimelineDto({required this.items});

  factory ApplicationTimelineDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationTimelineDtoFromJson(json);

  final List<StageEventDto> items;

  Map<String, dynamic> toJson() => _$ApplicationTimelineDtoToJson(this);
}
```

`lib/data/jobs/recruiter_job_dto.dart`: the applicant-row DTO (the one with `applicationId`/`displayName`/`status`) gains, after `status`:

```dart
  @JsonKey(unknownEnumValue: ApplicationStage.unknown)
  final ApplicationStage stage;
```
(+ constructor param; open the file for the exact class name and mirror-comment style.)

- [ ] **Step 4: API + repository methods**

`lib/data/jobs/applications_api.dart` (mirror its existing method style):

```dart
  Future<ApplicationTimelineDto> fetchTimeline(String applicationId) async {
    final res = await _dio
        .get<Map<String, dynamic>>('/v1/applications/$applicationId/timeline');
    return ApplicationTimelineDto.fromJson(res.data!);
  }
```

Applications repository interface + impl (whichever files define `applicationsRepositoryProvider` — open `lib/data/jobs/applications_repository*.dart`): add `Future<List<StageEventDto>> fetchTimeline(String applicationId);` returning `(await _api.fetchTimeline(id)).items`, wrapped in the impl's existing DioException-mapping idiom.

`lib/data/jobs/recruiter_jobs_api.dart`:

```dart
  Future<void> setStage(
    String jobId,
    String applicationId,
    String stage,
  ) async {
    await _dio.patch<dynamic>(
      '/v1/jobs/$jobId/applications/$applicationId/stage',
      data: {'stage': stage},
    );
  }
```

`recruiter_jobs_repository.dart` interface: `Future<void> setStage(String jobId, String applicationId, ApplicationStage stage);` — impl calls `_api.setStage(jobId, applicationId, stage.wireValue)` with the existing error-mapping idiom.

Extend the fakes in `test/helpers/fake_repositories.dart` (and any test-local fakes the compiler flags): record-and-return implementations (`stagesSet` list of `(jobId, applicationId, stage)` records; `timelines` map returning configured events).

- [ ] **Step 5: Codegen, tests, gates, commit**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
flutter test
dart format --set-exit-if-changed lib test && flutter analyze
cd ..
git add app/lib/data app/test
git commit -m "feat(app): application-stage data layer — enum, DTOs, timeline + setStage

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
NOTE: existing widget/unit tests that build `ApplicationDto` fixtures will fail compilation until their fixtures pass `stage:` — update every constructor call site and JSON fixture (add `'stage': 'applied'`) in the same commit; the analyzer output is the checklist.

---

### Task 7: Flutter applicant UI — stage chip, timeline, inbox copy

**Files (under `app/`):**
- Modify: `lib/presentation/applications/applications_screen.dart` (`_StatusPill` → stage-aware pill, ~line 142)
- Create: `lib/presentation/job_detail/application_timeline_controller.dart` (+ `.g.dart`)
- Modify: `lib/presentation/job_detail/job_detail_screen.dart` (timeline under the application section)
- Modify: `lib/presentation/notifications/notification_title.dart` (new kind case)
- Test: `test/widget/application_stage_ui_test.dart`

**Interfaces:**
- Consumes: Task 6 (`ApplicationStage`, `StageEventDto`, `fetchTimeline`); `jobDetailControllerProvider` (existing).
- Produces: applicant-facing stage labels — `applied`→"Applied", `shortlisted`→"Shortlisted", `interview`→"Interview", `offer`→"Offer", `hired`→"Hired", `rejected`→"Not selected", `unknown`→"In progress". `applicationTimelineControllerProvider(applicationId)`.

- [ ] **Step 1 (TDD): Write `test/widget/application_stage_ui_test.dart`** (use the harness style of `test/widget/applications_screen_test.dart` — open it first)

```dart
  testWidgets('applications row shows the stage label, not raw status',
      (tester) async {
    // fake applications repo returns one application with stage: interview
    // pump ApplicationsScreen per the existing harness
    expect(find.text('Interview'), findsOneWidget);
  });

  testWidgets('rejected renders as "Not selected"', (tester) async {
    // stage: rejected
    expect(find.text('Not selected'), findsOneWidget);
  });

  testWidgets('job detail shows the timeline when events exist', (tester) async {
    // fake timeline returns applied->shortlisted; pump JobDetailScreen with an application present
    expect(find.textContaining('Shortlisted'), findsWidgets);
  });

  testWidgets('timeline fetch error degrades to the chip alone', (tester) async {
    // fake timeline throws; screen still renders, no crash, no timeline section
    expect(tester.takeException(), isNull);
  });
```

Also add a plain unit expectation for the inbox copy in the same file:

```dart
  test('notificationTitle handles application_stage_changed', () {
    final n = NotificationDto(
      id: 'n1',
      kind: 'application_stage_changed',
      payload: {'job_title': 'QA Engineer', 'stage': 'shortlisted'},
      createdAt: DateTime.utc(2026, 7, 19),
      // ...other required ctor fields per the DTO...
    );
    expect(notificationTitle(n), 'Shortlisted for QA Engineer');
  });
```

Run — Expected: FAIL.

- [ ] **Step 2: Stage labels + pill in `applications_screen.dart`**

Add a shared label helper (top of the file or beside `_StatusPill`):

```dart
String stageLabel(ApplicationStage stage) => switch (stage) {
      ApplicationStage.applied => 'Applied',
      ApplicationStage.shortlisted => 'Shortlisted',
      ApplicationStage.interview => 'Interview',
      ApplicationStage.offer => 'Offer',
      ApplicationStage.hired => 'Hired',
      ApplicationStage.rejected => 'Not selected',
      ApplicationStage.unknown => 'In progress',
    };
```

Replace `_StatusPill(status: …)` usage with a stage-aware pill: withdrawn applications keep the existing withdrawn pill; otherwise show `stageLabel(item.application.stage)` with colour semantics — reuse the file's existing pill colour pattern: neutral (existing applied colours) for applied/shortlisted/interview/unknown, the design system's positive tint for offer/hired, `onSurfaceVariant`-muted for rejected. Follow `docs/design-system.md` tokens; do not invent new colours.

- [ ] **Step 3: Timeline controller + job detail section**

`lib/presentation/job_detail/application_timeline_controller.dart`:

```dart
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'application_timeline_controller.g.dart';

@riverpod
Future<List<StageEventDto>> applicationTimeline(
  Ref ref,
  String applicationId,
) =>
    ref.read(applicationsRepositoryProvider).fetchTimeline(applicationId);
```

(Match the repo provider's real import path/name from Task 6; use the codebase's current `@riverpod` function-provider idiom — check a sibling like `feed_summary_controller.dart` for the exact `Ref` typing.)

In `job_detail_screen.dart`, inside the existing application section (where the application status renders), add a `_ApplicationTimeline(applicationId: …)` ConsumerWidget that watches `applicationTimelineProvider(applicationId)` and:
- data + non-empty → a compact vertical list: `stageLabel(e.toStage)` + short date (`jobifyShortDateFormat`) per event;
- data + empty → nothing;
- loading/error → nothing (degrades to the stage chip alone — spec rule).

- [ ] **Step 4: Inbox copy — `notification_title.dart` case** (before `default:`)

```dart
    case 'application_stage_changed':
      final job = p['job_title'] as String?;
      final stage = p['stage'] as String?;
      final line = switch (stage) {
        'shortlisted' => 'Shortlisted',
        'interview' => 'Interview stage',
        'offer' => 'You have an offer',
        'hired' => 'You were hired',
        'rejected' => 'Update on your application',
        _ => 'Application updated',
      };
      return job != null ? '$line for $job' : line;
```

- [ ] **Step 5: Codegen, tests, gates, commit**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
flutter test
dart format --set-exit-if-changed lib test && flutter analyze
cd ..
git add app/lib/presentation app/test
git commit -m "feat(app): applicant stage chip, application timeline, stage-change inbox copy

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Flutter recruiter UI — stage menu on the candidate roster

**Files (under `app/`):**
- Modify: `lib/presentation/recruiter/job_applicants_screen.dart` (stage chip + PopupMenuButton per row)
- Modify: `lib/presentation/recruiter/recruiter_applicants_controller.dart` (optimistic `setStage` + revert)
- Test: `test/widget/job_applicants_stage_test.dart`

**Interfaces:**
- Consumes: Task 6 (`RecruiterJobsRepository.setStage`, applicant-row DTO `stage`); `stageLabel` from Task 7 (import it — do not duplicate the map).
- Produces: recruiter-side stage change UX: row shows current stage; menu offers the 5 targets; optimistic update, snackbar + revert on failure; withdrawn-slug failure shows "Candidate withdrew".

- [ ] **Step 1 (TDD): Write `test/widget/job_applicants_stage_test.dart`** (harness: mirror `test/widget/job_applicants_screen_test.dart`)

```dart
  testWidgets('row shows current stage and menu changes it', (tester) async {
    // fake recruiter repo: one applicant row, stage applied
    await tester.tap(find.byTooltip('Change stage').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Shortlisted').last);
    await tester.pumpAndSettle();
    expect(fakeRecruiterRepo.stagesSet, isNotEmpty); // recorded call
    expect(find.text('Shortlisted'), findsWidgets); // optimistic label
  });

  testWidgets('failure reverts the label and shows a snackbar', (tester) async {
    // fake repo throws on setStage
    await tester.tap(find.byTooltip('Change stage').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Interview').last);
    await tester.pumpAndSettle();
    expect(find.text('Applied'), findsWidgets); // reverted
    expect(find.textContaining("Couldn't update"), findsOneWidget);
  });
```

Run — Expected: FAIL.

- [ ] **Step 2: Controller mutation** (`recruiter_applicants_controller.dart` — open it; it holds a `PagedState` of applicant rows like the feed)

```dart
  /// Optimistic stage change: patch the row locally, call the API, revert on
  /// error and rethrow so the screen can snackbar.
  Future<void> setStage(
    String applicationId,
    ApplicationStage stage,
  ) async {
    final prev = state;
    _patchRow(applicationId, stage);
    try {
      await ref
          .read(recruiterJobsRepositoryProvider)
          .setStage(jobId, applicationId, stage);
    } catch (_) {
      state = prev;
      rethrow;
    }
  }
```

`_patchRow` rebuilds the row DTO with the new stage via the paged state's `copyWith` — copy EVERY constructor field of the row DTO (the silent-field-drop trap; verify against Task 6's final DTO). The controller family already carries `jobId` (check its `build` signature — adapt if the param name differs).

- [ ] **Step 3: Row UI** — in `job_applicants_screen.dart`, beside the existing download action, add:

```dart
              PopupMenuButton<ApplicationStage>(
                tooltip: 'Change stage',
                initialValue: row.stage,
                onSelected: (stage) => _changeStage(row.applicationId, stage),
                itemBuilder: (context) => const [
                  ApplicationStage.shortlisted,
                  ApplicationStage.interview,
                  ApplicationStage.offer,
                  ApplicationStage.hired,
                  ApplicationStage.rejected,
                ]
                    .map((s) => PopupMenuItem(value: s, child: Text(stageLabel(s))))
                    .toList(),
                child: /* compact chip showing stageLabel(row.stage) — follow the file's pill styling */,
              ),
```

Screen handler (capture messenger before await; map the withdrawn slug):

```dart
  Future<void> _changeStage(String applicationId, ApplicationStage stage) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref
          .read(recruiterApplicantsControllerProvider(widget.jobId).notifier)
          .setStage(applicationId, stage);
    } catch (e) {
      final withdrew = e.toString().contains('application_withdrawn');
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            withdrew ? 'Candidate withdrew' : "Couldn't update the stage",
          ),
        ),
      );
    }
  }
```

(Adapt provider name/param to the controller's real generated name.)

- [ ] **Step 4: Codegen, tests, gates, commit**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
flutter test
dart format --set-exit-if-changed lib test && flutter analyze
cd ..
git add app/lib/presentation/recruiter app/test
git commit -m "feat(app): recruiter stage menu on candidate roster — optimistic with revert

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Web employers — stage dropdown in Applicants.tsx

**Files (under `frontend/`):**
- Modify: `src/sites/employers/api/types.ts` (`ApplicantOfJobRow.stage`, `ApplicationStage` union)
- Modify: `src/sites/employers/api/client.ts` (interface + `HttpClient.setApplicationStage`)
- Modify: `src/sites/employers/pages/dashboard/Applicants.tsx` (stage column: badge + select)
- Modify: `frontend/scripts/check-api-contract.mjs` (pin `stage` on the applicants row + the new endpoint's schemas, following the script's existing format)

**Interfaces:**
- Consumes: Task 3 endpoint + Task 4 row field, verbatim.
- Produces: `ApplicationStage = "applied" | "shortlisted" | "interview" | "offer" | "hired" | "rejected"`; `EmployerClient.setApplicationStage(jobId, applicationId, stage) → Promise<{application_id, stage, updated_at}>`.

- [ ] **Step 1: Types** (`types.ts`)

```ts
export type ApplicationStage =
  | "applied"
  | "shortlisted"
  | "interview"
  | "offer"
  | "hired"
  | "rejected";

export interface StageChangeRead {
  application_id: string;
  stage: ApplicationStage;
  updated_at: string;
}
```

And add `stage: ApplicationStage;` to `ApplicantOfJobRow` (after `status`).

- [ ] **Step 2: Client** (`client.ts` — interface + impl)

```ts
  setApplicationStage(
    jobId: string,
    applicationId: string,
    stage: Exclude<ApplicationStage, "applied">,
  ): Promise<StageChangeRead>;
```

```ts
  setApplicationStage(
    jobId: string,
    applicationId: string,
    stage: Exclude<ApplicationStage, "applied">,
  ): Promise<StageChangeRead> {
    return this.request(
      "PATCH",
      `/v1/jobs/${jobId}/applications/${applicationId}/stage`,
      { stage },
    );
  }
```

(There is no employers DemoClient — the surface is live-only; nothing else implements `EmployerClient`. Verify with a grep for `implements EmployerClient` before assuming.)

- [ ] **Step 3: Applicants.tsx** — replace the Status `<td>` with a Stage cell:

```tsx
                <td>
                  {row.status === "withdrawn" ? (
                    <span className="chip">withdrawn</span>
                  ) : (
                    <select
                      className="stage-select"
                      value={row.stage}
                      disabled={savingId === row.application_id}
                      onChange={(e) =>
                        void changeStage(
                          row.application_id,
                          e.target.value as Exclude<ApplicationStage, "applied">,
                        )
                      }
                    >
                      {row.stage === "applied" && (
                        <option value="applied" disabled>
                          applied
                        </option>
                      )}
                      {(["shortlisted", "interview", "offer", "hired", "rejected"] as const).map(
                        (s) => (
                          <option key={s} value={s}>
                            {s === "rejected" ? "not selected" : s}
                          </option>
                        ),
                      )}
                    </select>
                  )}
                </td>
```

With component state + handler:

```tsx
  const [savingId, setSavingId] = useState<string | null>(null);
  const [stageError, setStageError] = useState<string | null>(null);

  const changeStage = async (
    applicationId: string,
    stage: Exclude<ApplicationStage, "applied">,
  ) => {
    if (!jobId) return;
    setSavingId(applicationId);
    setStageError(null);
    try {
      await client.setApplicationStage(jobId, applicationId, stage);
      reload();
    } catch (e) {
      setStageError(errorMessage(e));
    } finally {
      setSavingId(null);
    }
  };
```

(`reload` comes from the existing `usePagedFetch` return — destructure it; import `errorMessage` the way sibling pages do; render `stageError` through the existing `ErrorNotice`. Reconcile `className`s against the real CSS — if `stage-select` doesn't exist in the employers stylesheet, reuse whatever class the surface's existing `<select>`s use, or the bare element if none.)

Table header: rename the `Status` column header to `Stage`.

- [ ] **Step 4: Contract pins** — `frontend/scripts/check-api-contract.mjs`: add `stage` to the applicants-row field list it already pins, and pin `StageChangeRequest`/`StageChangeRead` per the script's existing entry format (open it and mirror).

- [ ] **Step 5: Build + commit**

```bash
cd frontend && npm run build && cd ..
git add frontend/src/sites/employers frontend/scripts/check-api-contract.mjs
git commit -m "feat(employers): stage dropdown on the applicant roster

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Docs, full verification sweep, PR

**Files:**
- Modify: `api/CLAUDE.md` (recruiter routes + applications sections), `core/CLAUDE.md` (new section)

**Interfaces:** none — verification + documentation only.

- [ ] **Step 1: Docs**

`core/CLAUDE.md`, new section after "Match feedback":

```markdown
## Application stages (`applications.stage` + `application_stage_events`) — spec `2026-07-19-application-stages-design.md`

- **`status` = applicant lifecycle (applied/withdrawn); `stage` = recruiter pipeline** (varchar+CHECK `applied|shortlisted|interview|offer|hired|rejected`; `ApplicationStage` StrEnum at the boundary — the native-enum `status` is legacy, don't copy it). Withdrawal freezes stage; **re-apply resets stage to `applied` and writes a stage event with the applicant as actor**.
- **`application_stage_events` powers the applicant timeline** — append-only in practice, `actor_user_id` SET NULL (survives DSR), actor NEVER exposed to the applicant. DSR class: **export-only** (like `applications`) — exported, kept on delete; pinned in `_EXPORT_ONLY_TABLES`.
- **Every real transition, one txn:** structlog → `audit_log("application.stage_changed")` → event row → Notification (kind `application_stage_changed`, EMAIL + IN_APP). Same-stage PATCH = 200 no-op with none of those. Rejection copy is neutral ("moved forward with other candidates"); applicant-facing label is "Not selected".
```

`api/CLAUDE.md`, append to the "Recruiter routes" section:

```markdown
- **`PATCH /v1/jobs/{id}/applications/{aid}/stage`** — recruiter pipeline; `_load_recruiter_job` guard first, then 404 (application under this job, uniform) → 409 `application_withdrawn` → 422 (`Literal` of the 5 targets; `applied` is never recruiter-settable). Transition side-effects live in `jobify_api.applications.service.change_application_stage` (one txn: structlog → audit → event → dual-channel notification). **`GET /v1/applications/{id}/timeline`** is applicant-owned (uniform 404) and never exposes the actor.
```

- [ ] **Step 2: Full verification sweep (exact CI commands)**

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
uv run pytest tests/unit/test_openapi_contract.py   # must pass WITHOUT the update env var
```
Expected: everything green. If ANY command fails, STOP and report BLOCKED with output.

- [ ] **Step 3: Commit docs, push, open PR (do NOT merge)**

```bash
git add core/CLAUDE.md api/CLAUDE.md
git commit -m "docs: application-stage invariants in core/api CLAUDE.md

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git push -u origin HEAD
gh pr create --title "Application stages — closing the apply loop for applicants" --body "$(cat <<'EOF'
Implements docs/superpowers/specs/2026-07-19-application-stages-design.md — the applicant-usefulness brainstorm's slice A (BRD: "low application visibility").

- `applications.stage` (varchar+CHECK) + `application_stage_events` timeline table (migration 0026); DSR export-only wiring
- Recruiter `PATCH /v1/jobs/{id}/applications/{aid}/stage` — free movement across 5 stages, no-op-safe, 409 on withdrawn; one txn: structlog → audit → event → EMAIL+IN_APP notification (neutral rejection copy)
- `stage` on applicant + recruiter payloads; re-apply resets stage with a recorded event; `GET /v1/applications/{id}/timeline`
- Flutter: applicant stage chip ("Not selected" for rejected) + job-detail timeline + inbox copy; recruiter stage menu (optimistic + revert)
- Web employers: stage dropdown on the applicant roster; contract pins

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
(Multi-account note: if `gh pr create` 404s, `gh auth switch --user ahamedShahWahid`, create, then `gh auth switch --user lighthouse-learning`.)

---

## Self-review notes (resolved during authoring)

- **Spec coverage:** storage (T1), DSR export-only (T2), transition rules + guards + notification + SES copy (T3), payload `stage` + re-apply reset (T4), timeline endpoint (T5), Flutter applicant (T6-7), Flutter recruiter (T8), employers web (T9), docs + gates + PR (T10). Notification consent-gating needs no new code — the existing sweep gate is kind-agnostic; T3's tests assert row creation, the sweep's own tests cover gating.
- **Type consistency:** `ApplicationStage` values lowercase everywhere; repo method names `fetchTimeline`/`setStage` identical across T6-T8; `StageChangeRead {application_id, stage, updated_at}` mirrored in T9 TS; `stageLabel` defined once (T7) and imported by T8.
- **Known adaptation points (deliberate):** integration-test fixture helpers come from named existing files; Flutter provider/controller names verified against generated code at implementation time; employers CSS classes reconciled against the real stylesheet. These are anchored instructions, not placeholders.
- **Deliberate scope note:** recruiter roster keeps its existing `status == "applied"` filter — withdrawn candidates stay hidden from the roster (the 409 is defense-in-depth); changing roster membership is out of scope.
