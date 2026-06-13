# P4-C DSR Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship `POST /v1/me/dsr/export` — a sync JSON dump of every user-linked row, plus the user's audit history, plus a `redactions` array documenting what was excluded. Writes two audit rows per export.

**Architecture:** Pydantic envelope model in `kpa/dsr/__init__.py`, one read-only per-section helper per table. Route in `routes/dsr.py` writes `user.dsr_export_requested` BEFORE assembly and `user.dsr_export_completed` AFTER. Refresh tokens redacted; resume binaries metadata-only.

**Tech Stack:** FastAPI / async SQLAlchemy / Pydantic v2 / pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-dsr-export-design.md`

---

## Files

**Create:**
- `api/src/kpa/dsr/__init__.py` — `UserExport` model + `build_user_export` + per-section collectors.
- `api/src/kpa/routes/dsr.py` — the endpoint.
- `api/tests/unit/dsr/__init__.py` (empty).
- `api/tests/unit/dsr/test_builder_signature.py` — pure signature test.
- `api/tests/integration/test_dsr_export.py` — applicant + recruiter + auth + redaction + audit-rows tests.

**Modify:**
- `api/src/kpa/app_factory.py` — mount the new router.
- `CLAUDE.md` — add the "DSR export" section.

---

### Task 1: Export builder module

**Files:**
- Create: `api/src/kpa/dsr/__init__.py`
- Create: `api/tests/unit/dsr/__init__.py` (empty)
- Create: `api/tests/unit/dsr/test_builder_signature.py`

- [ ] **Step 1: Write the failing signature unit test**

`api/tests/unit/dsr/__init__.py` — empty (`""`).

`api/tests/unit/dsr/test_builder_signature.py`:

```python
"""Pure-signature contract test for build_user_export. No DB."""
from __future__ import annotations

import inspect

from kpa.dsr import UserExport, build_user_export


def test_builder_signature() -> None:
    sig = inspect.signature(build_user_export)
    params = list(sig.parameters)
    assert params[0] == "session"
    assert sig.parameters["user"].kind == inspect.Parameter.KEYWORD_ONLY


def test_user_export_top_level_fields() -> None:
    fields = set(UserExport.model_fields.keys())
    expected = {
        "version",
        "exported_at",
        "exported_for_user_id",
        "user",
        "applicant",
        "oauth_identities",
        "resumes",
        "applicant_embedding",
        "applications",
        "saved_jobs",
        "matches",
        "notifications",
        "user_consents",
        "audit_history",
        "employer_memberships",
        "owned_jobs",
        "redactions",
        "notes",
    }
    assert fields == expected, f"missing={expected - fields}, extra={fields - expected}"
```

Run `uv run pytest -v tests/unit/dsr/` — expect FAIL (`kpa.dsr` doesn't exist).

- [ ] **Step 2: Write the builder**

Create `api/src/kpa/dsr/__init__.py`.

The module exports:
- `UserExport` (Pydantic v2 model — the envelope).
- `build_user_export(session, *, user) -> UserExport`.

The model must have exactly the 18 top-level fields from the unit test. Each field's type:

```python
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _SectionItem(BaseModel):
    """Generic row dump — we serialize SQLAlchemy rows to dicts via model_to_dict
    rather than introducing a Pydantic model per table. Stable enough for v0."""

    model_config = ConfigDict(extra="allow")


class RedactionEntry(BaseModel):
    type: str
    reason: str


class UserExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "1"
    exported_at: datetime
    exported_for_user_id: UUID

    user: dict[str, Any]
    applicant: dict[str, Any] | None = None

    oauth_identities: list[dict[str, Any]] = []
    resumes: list[dict[str, Any]] = []
    applicant_embedding: dict[str, Any] | None = None
    applications: list[dict[str, Any]] = []
    saved_jobs: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []
    user_consents: list[dict[str, Any]] = []
    audit_history: list[dict[str, Any]] = []

    employer_memberships: list[dict[str, Any]] = []
    owned_jobs: list[dict[str, Any]] = []

    redactions: list[RedactionEntry] = []
    notes: list[str] = []
```

The choice of `dict[str, Any]` per section is deliberate — for v0 we don't introduce 12 Pydantic row models; we serialize SQLAlchemy rows via a row-to-dict helper. Future versions can tighten.

Now `build_user_export`:

```python
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.db.models import (
    Applicant,
    ApplicantEmbedding,
    Application,
    AuditLog,
    Employer,
    EmployerUser,
    Job,
    Match,
    Notification,
    OAuthIdentity,
    Resume,
    SavedJob,
    User,
    UserConsent,
    UserRole,
)

