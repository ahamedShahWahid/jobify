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

from jobify.consent import seed_default_consents
from jobify.db.models import (
    Applicant,
    ApplicantPreferences,
    Application,
    ApplicationStageEvent,
    AuditLog,
    Employer,
    EmployerInvite,
    EmployerInviteStatus,
    EmployerUser,
    Job,
    JobStatus,
    User,
    UserRole,
)
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration


def _live_invite(*, employer_id, email: str, invited_by=None) -> EmployerInvite:
    from datetime import UTC, datetime, timedelta

    return EmployerInvite(
        employer_id=employer_id,
        email=email.lower(),
        role="member",
        status=EmployerInviteStatus.PENDING,
        invited_by_user_id=invited_by,
        expires_at=datetime.now(UTC) + timedelta(days=14),
    )


async def _make_applicant(session: AsyncSession) -> tuple[User, Applicant, str]:
    user = User(email=f"dsr-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="DSR Test User")
    session.add(applicant)
    await session.flush()
    session.add(ApplicantPreferences(applicant_id=applicant.id))
    await seed_default_consents(session, user=user)
    await session.commit()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, applicant, token


async def _make_recruiter_with_employer(
    session: AsyncSession,
) -> tuple[User, Employer, Job, str]:
    user = User(email=f"rec-{uuid4().hex[:8]}@example.com", role=UserRole.RECRUITER)
    session.add(user)
    await session.flush()
    employer_name = f"Test Employer {uuid4().hex[:6]}"
    employer = Employer(name=employer_name, name_norm=employer_name.lower())
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
    assert len(body["applicant_preferences"]) == 1
    assert body["applicant_preferences"][0]["locations"] == []
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
async def test_export_includes_received_and_sent_invites(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, employer, _job, token = await _make_recruiter_with_employer(session)
    # An invite this recruiter SENT to someone else.
    session.add(
        _live_invite(
            employer_id=employer.id,
            email="someone-else@example.com",
            invited_by=user.id,
        )
    )
    # An invite this user RECEIVED at their own email from another employer.
    other = Employer(name="Other Co", name_norm="other co")
    session.add(other)
    await session.flush()
    session.add(_live_invite(employer_id=other.id, email=user.email))
    await session.commit()

    resp = await async_client.post(
        "/v1/me/dsr/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sent_invites"]) == 1
    assert body["sent_invites"][0]["email"] == "someone-else@example.com"
    assert len(body["received_invites"]) == 1
    assert body["received_invites"][0]["employer_name"] == "Other Co"


@pytest.mark.asyncio
async def test_export_includes_live_and_soft_deleted_preferences_rows(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    """Export convention: ALL rows we hold, no deleted_at filter. A live +
    soft-deleted pair is legal under the partial-unique index — the old
    scalar_one_or_none() raised MultipleResultsFound on exactly this."""
    from datetime import UTC, datetime

    user, applicant, token = await _make_applicant(session)
    old_row = (
        await session.execute(
            select(ApplicantPreferences).where(ApplicantPreferences.applicant_id == applicant.id)
        )
    ).scalar_one()
    old_row.deleted_at = datetime.now(UTC)
    session.add(ApplicantPreferences(applicant_id=applicant.id, locations=["Pune"]))
    await session.commit()

    resp = await async_client.post(
        "/v1/me/dsr/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    prefs = resp.json()["applicant_preferences"]
    assert len(prefs) == 2
    assert sorted(p["deleted_at"] is not None for p in prefs) == [False, True]


@pytest.mark.asyncio
async def test_export_includes_application_stage_events_ascending(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    """application_stage_events is export-only: exported under the user's
    applications history, ascending by created_at, actor identity never
    disclosed to the applicant (design spec 2026-07-19). A second
    applicant's own application + stage event must never leak in."""
    from datetime import UTC, datetime, timedelta

    user, applicant, token = await _make_applicant(session)
    emp_name = f"E-{uuid4().hex[:6]}"
    employer = Employer(name=emp_name, name_norm=emp_name.lower())
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Backend Engineer",
        description="DSR stage-events test job.",
        locations=["Remote"],
        status=JobStatus.OPEN,
        min_exp_years=1,
        max_exp_years=5,
    )
    session.add(job)
    await session.flush()
    application = Application(applicant_id=applicant.id, job_id=job.id)
    session.add(application)
    await session.flush()

    now = datetime.now(UTC)
    # Insertion order deliberately DIVERGES from chronological order — the
    # later event is added first — so an export query missing its ORDER BY
    # cannot coincidentally pass by matching insertion/heap order.
    session.add(
        ApplicationStageEvent(
            application_id=application.id,
            from_stage="shortlisted",
            to_stage="interview",
            created_at=now + timedelta(seconds=1),
        )
    )
    session.add(
        ApplicationStageEvent(
            application_id=application.id,
            from_stage="applied",
            to_stage="shortlisted",
            created_at=now,
        )
    )

    # Negative control: another applicant's own application + stage event
    # must not appear in this applicant's export.
    _other_user, other_applicant, _other_token = await _make_applicant(session)
    other_job = Job(
        employer_id=employer.id,
        title="Other Role",
        description="Other applicant's job.",
        locations=["Remote"],
        status=JobStatus.OPEN,
        min_exp_years=1,
        max_exp_years=5,
    )
    session.add(other_job)
    await session.flush()
    other_application = Application(applicant_id=other_applicant.id, job_id=other_job.id)
    session.add(other_application)
    await session.flush()
    session.add(
        ApplicationStageEvent(
            application_id=other_application.id,
            from_stage="applied",
            to_stage="rejected",
            created_at=now,
        )
    )
    await session.commit()

    resp = await async_client.post(
        "/v1/me/dsr/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    events = body["application_stage_events"]
    assert len(events) == 2
    assert [(e["from_stage"], e["to_stage"]) for e in events] == [
        ("applied", "shortlisted"),
        ("shortlisted", "interview"),
    ]
    # actor_user_id is redacted — internal actor identity, never disclosed
    # to the data subject.
    assert "actor_user_id" not in events[0]
    assert all(e["application_id"] != str(other_application.id) for e in events)


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
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,
                    AuditLog.action.in_(["user.dsr_export_requested", "user.dsr_export_completed"]),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 2
    actions = {r.action for r in audit_rows}
    assert actions == {"user.dsr_export_requested", "user.dsr_export_completed"}
    completed = next(r for r in audit_rows if r.action == "user.dsr_export_completed")
    assert "section_counts" in completed.context
    assert completed.context["section_counts"]["user_consents"] == 7


async def test_export_serializes_pgvector_embedding(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    """An applicant WITH an embedding row must export cleanly.

    pgvector's asyncpg codec materializes the vector as numpy.ndarray on a
    real DB round-trip (the savepoint identity map hides this — it returns
    the original Python list), and _row_to_dict must convert it or
    model_dump_json() 500s. Caught live by E2E; expire_all() forces the
    reload here.
    """
    from jobify.db.models import ApplicantEmbedding

    user, applicant, token = await _make_applicant(session)
    session.add(
        ApplicantEmbedding(
            applicant_id=applicant.id,
            embedding=[0.5] * 1536,
            model_name="test-model",
            canonicalized_text_hash="x" * 64,
            input_tokens=128,
        )
    )
    await session.commit()
    session.expire_all()  # force the next read through asyncpg → ndarray

    resp = await async_client.post(
        "/v1/me/dsr/export", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    emb = resp.json()["applicant_embedding"]
    assert emb is not None
    assert isinstance(emb["embedding"], list)
    assert len(emb["embedding"]) == 1536
