"""Integration tests for DELETE /v1/me/dsr.

Covers:
1. Confirmation guard — wrong token / missing field → 400 or 422.
2. Applicant happy path — user + applicant tombstoned, oauth + consents
   + notifications + refresh_tokens hard-gone, audit rows written.
3. Recruiter happy path — sole-owner employer warning in response.
4. Application + match survive anonymized after applicant delete.
5. JWT becomes invalid after delete (401 user_not_found).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.google_verifier import GoogleClaims
from kpa.auth.tokens import mint_access_token
from kpa.consent import seed_default_consents
from kpa.db.models import (
    Applicant,
    Application,
    ApplicationStatus,
    AuditLog,
    Employer,
    EmployerInvite,
    EmployerInviteStatus,
    EmployerUser,
    Job,
    JobStatus,
    Notification,
    NotificationChannel,
    OAuthIdentity,
    OAuthProvider,
    Resume,
    User,
    UserConsent,
    UserRole,
)
from tests.integration.conftest import FakeGoogleIdTokenVerifier

pytestmark = pytest.mark.integration

_CONFIRMATION = {"confirmation": "DELETE_MY_ACCOUNT"}


async def _make_applicant_with_dependencies(
    session: AsyncSession,
) -> tuple[User, Applicant, str]:
    user = User(email=f"dsrd-{uuid4().hex[:8]}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="DSR Test User")
    session.add(applicant)
    await session.flush()
    # OAuth identity
    session.add(
        OAuthIdentity(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_subject=f"sub-{uuid4().hex}",
            email_at_link=user.email,
        )
    )
    # Notification
    session.add(
        Notification(
            user_id=user.id,
            kind="application.applied",
            channel=NotificationChannel.IN_APP,
            payload={"job_title": "Test Role"},
        )
    )
    # Consents
    await seed_default_consents(session, user=user)
    await session.commit()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, applicant, token


async def _make_recruiter_with_employer(
    session: AsyncSession,
) -> tuple[User, Employer, str]:
    user = User(email=f"rec-{uuid4().hex[:8]}@example.com", role=UserRole.RECRUITER)
    session.add(user)
    await session.flush()
    emp_name = f"Foo Inc {uuid4().hex[:6]}"
    employer = Employer(name=emp_name, name_norm=emp_name.lower())
    session.add(employer)
    await session.flush()
    link = EmployerUser(employer_id=employer.id, user_id=user.id, role="owner")
    session.add(link)
    await seed_default_consents(session, user=user)
    await session.commit()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, employer, token


@pytest.mark.asyncio
async def test_delete_wrong_confirmation_returns_400(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    _user, _applicant, token = await _make_applicant_with_dependencies(session)
    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmation": "not_the_token"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "confirmation_mismatch"


@pytest.mark.asyncio
async def test_delete_missing_confirmation_returns_422(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    _user, _applicant, token = await _make_applicant_with_dependencies(session)
    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json={},  # missing required field
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_applicant_happy_path_tombstones_and_clears(
    async_client: AsyncClient, session: AsyncSession, tmp_path
) -> None:
    user, applicant, token = await _make_applicant_with_dependencies(session)
    applicant.expected_ctc = Decimal("1500000")
    applicant.years_experience = Decimal("4.5")
    resume = Resume(
        applicant_id=applicant.id,
        original_filename="private-cv.pdf",
        content_type="application/pdf",
        storage_key=f"resumes/{uuid4()}.pdf",
        size_bytes=12,
    )
    session.add(resume)
    storage = async_client._transport.app.state.storage  # type: ignore[union-attr]
    await storage.save(
        key=resume.storage_key,
        content=b"%PDF-1.4\nx",
        content_type="application/pdf",
    )
    blob_path = tmp_path / resume.storage_key
    await session.commit()

    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["section_counts"]["notifications"] == 1
    assert body["section_counts"]["oauth_identities"] == 1
    assert body["section_counts"]["user_consents"] == 7
    assert body["section_counts"]["user_tombstoned"] == 1
    assert body["section_counts"]["applicant_tombstoned"] == 1
    assert body["section_counts"]["resumes_scrubbed"] == 1
    assert body["warnings"] == []

    # User row is tombstoned (still exists) with PII scrubbed.
    refetched_user = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refetched_user.deleted_at is not None
    assert refetched_user.email is None
    assert refetched_user.phone is None

    # Applicant row is tombstoned with PII scrubbed.
    refetched_applicant = (
        await session.execute(select(Applicant).where(Applicant.id == applicant.id))
    ).scalar_one()
    assert refetched_applicant.deleted_at is not None
    assert refetched_applicant.full_name is None
    assert refetched_applicant.expected_ctc is None
    assert refetched_applicant.years_experience is None

    refetched_resume = (
        await session.execute(select(Resume).where(Resume.id == resume.id))
    ).scalar_one()
    assert refetched_resume.deleted_at is not None
    assert refetched_resume.original_filename is None
    assert refetched_resume.storage_key is None
    assert refetched_resume.parsed_json is None
    assert not blob_path.exists()

    # Notifications + OAuth identities + consents are hard-gone.
    assert (
        await session.execute(select(Notification).where(Notification.user_id == user.id))
    ).scalars().first() is None
    assert (
        await session.execute(select(OAuthIdentity).where(OAuthIdentity.user_id == user.id))
    ).scalars().first() is None
    assert (
        await session.execute(select(UserConsent).where(UserConsent.user_id == user.id))
    ).scalars().first() is None

    # Audit rows written — both rows committed in the same transaction so
    # created_at resolution may tie; assert by action set, not position.
    audit_rows = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,
                    AuditLog.action.in_(["user.dsr_delete_requested", "user.dsr_deleted"]),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 2
    actions = {r.action for r in audit_rows}
    assert actions == {"user.dsr_delete_requested", "user.dsr_deleted"}
    deleted_row = next(r for r in audit_rows if r.action == "user.dsr_deleted")
    assert "section_counts" in deleted_row.context


@pytest.mark.asyncio
async def test_delete_erases_invites_addressed_to_the_user(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    from datetime import UTC, datetime, timedelta

    user, _applicant, token = await _make_applicant_with_dependencies(session)
    employer = Employer(name="Inviter Co", name_norm="inviter co")
    session.add(employer)
    await session.flush()
    # A pending invite addressed to this user's email — their PII.
    invite = EmployerInvite(
        employer_id=employer.id,
        email=user.email,
        role="member",
        status=EmployerInviteStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(days=14),
    )
    session.add(invite)
    await session.commit()
    invite_id = invite.id

    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp.status_code == 200
    assert resp.json()["section_counts"]["employer_invites"] == 1
    gone = (
        await session.execute(select(EmployerInvite).where(EmployerInvite.id == invite_id))
    ).scalar_one_or_none()
    assert gone is None


@pytest.mark.asyncio
async def test_recruiter_sole_owner_employer_warning(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, employer, token = await _make_recruiter_with_employer(session)

    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["warnings"]) == 1
    w = body["warnings"][0]
    assert w["type"] == "ownerless_employer"
    assert w["employer_id"] == str(employer.id)
    assert w["employer_name"] == employer.name

    # Employer row survives.
    refetched_employer = (
        await session.execute(select(Employer).where(Employer.id == employer.id))
    ).scalar_one()
    assert refetched_employer.deleted_at is None
    # employer_users membership for the recruiter is hard-gone.
    assert (
        await session.execute(select(EmployerUser).where(EmployerUser.user_id == user.id))
    ).scalars().first() is None


@pytest.mark.asyncio
async def test_application_survives_anonymized(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user, applicant, token = await _make_applicant_with_dependencies(session)
    # Set up an employer + job + application so we can observe survival.
    emp_name = f"E-{uuid4().hex[:6]}"
    employer = Employer(name=emp_name, name_norm=emp_name.lower())
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Senior Role",
        description="Desc.",
        locations=["Remote"],
        status=JobStatus.OPEN,
        min_exp_years=3,
        max_exp_years=8,
    )
    session.add(job)
    await session.flush()
    application = Application(
        applicant_id=applicant.id,
        job_id=job.id,
        status=ApplicationStatus.APPLIED,
        source="feed",
    )
    session.add(application)
    await session.commit()

    resp = await async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {token}"},
        json=_CONFIRMATION,
    )
    assert resp.status_code == 200

    # Application row still exists; applicant_id still references the
    # (now-tombstoned) applicant.
    refetched_app = (
        await session.execute(select(Application).where(Application.id == application.id))
    ).scalar_one()
    assert refetched_app.applicant_id == applicant.id

    # And the applicant tombstone has no PII.
    refetched_applicant = (
        await session.execute(select(Applicant).where(Applicant.id == applicant.id))
    ).scalar_one()
    assert refetched_applicant.full_name is None


@pytest.mark.asyncio
async def test_subsequent_request_returns_401(
    concurrent_async_client: AsyncClient, google_verifier: FakeGoogleIdTokenVerifier
) -> None:
    """After a successful DSR delete, the same JWT becomes invalid.

    Uses concurrent_async_client (real pool, no shared session override) so
    each request gets a fresh DB connection and current_user sees the committed
    tombstone on the second call — not the stale identity-map value that the
    shared session fixture would return.
    """
    tok = f"dsr-idem-{uuid4().hex[:8]}"
    google_verifier.canned[tok] = GoogleClaims(
        sub=f"sub-{uuid4().hex}",
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=f"idem-{uuid4().hex[:8]}@example.com",
        email_verified=True,
        name="Idem User",
    )
    sign_in = await concurrent_async_client.post("/v1/auth/oauth/google", json={"id_token": tok})
    assert sign_in.status_code == 200
    access_token = sign_in.json()["access_token"]

    # First delete succeeds.
    resp1 = await concurrent_async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {access_token}"},
        json=_CONFIRMATION,
    )
    assert resp1.status_code == 200

    # Second request with the same token → 401 (user_not_found via current_user
    # refetch since deleted_at is now set).
    resp2 = await concurrent_async_client.request(
        "DELETE",
        "/v1/me/dsr",
        headers={"Authorization": f"Bearer {access_token}"},
        json=_CONFIRMATION,
    )
    assert resp2.status_code == 401
