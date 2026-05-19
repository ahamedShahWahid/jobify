"""POST + GET /v1/applicants/me/resumes — upload + persistence (auth-required)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.google_verifier import GoogleClaims
from kpa.db.models import Resume, ResumeParseStatus

_TINY_PDF = b"%PDF-1.4\n%minimal\n"


def _claims(sub: str, email: str) -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=True,
        name=email.split("@", 1)[0].title(),
    )


async def _signin_as_applicant(
    client: httpx.AsyncClient,
    google_verifier,  # FakeGoogleIdTokenVerifier
    *,
    sub: str | None = None,
    email: str | None = None,
) -> tuple[str, str]:
    """Sign in via the fake Google verifier; return (applicant_id, access_token).

    Each call uses a unique sub/email by default so multiple applicants in
    one test don't collide on the partial-unique email index.
    """
    sub = sub or f"google-sub-{uuid.uuid4()}"
    email = email or f"applicant-{uuid.uuid4()}@example.com"
    token = f"tok-{uuid.uuid4()}"

    google_verifier.canned[token] = _claims(sub=sub, email=email)
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["user"]["applicant_id"], body["access_token"]


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.integration
async def test_upload_resume_happy_path(
    async_client: httpx.AsyncClient,
    google_verifier,
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    applicant_id, access = await _signin_as_applicant(async_client, google_verifier)

    response = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(access),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["applicant_id"] == applicant_id
    assert body["original_filename"] == "cv.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(_TINY_PDF)
    assert body["parse_status"] == "pending"

    resume_id = uuid.UUID(body["id"])
    row = (await session.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
    assert row.parse_status is ResumeParseStatus.PENDING

    on_disk = tmp_path / row.storage_key
    assert on_disk.is_file()
    assert on_disk.read_bytes() == _TINY_PDF


@pytest.mark.integration
async def test_upload_resume_rejects_disallowed_content_type(
    async_client: httpx.AsyncClient,
    google_verifier,
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    applicant_id, access = await _signin_as_applicant(async_client, google_verifier)

    response = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=_auth(access),
    )

    assert response.status_code == 415
    # No row persisted for this applicant, no file written by this test.
    rows = (
        await session.execute(select(Resume).where(Resume.applicant_id == uuid.UUID(applicant_id)))
    ).all()
    assert rows == []
    assert not any(tmp_path.rglob("*"))


@pytest.mark.integration
async def test_upload_resume_rejects_oversized_payload(
    async_client: httpx.AsyncClient,
    google_verifier,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
    tmp_path: Path,
) -> None:
    """Use a low cap so we don't allocate real 10 MB blobs in tests."""
    # Sign in against the suite's default app first to get a token bound to a
    # real applicant row in `session`.
    applicant_id, access = await _signin_as_applicant(async_client, google_verifier)

    # Re-create the app with a stricter KPA_MAX_UPLOAD_BYTES, sharing `session`
    # so the user we just signed in as is visible.
    monkeypatch.setenv("KPA_MAX_UPLOAD_BYTES", "16")  # 16 bytes
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:  # type: ignore[return]
        yield session

    app.dependency_overrides[get_session] = _shared_session

    payload = b"x" * 32  # over 16 bytes

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        response = await c.post(
            "/v1/applicants/me/resumes",
            files={"file": ("cv.pdf", payload, "application/pdf")},
            headers=_auth(access),
        )

    assert response.status_code == 413
    rows = (
        await session.execute(select(Resume).where(Resume.applicant_id == uuid.UUID(applicant_id)))
    ).all()
    assert rows == []


@pytest.mark.integration
async def test_get_resume_returns_metadata(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    _applicant_id, access = await _signin_as_applicant(async_client, google_verifier)
    post = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(access),
    )
    assert post.status_code == 201, post.text
    posted = post.json()

    response = await async_client.get(
        f"/v1/applicants/me/resumes/{posted['id']}",
        headers=_auth(access),
    )

    assert response.status_code == 200
    assert response.json() == posted


@pytest.mark.integration
async def test_get_resume_unknown_id_returns_404(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    _applicant_id, access = await _signin_as_applicant(async_client, google_verifier)
    bogus = uuid.uuid4()

    response = await async_client.get(
        f"/v1/applicants/me/resumes/{bogus}",
        headers=_auth(access),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "resume not found"


@pytest.mark.integration
async def test_get_resume_belonging_to_other_user_returns_404(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    """A resume id owned by user B must 404 when user A asks for it.

    Returning 403 would leak the existence of the resume to an unauthorized
    caller; 404 keeps the surface flat.
    """
    _owner_id, owner_access = await _signin_as_applicant(async_client, google_verifier)
    _intruder_id, intruder_access = await _signin_as_applicant(async_client, google_verifier)

    post = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(owner_access),
    )
    posted = post.json()

    response = await async_client.get(
        f"/v1/applicants/me/resumes/{posted['id']}",
        headers=_auth(intruder_access),
    )

    assert response.status_code == 404


@pytest.mark.integration
async def test_get_resume_404_detail_is_uniform(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    """Both 404 cases (unknown id; another user's id) return the same detail.

    Distinguishing them would leak which case the caller hit — i.e., whether
    a resume id exists at all.
    """
    _user_a_id, access_a = await _signin_as_applicant(async_client, google_verifier)
    _user_b_id, access_b = await _signin_as_applicant(async_client, google_verifier)

    # User B uploads a resume; user A queries that real id and a bogus one.
    post = await async_client.post(
        "/v1/applicants/me/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
        headers=_auth(access_b),
    )
    real_resume_id = post.json()["id"]
    bogus = uuid.uuid4()

    cases = [
        f"/v1/applicants/me/resumes/{bogus}",
        f"/v1/applicants/me/resumes/{real_resume_id}",
    ]
    details = []
    for url in cases:
        response = await async_client.get(url, headers=_auth(access_a))
        assert response.status_code == 404, url
        details.append(response.json().get("detail"))

    assert len(set(details)) == 1, f"detail messages leak info: {details}"
    assert details[0] == "resume not found", f"unexpected canonical detail: {details[0]!r}"
