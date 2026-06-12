"""Integration tests for R4 employer team management (members + invites).

Covers spec §7.1: owner/member RBAC, role flips derived from membership,
invite create/list/revoke + invitee accept/decline, lazy expiry, and audit rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.auth.tokens import mint_access_token
from jobify.db.models import (
    Applicant,
    AuditLog,
    EmployerInvite,
    EmployerInviteStatus,
    EmployerUser,
    Notification,
    User,
    UserRole,
)

pytestmark = pytest.mark.integration


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_owner(async_client: AsyncClient, token: str) -> str:
    """Create an employer as the token's user (flips them to recruiter+owner)."""
    r = await async_client.post(
        "/v1/employers",
        json={"name": f"Acme {uuid4().hex[:6]}"},
        headers=_h(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _make_user(
    session: AsyncSession,
    *,
    email: str | None = None,
    role: UserRole = UserRole.APPLICANT,
    full_name: str | None = "Pat Example",
) -> tuple[User, str]:
    email = email or f"u-{uuid4().hex[:8]}@example.com"
    user = User(email=email, role=role)
    session.add(user)
    await session.flush()
    if full_name is not None:
        session.add(Applicant(user_id=user.id, full_name=full_name))
        await session.flush()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    return user, token


async def _role(session: AsyncSession, user_id) -> UserRole:
    return await session.scalar(select(User.role).where(User.id == user_id))


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


async def test_member_can_read_roster_owner_can_mutate(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    owner, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    member, member_token = await _make_user(session)
    await session.commit()

    # Owner direct-adds the member.
    add = await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": member.email, "role": "member"},
        headers=_h(owner_token),
    )
    assert add.status_code == 201, add.text

    # Member can read the roster (2 people now).
    listing = await async_client.get(f"/v1/employers/{emp_id}/members", headers=_h(member_token))
    assert listing.status_code == 200
    assert len(listing.json()) == 2

    # Member CANNOT add another member (owner-only).
    other, _ = await _make_user(session)
    await session.commit()
    forbidden = await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": other.email, "role": "member"},
        headers=_h(member_token),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "not_an_owner"


async def test_add_member_flips_applicant_to_recruiter_and_audits(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    owner, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    member, _ = await _make_user(session)
    await session.commit()
    assert await _role(session, member.id) == UserRole.APPLICANT

    add = await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": member.email, "role": "member"},
        headers=_h(owner_token),
    )
    assert add.status_code == 201
    assert add.json()["display_name"] == "Pat Example"
    assert await _role(session, member.id) == UserRole.RECRUITER

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "employer.member_added",
                    AuditLog.actor_user_id == owner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].context["target_user_id"] == str(member.id)


async def test_add_member_unknown_email_404(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    r = await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": "nobody@example.com", "role": "member"},
        headers=_h(owner_token),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "user_not_found"


async def test_add_member_already_member_409(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    member, _ = await _make_user(session)
    await session.commit()
    body = {"email": member.email, "role": "member"}
    first = await async_client.post(
        f"/v1/employers/{emp_id}/members", json=body, headers=_h(owner_token)
    )
    assert first.status_code == 201
    dup = await async_client.post(
        f"/v1/employers/{emp_id}/members", json=body, headers=_h(owner_token)
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "already_a_member"


async def test_demote_sole_owner_blocked(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    owner, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    r = await async_client.patch(
        f"/v1/employers/{emp_id}/members/{owner.id}",
        json={"role": "member"},
        headers=_h(owner_token),
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "last_owner"


async def test_promote_member_then_demote_original_owner(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    owner, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    member, _ = await _make_user(session)
    await session.commit()
    await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": member.email, "role": "member"},
        headers=_h(owner_token),
    )
    # Promote member → owner (now two owners).
    promote = await async_client.patch(
        f"/v1/employers/{emp_id}/members/{member.id}",
        json={"role": "owner"},
        headers=_h(owner_token),
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == "owner"
    # Now demoting the original owner is allowed (a second owner remains).
    demote = await async_client.patch(
        f"/v1/employers/{emp_id}/members/{owner.id}",
        json={"role": "member"},
        headers=_h(owner_token),
    )
    assert demote.status_code == 200


async def test_remove_member_demotes_to_applicant(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    member, _ = await _make_user(session)
    await session.commit()
    await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": member.email, "role": "member"},
        headers=_h(owner_token),
    )
    assert await _role(session, member.id) == UserRole.RECRUITER

    rm = await async_client.delete(
        f"/v1/employers/{emp_id}/members/{member.id}", headers=_h(owner_token)
    )
    assert rm.status_code == 204
    assert await _role(session, member.id) == UserRole.APPLICANT

    audit = (
        await session.execute(select(AuditLog).where(AuditLog.action == "employer.member_removed"))
    ).scalar_one()
    assert audit.context["demoted_to_applicant"] is True


async def test_remove_last_owner_blocked(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    owner, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    r = await async_client.delete(
        f"/v1/employers/{emp_id}/members/{owner.id}", headers=_h(owner_token)
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "last_owner"


async def test_remove_admin_member_does_not_demote(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    admin, _ = await _make_user(session, role=UserRole.ADMIN, full_name=None)
    await session.commit()
    # Direct-add the admin as a member (flip is a no-op for ADMIN).
    await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": admin.email, "role": "member"},
        headers=_h(owner_token),
    )
    assert await _role(session, admin.id) == UserRole.ADMIN
    rm = await async_client.delete(
        f"/v1/employers/{emp_id}/members/{admin.id}", headers=_h(owner_token)
    )
    assert rm.status_code == 204
    assert await _role(session, admin.id) == UserRole.ADMIN


# ---------------------------------------------------------------------------
# Invites
# ---------------------------------------------------------------------------


async def test_create_invite_writes_outbox_for_existing_user(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    owner, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    invitee, _ = await _make_user(session)
    await session.commit()

    r = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": invitee.email, "role": "member"},
        headers=_h(owner_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"

    notes = (
        (
            await session.execute(
                select(Notification).where(
                    Notification.user_id == invitee.id,
                    Notification.kind == "employer_invite",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notes) == 1
    assert notes[0].payload["employer_id"] == emp_id

    audit = (
        await session.execute(select(AuditLog).where(AuditLog.action == "employer.invite_created"))
    ).scalar_one()
    assert audit.context["email"] == invitee.email


async def test_create_invite_unknown_email_no_outbox(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    email = f"ghost-{uuid4().hex[:8]}@example.com"
    r = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": email, "role": "member"},
        headers=_h(owner_token),
    )
    assert r.status_code == 201
    notes = (
        (await session.execute(select(Notification).where(Notification.kind == "employer_invite")))
        .scalars()
        .all()
    )
    assert notes == []


async def test_create_invite_duplicate_pending_409(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    email = f"dup-{uuid4().hex[:8]}@example.com"
    body = {"email": email, "role": "member"}
    first = await async_client.post(
        f"/v1/employers/{emp_id}/invites", json=body, headers=_h(owner_token)
    )
    assert first.status_code == 201
    dup = await async_client.post(
        f"/v1/employers/{emp_id}/invites", json=body, headers=_h(owner_token)
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "invite_already_pending"


async def test_create_invite_existing_member_409(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    member, _ = await _make_user(session)
    await session.commit()
    await async_client.post(
        f"/v1/employers/{emp_id}/members",
        json={"email": member.email, "role": "member"},
        headers=_h(owner_token),
    )
    r = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": member.email, "role": "member"},
        headers=_h(owner_token),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "already_a_member"


async def test_list_and_revoke_invite(
    async_client: AsyncClient,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    email = f"inv-{uuid4().hex[:8]}@example.com"
    created = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": email, "role": "member"},
        headers=_h(owner_token),
    )
    invite_id = created.json()["id"]

    listed = await async_client.get(f"/v1/employers/{emp_id}/invites", headers=_h(owner_token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    revoked = await async_client.delete(
        f"/v1/employers/{emp_id}/invites/{invite_id}", headers=_h(owner_token)
    )
    assert revoked.status_code == 204

    after = await async_client.get(f"/v1/employers/{emp_id}/invites", headers=_h(owner_token))
    assert after.json() == []


async def test_my_invites_email_matched_only(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    invitee, invitee_token = await _make_user(session)
    other, other_token = await _make_user(session)
    await session.commit()
    await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": invitee.email, "role": "member"},
        headers=_h(owner_token),
    )

    mine = await async_client.get("/v1/me/invites", headers=_h(invitee_token))
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    assert mine.json()[0]["employer_id"] == emp_id

    theirs = await async_client.get("/v1/me/invites", headers=_h(other_token))
    assert theirs.json() == []


async def test_accept_invite_creates_membership_and_flips(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    invitee, invitee_token = await _make_user(session)
    await session.commit()
    created = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": invitee.email, "role": "member"},
        headers=_h(owner_token),
    )
    invite_id = created.json()["id"]

    accept = await async_client.post(
        f"/v1/me/invites/{invite_id}/accept", headers=_h(invitee_token)
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["role"] == "member"
    assert await _role(session, invitee.id) == UserRole.RECRUITER

    link = await session.scalar(
        select(EmployerUser).where(
            EmployerUser.employer_id == emp_id,
            EmployerUser.user_id == invitee.id,
            EmployerUser.deleted_at.is_(None),
        )
    )
    assert link is not None

    invite = await session.get(EmployerInvite, invite_id)
    assert invite is not None
    assert invite.status == EmployerInviteStatus.ACCEPTED
    assert invite.accepted_user_id == invitee.id

    audit = (
        await session.execute(select(AuditLog).where(AuditLog.action == "employer.invite_accepted"))
    ).scalar_one()
    assert audit.context["employer_id"] == emp_id


async def test_accept_invite_wrong_user_404(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    invitee, _ = await _make_user(session)
    _, wrong_token = await _make_user(session)
    await session.commit()
    created = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": invitee.email, "role": "member"},
        headers=_h(owner_token),
    )
    invite_id = created.json()["id"]
    r = await async_client.post(f"/v1/me/invites/{invite_id}/accept", headers=_h(wrong_token))
    assert r.status_code == 404


async def test_accept_expired_invite_410(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    invitee, invitee_token = await _make_user(session)
    await session.commit()
    created = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": invitee.email, "role": "member"},
        headers=_h(owner_token),
    )
    invite_id = created.json()["id"]
    # Force expiry in the past.
    await session.execute(
        update(EmployerInvite)
        .where(EmployerInvite.id == invite_id)
        .values(expires_at=datetime.now(UTC) - timedelta(days=1))
    )
    await session.commit()

    r = await async_client.post(f"/v1/me/invites/{invite_id}/accept", headers=_h(invitee_token))
    assert r.status_code == 410
    assert r.json()["detail"] == "invite_expired"


async def test_decline_invite(
    async_client: AsyncClient,
    session: AsyncSession,
    applicant_user_and_token: tuple[User, str],
) -> None:
    _, owner_token = applicant_user_and_token
    emp_id = await _make_owner(async_client, owner_token)
    invitee, invitee_token = await _make_user(session)
    await session.commit()
    created = await async_client.post(
        f"/v1/employers/{emp_id}/invites",
        json={"email": invitee.email, "role": "member"},
        headers=_h(owner_token),
    )
    invite_id = created.json()["id"]

    decline = await async_client.post(
        f"/v1/me/invites/{invite_id}/decline", headers=_h(invitee_token)
    )
    assert decline.status_code == 200
    assert decline.json()["status"] == "revoked"

    # No membership created; invite no longer pending.
    assert await _role(session, invitee.id) == UserRole.APPLICANT
    mine = await async_client.get("/v1/me/invites", headers=_h(invitee_token))
    assert mine.json() == []
