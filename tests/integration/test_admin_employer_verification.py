"""Integration tests for /v1/admin/employers (list + verify + reject).

Mirrors the admin error-ladder: 401 (no token) → 403 not_an_admin → 404
employer_not_found. Verification tri-state is derived from verified_at /
rejected_at; verify and reject are mutually exclusive.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import AuditLog, Employer, User, UserRole
from jobify_api.auth.tokens import mint_access_token

pytestmark = pytest.mark.integration


async def _make_employer(
    session: AsyncSession,
    *,
    name: str | None = None,
    gst: str | None = "29ABCDE1234F1Z5",
) -> Employer:
    name = name or f"Org {uuid4().hex[:8]}"
    employer = Employer(name=name, name_norm=name.lower(), gst=gst)
    session.add(employer)
    await session.flush()
    return employer


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_verify_employer_happy_path(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _, token = admin_user_and_token
    employer = await _make_employer(session)
    await session.commit()

    resp = await async_client.post(
        f"/v1/admin/employers/{employer.id}/verify", headers=_auth(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "verified"
    assert body["reviewed_at"] is not None
    assert body["reason"] is None

    # verified_at is set; the trust badge derives from it.
    refreshed = await session.get(Employer, employer.id)
    assert refreshed is not None
    await session.refresh(refreshed)
    assert refreshed.verified_at is not None
    assert refreshed.rejected_at is None

    # An audit row was written.
    rows = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "admin.employer.verified",
                    AuditLog.resource_id == employer.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_reject_then_reverify_clears_each_other(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _, token = admin_user_and_token
    employer = await _make_employer(session)
    await session.commit()

    # Reject with a reason.
    resp = await async_client.post(
        f"/v1/admin/employers/{employer.id}/reject",
        headers=_auth(token),
        json={"reason": "GST mismatch"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["reason"] == "GST mismatch"

    refreshed = await session.get(Employer, employer.id)
    assert refreshed is not None
    await session.refresh(refreshed)
    assert refreshed.rejected_at is not None
    assert refreshed.verified_at is None
    assert refreshed.rejection_reason == "GST mismatch"

    # Now verify — must clear the rejection (timestamp + reason).
    resp = await async_client.post(
        f"/v1/admin/employers/{employer.id}/verify", headers=_auth(token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"

    await session.refresh(refreshed)
    assert refreshed.verified_at is not None
    assert refreshed.rejected_at is None
    assert refreshed.rejection_reason is None


@pytest.mark.asyncio
async def test_list_filters_by_status(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _, token = admin_user_and_token
    pending = await _make_employer(session, name=f"Pending {uuid4().hex[:6]}")
    verified = await _make_employer(session, name=f"Verified {uuid4().hex[:6]}")
    rejected = await _make_employer(session, name=f"Rejected {uuid4().hex[:6]}")
    await session.commit()

    await async_client.post(f"/v1/admin/employers/{verified.id}/verify", headers=_auth(token))
    await async_client.post(
        f"/v1/admin/employers/{rejected.id}/reject",
        headers=_auth(token),
        json={"reason": "incomplete"},
    )

    for status, expected_id in (
        ("pending", pending.id),
        ("verified", verified.id),
        ("rejected", rejected.id),
    ):
        resp = await async_client.get(
            "/v1/admin/employers", headers=_auth(token), params={"status": status}
        )
        assert resp.status_code == 200
        ids = {item["id"] for item in resp.json()["items"]}
        assert str(expected_id) in ids
        # rows of the other two statuses must not leak into this partition.
        other_ids = {str(pending.id), str(verified.id), str(rejected.id)} - {str(expected_id)}
        assert ids.isdisjoint(other_ids)


@pytest.mark.asyncio
async def test_list_pagination_cursor(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _, token = admin_user_and_token
    for i in range(3):
        await _make_employer(session, name=f"Paged {i}-{uuid4().hex[:6]}")
    await session.commit()

    resp = await async_client.get(
        "/v1/admin/employers", headers=_auth(token), params={"status": "pending", "limit": 2}
    )
    assert resp.status_code == 200
    page1 = resp.json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"] is not None

    resp = await async_client.get(
        "/v1/admin/employers",
        headers=_auth(token),
        params={"status": "pending", "limit": 2, "cursor": page1["next_cursor"]},
    )
    assert resp.status_code == 200
    page2 = resp.json()
    page1_ids = {i["id"] for i in page1["items"]}
    page2_ids = {i["id"] for i in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_reject_requires_reason(
    async_client: AsyncClient,
    session: AsyncSession,
    admin_user_and_token: tuple[User, str],
) -> None:
    _, token = admin_user_and_token
    employer = await _make_employer(session)
    await session.commit()

    resp = await async_client.post(
        f"/v1/admin/employers/{employer.id}/reject", headers=_auth(token), json={"reason": ""}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unknown_employer_404(
    async_client: AsyncClient,
    admin_user_and_token: tuple[User, str],
) -> None:
    _, token = admin_user_and_token
    resp = await async_client.post(f"/v1/admin/employers/{uuid4()}/verify", headers=_auth(token))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "employer_not_found"


@pytest.mark.asyncio
async def test_non_admin_forbidden(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    recruiter = User(email=f"rec-{uuid4().hex[:8]}@example.com", role=UserRole.RECRUITER)
    session.add(recruiter)
    await session.flush()
    employer = await _make_employer(session)
    await session.commit()
    token = mint_access_token(
        user_id=recruiter.id, role=recruiter.role.value, secret="x" * 32, ttl_seconds=600
    )

    for method, path, json in (
        ("get", "/v1/admin/employers", None),
        ("post", f"/v1/admin/employers/{employer.id}/verify", None),
        ("post", f"/v1/admin/employers/{employer.id}/reject", {"reason": "no"}),
    ):
        resp = await async_client.request(method, path, headers=_auth(token), json=json)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "not_an_admin"


@pytest.mark.asyncio
async def test_missing_token_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/v1/admin/employers")
    assert resp.status_code == 401