_REDACTIONS = [
    RedactionEntry(
        type="refresh_tokens",
        reason="Session secrets — not personal data; would let an exposed export be used to impersonate the user.",
    ),
    RedactionEntry(
        type="resume_binaries",
        reason="Metadata included; binaries downloadable on request from privacy@kpa.",
    ),
]

_NOTES = [
    "This export was generated automatically.",
    "For data older than your sign-up date, contact privacy@kpa.",
    "Resume PDFs/DOCXs are not included in this JSON — request copies separately.",
]


def _row_to_dict(row: object) -> dict[str, Any]:
    """SQLAlchemy ORM row → dict via column introspection. Includes every
    mapped column; does NOT walk relationships."""
    state = row.__dict__.copy()
    state.pop("_sa_instance_state", None)
    # Convert UUIDs and datetimes to ISO strings for JSON friendliness.
    out: dict[str, Any] = {}
    for k, v in state.items():
        if hasattr(v, "isoformat"):  # datetime
            out[k] = v.isoformat()
        elif hasattr(v, "hex"):  # UUID
            out[k] = str(v)
        else:
            out[k] = v
    return out


async def build_user_export(
    session: AsyncSession,
    *,
    user: User,
) -> UserExport:
    user_dict = _row_to_dict(user)

    applicant_row = (
        await session.execute(
            select(Applicant).where(Applicant.user_id == user.id)
        )
    ).scalar_one_or_none()
    applicant_dict = _row_to_dict(applicant_row) if applicant_row else None

    oauth_rows = (
        await session.execute(
            select(OAuthIdentity).where(OAuthIdentity.user_id == user.id)
        )
    ).scalars().all()

    resumes: list[dict[str, Any]] = []
    embedding_dict: dict[str, Any] | None = None
    applications: list[dict[str, Any]] = []
    saved_jobs: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []

    if applicant_row is not None:
        applicant_id = applicant_row.id
        resumes = [
            _row_to_dict(r)
            for r in (
                await session.execute(
                    select(Resume).where(Resume.applicant_id == applicant_id)
                )
            ).scalars().all()
        ]
        embedding_row = (
            await session.execute(
                select(ApplicantEmbedding).where(
                    ApplicantEmbedding.applicant_id == applicant_id
                )
            )
        ).scalar_one_or_none()
        if embedding_row is not None:
            embedding_dict = _row_to_dict(embedding_row)
        applications = [
            _row_to_dict(a)
            for a in (
                await session.execute(
                    select(Application).where(
                        Application.applicant_id == applicant_id
                    )
                )
            ).scalars().all()
        ]
        saved_jobs = [
            _row_to_dict(s)
            for s in (
                await session.execute(
                    select(SavedJob).where(SavedJob.applicant_id == applicant_id)
                )
            ).scalars().all()
        ]
        matches = [
            _row_to_dict(m)
            for m in (
                await session.execute(
                    select(Match).where(Match.applicant_id == applicant_id)
                )
            ).scalars().all()
        ]

    notifications = [
        _row_to_dict(n)
        for n in (
            await session.execute(
                select(Notification).where(Notification.user_id == user.id)
            )
        ).scalars().all()
    ]

    user_consents = [
        _row_to_dict(c)
        for c in (
            await session.execute(
                select(UserConsent).where(UserConsent.user_id == user.id)
            )
        ).scalars().all()
    ]

    audit_history = [
        _row_to_dict(a)
        for a in (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.actor_user_id == user.id)
                .order_by(AuditLog.created_at.desc())
            )
        ).scalars().all()
    ]

    employer_memberships: list[dict[str, Any]] = []
    owned_jobs: list[dict[str, Any]] = []

    if user.role in (UserRole.RECRUITER, UserRole.ADMIN):
        eu_rows = (
            await session.execute(
                select(EmployerUser, Employer)
                .join(Employer, Employer.id == EmployerUser.employer_id)
                .where(EmployerUser.user_id == user.id)
            )
        ).all()
        for eu, emp in eu_rows:
            entry = _row_to_dict(eu)
            entry["employer"] = _row_to_dict(emp)
            employer_memberships.append(entry)

        if eu_rows:
            employer_ids = [eu.employer_id for eu, _ in eu_rows]
            owned_jobs = [
                _row_to_dict(j)
                for j in (
                    await session.execute(
                        select(Job).where(Job.employer_id.in_(employer_ids))
                    )
                ).scalars().all()
            ]

    return UserExport(
        exported_at=datetime.now(UTC),
        exported_for_user_id=user.id,
        user=user_dict,
        applicant=applicant_dict,
        oauth_identities=[_row_to_dict(o) for o in oauth_rows],
        resumes=resumes,
        applicant_embedding=embedding_dict,
        applications=applications,
        saved_jobs=saved_jobs,
        matches=matches,
        notifications=notifications,
        user_consents=user_consents,
        audit_history=audit_history,
        employer_memberships=employer_memberships,
        owned_jobs=owned_jobs,
        redactions=list(_REDACTIONS),
        notes=list(_NOTES),
    )
```

- [ ] **Step 3: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v tests/unit/dsr/
uv run ruff check src/kpa/dsr/ tests/unit/dsr/
uv run ruff format src/kpa/dsr/ tests/unit/dsr/
uv run mypy
```

2/2 unit tests pass; ruff + mypy clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/dsr/ api/tests/unit/dsr/
git commit -m "feat(api): DSR export builder (UserExport + build_user_export)

Read-only assembly of every user-linked row into a Pydantic envelope.
Refresh tokens redacted via the redactions[] field; resume binaries
metadata-only. Recruiter+admin get employer_memberships + owned_jobs
populated; applicant sections empty for those roles."
```

---

### Task 2: Route + audit rows + mount

**Files:**
- Create: `api/src/kpa/routes/dsr.py`
- Modify: `api/src/kpa/app_factory.py`

- [ ] **Step 1: Write the route**

Create `api/src/kpa/routes/dsr.py`:

```python
"""POST /v1/me/dsr/export — DPDP § 11 right-of-access endpoint."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.audit import audit_log
from kpa.auth.dependencies import current_user
from kpa.db.models import User
from kpa.db.session import get_session
from kpa.dsr import build_user_export

router = APIRouter(prefix="/v1/me", tags=["dsr"])
_log = structlog.get_logger(__name__)


@router.post("/dsr/export")
async def export_user_data(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Return a JSON dump of every row tied to the authenticated user.

    DPDP § 11 right-of-access. Sync at MVP scale; if/when audit history
    exceeds ~10K rows per user, switch to async + signed-URL.
    """
    request_id = request.state.request_id

    # 1. Audit the request BEFORE assembly. Durable even if assembly fails.
    await audit_log(
        session,
        action="user.dsr_export_requested",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={"request_id": request_id},
    )
    await session.flush()

    export = await build_user_export(session, user=user)

    # 2. Audit completion with section counts.
    section_counts = {
        "oauth_identities": len(export.oauth_identities),
        "resumes": len(export.resumes),
        "applicant_embedding": 1 if export.applicant_embedding else 0,
        "applications": len(export.applications),
        "saved_jobs": len(export.saved_jobs),
        "matches": len(export.matches),
        "notifications": len(export.notifications),
        "user_consents": len(export.user_consents),
        "audit_history": len(export.audit_history),
        "employer_memberships": len(export.employer_memberships),
        "owned_jobs": len(export.owned_jobs),
    }
    await audit_log(
        session,
        action="user.dsr_export_completed",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        context={"request_id": request_id, "section_counts": section_counts},
    )

    _log.info(
        "dsr.export-completed",
        user_id=str(user.id),
        section_counts=section_counts,
    )

    body = export.model_dump_json()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"kpa-data-export-{user.id}-{timestamp}.json"

    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
```

- [ ] **Step 2: Mount the router**

In `api/src/kpa/app_factory.py`, find the existing `from kpa.routes import consents as consents_routes` (added in PR #26). Add a sibling:

```python
from kpa.routes import dsr as dsr_routes
# ... with the other app.include_router calls:
app.include_router(dsr_routes.router)
```

Match the surrounding style.

- [ ] **Step 3: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run ruff check src/kpa/routes/dsr.py src/kpa/app_factory.py
uv run ruff format src/kpa/routes/dsr.py src/kpa/app_factory.py
uv run mypy
```

- [ ] **Step 4: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/src/kpa/routes/dsr.py api/src/kpa/app_factory.py
git commit -m "feat(api): POST /v1/me/dsr/export endpoint

Writes user.dsr_export_requested before assembly + user.dsr_export_completed
after. Returns the envelope as application/json with Content-Disposition:
attachment and Cache-Control: no-store. Sync at MVP scale per spec §5."
```

---

### Task 3: Integration tests + CLAUDE.md + PR

**Files:**
- Create: `api/tests/integration/test_dsr_export.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write the integration tests**

Create `api/tests/integration/test_dsr_export.py`:

```python
"""Integration tests for POST /v1/me/dsr/export.

Covers:
1. Applicant happy path — all sections populated where applicable.
2. Recruiter happy path — employer_memberships + owned_jobs populated;
   applicant sections empty.
3. Authentication required (no bearer → 401).
4. Refresh tokens never appear in the export body.
5. Two audit rows written per export (request + completed).
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import mint_access_token
from kpa.consent import seed_default_consents
from kpa.db.models import (
    Applicant,
    AuditLog,
    Employer,
    EmployerUser,
    Job,
    JobStatus,
    User,
    UserRole,
)


async def _make_applicant(session: AsyncSession) -> tuple[User, Applicant, str]:
    user = User(
        email=f"dsr-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT
    )
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="DSR Test User")
    session.add(applicant)
    await session.flush()
    await seed_default_consents(session, user=user)
    await session.commit()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, applicant, token


async def _make_recruiter_with_employer(
    session: AsyncSession,
) -> tuple[User, Employer, Job, str]:
    user = User(
        email=f"rec-{uuid4().hex[:8]}@example.com", role=UserRole.RECRUITER
    )
    session.add(user)
    await session.flush()
    employer = Employer(name=f"Test Employer {uuid4().hex[:6]}")
    session.add(employer)
    await session.flush()
    link = EmployerUser(employer_id=employer.id, user_id=user.id, role="owner")
    session.add(link)
    job = Job(
        employer_id=employer.id,
        title="Senior Engineer",
        description="DSR test job.",
        locations=["Remote"],
        status=JobStatus.OPEN,
        min_exp_years=3,
        max_exp_years=8,
    )
    session.add(job)
    await seed_default_consents(session, user=user)
    await session.commit()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, employer, job, token


@pytest.mark.asyncio
async def test_applicant_export_happy_path(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _applicant, token = await _make_applicant(session)
    resp = await async_client.post(
        "/v1/me/dsr/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["cache-control"] == "no-store"

    body = resp.json()
    assert body["version"] == "1"
    assert body["exported_for_user_id"] == str(user.id)
    assert body["user"]["id"] == str(user.id)
    assert body["applicant"] is not None
    assert body["applicant"]["full_name"] == "DSR Test User"
    assert len(body["user_consents"]) == 7  # all default scopes
    assert body["employer_memberships"] == []
    assert body["owned_jobs"] == []
    assert any(r["type"] == "refresh_tokens" for r in body["redactions"])
    assert len(body["notes"]) >= 1


@pytest.mark.asyncio
async def test_recruiter_export_includes_employer_and_jobs(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, employer, job, token = await _make_recruiter_with_employer(session)
    resp = await async_client.post(
        "/v1/me/dsr/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicant"] is None
    assert body["resumes"] == []
    assert body["applications"] == []
    assert len(body["employer_memberships"]) == 1
    assert body["employer_memberships"][0]["employer"]["id"] == str(employer.id)
    assert any(j["id"] == str(job.id) for j in body["owned_jobs"])


@pytest.mark.asyncio
async def test_export_requires_auth(async_client: AsyncClient) -> None:
    resp = await async_client.post("/v1/me/dsr/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_never_includes_refresh_tokens(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _applicant, token = await _make_applicant(session)
    resp = await async_client.post(
        "/v1/me/dsr/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Scan the entire serialized body for the substring; no false positives
    # because refresh_tokens is not a documented top-level key in the envelope.
    body_text = resp.text
    parsed = json.loads(body_text)
    assert "refresh_tokens" not in parsed
    # Make sure the redaction is documented.
    assert any(r["type"] == "refresh_tokens" for r in parsed["redactions"])


@pytest.mark.asyncio
async def test_export_writes_two_audit_rows(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, _applicant, token = await _make_applicant(session)
    resp = await async_client.post(
        "/v1/me/dsr/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    audit_rows = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action.in_(
                    ["user.dsr_export_requested", "user.dsr_export_completed"]
                ),
            )
            .order_by(AuditLog.created_at.asc())
        )
    ).scalars().all()
    assert len(audit_rows) == 2
    assert audit_rows[0].action == "user.dsr_export_requested"
    assert audit_rows[1].action == "user.dsr_export_completed"
    assert "section_counts" in audit_rows[1].context
    assert audit_rows[1].context["section_counts"]["user_consents"] == 7
```

- [ ] **Step 2: Add CLAUDE.md section**

Open `CLAUDE.md`. Find the existing `### Consent + notification-channel preferences` section (added by PR #26). AFTER its body and BEFORE the next `###`, insert:

```markdown
### DSR export

- **Sync HTTP, JSON envelope.** `POST /v1/me/dsr/export` returns the dump immediately as `application/json` with `Content-Disposition: attachment; filename="kpa-data-export-{user_id}-{timestamp}.json"` and `Cache-Control: no-store`. MVP-acceptable at our scale; switch to async + signed-URL when an applicant's audit history exceeds ~10K rows.
- **`refresh_tokens` are NEVER in the export.** Session secrets, not personal data. A `redactions` entry documents the exclusion. When MFA ships, `totp_secret` + recovery codes get the same treatment.
- **`audit_history` is `actor_user_id = self.id` only** in v0 — not the full `(resource_type, resource_id)` join. Documented v0 limit per spec §4.2. Expand when a regulator pushes back.
- **Two audit rows per export.** `user.dsr_export_requested` (written + flushed BEFORE assembly) and `user.dsr_export_completed` (written AFTER assembly with `section_counts` in context). If assembly throws, the request row is durable; the completion row is not. Failed-export replay is admin tooling later.
- **Reserved action slugs for sub-project D (DSR-delete):** `user.dsr_delete_requested`, `user.dsr_deleted`. Don't reuse these prefixes for unrelated actions.
- **Recruiters get a different envelope** — applicant sections (`applicant`, `resumes`, `applicant_embedding`, `applications`, `saved_jobs`, `matches`) are empty; `employer_memberships` + `owned_jobs` populated. Admins get an all-empty envelope today.
- **Per-section serialization is `dict[str, Any]` not a per-table Pydantic model.** Trade-off for v0 — we don't introduce 12 row-shape models. The export contract is the section *set*, not the row schemas; the row schemas drift with the existing tables and the export inherits that.
```

- [ ] **Step 3: Verify**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/api
uv run pytest -v -m integration tests/integration/test_dsr_export.py
uv run pytest -m integration -q  # full suite — must stay green (baseline 268 → 273)
uv run pytest -m "not integration" -q
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

- [ ] **Step 4: Commit + push + PR**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add api/tests/integration/test_dsr_export.py CLAUDE.md
git commit -m "test(api): integration tests + CLAUDE.md docs for P4-C DSR export"

git push -u origin feat/p4-dsr-export
gh pr create --title "feat(api): P4-C DSR export pipeline" --body "$(cat <<'EOF'
## Summary
Third P4 sub-project (of A→B→C in the approved DPDP plan). Depends on A (audit_logs) and B (consent helper).

- `POST /v1/me/dsr/export` returns a JSON envelope with every user-linked row, audit history, recruiter-side data (when applicable), and a `redactions` array documenting what was excluded.
- `refresh_tokens` deliberately omitted — they're session secrets, not personal data, and exporting them would let an exposed export be used for impersonation. The redaction is documented in the envelope itself.
- Two audit rows per export: `user.dsr_export_requested` (flushed BEFORE assembly so it's durable even on failure) and `user.dsr_export_completed` (with `section_counts` in context).
- Sync at MVP scale per spec §5; envelope shape supports a future async + signed-URL upgrade without breaking v0 clients.

Spec: `docs/superpowers/specs/2026-05-29-dsr-export-design.md`
Plan: `docs/superpowers/plans/2026-05-29-dsr-export.md`

## Test plan
- [x] `uv run pytest -m integration tests/integration/test_dsr_export.py` — 5/5 pass
- [x] Full integration suite stays green (268 baseline → 273)
- [x] `uv run mypy` clean
- [x] `uv run ruff check` clean

## v0 documented limits
- `audit_history` uses `actor_user_id = self.id` only — not the `(resource_type, resource_id)` join. Tracked in CLAUDE.md for expansion if a regulator asks.
- Per-section payloads are `dict[str, Any]`, not Pydantic row models. The contract is the SECTION SET, not the row schemas — those drift with the tables.

## Out of scope
- Sub-project D (DSR delete) — separate PR
- Admin-side "export any user" — separate sub-project
- Resume binaries inline in the export — applicant-side download endpoint needed first
- Rate limiting

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review checklist

- [x] Every spec section maps to a task: §3 endpoint → Task 2; §4 envelope shape → Task 1; §6 audit rows → Task 2; §7 builder → Task 1; §9 docs → Task 3.
- [x] Refresh-token redaction is asserted in BOTH a route-level test and a builder-level note. Two independent layers of guarantee.
- [x] The `user.dsr_export_requested` flush BEFORE assembly is explicit in both the spec and the route code — failure-survival is intentional.
- [x] No placeholders. Every step has actual code or actual commands.
- [x] Sub-project D's reserved slugs (`user.dsr_delete_requested`, `user.dsr_deleted`) are flagged in CLAUDE.md so D's implementer doesn't conflict.
