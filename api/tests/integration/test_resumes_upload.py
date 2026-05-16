"""POST /v1/applicants/{applicant_id}/resumes — upload + persistence."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
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
    async_client: httpx.AsyncClient, session: AsyncSession, tmp_path: Path
) -> None:
    applicant = await _make_applicant(session)

    response = await async_client.post(
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
    row = (await session.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
    assert row.parse_status is ResumeParseStatus.PENDING

    on_disk = tmp_path / row.storage_key
    assert on_disk.is_file()
    assert on_disk.read_bytes() == _TINY_PDF


@pytest.mark.integration
async def test_upload_resume_unknown_applicant_returns_404(
    async_client: httpx.AsyncClient,
) -> None:
    bogus = uuid.uuid4()

    response = await async_client.post(
        f"/v1/applicants/{bogus}/resumes",
        files={"file": ("cv.pdf", _TINY_PDF, "application/pdf")},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.integration
async def test_upload_resume_rejects_disallowed_content_type(
    async_client: httpx.AsyncClient, session: AsyncSession, tmp_path: Path
) -> None:
    applicant = await _make_applicant(session)

    response = await async_client.post(
        f"/v1/applicants/{applicant.id}/resumes",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    # No row persisted, no file written.
    rows = (await session.execute(select(Resume).where(Resume.applicant_id == applicant.id))).all()
    assert rows == []
    assert not any(tmp_path.rglob("*"))


@pytest.mark.integration
async def test_upload_resume_rejects_oversized_payload(
    async_client: httpx.AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
    tmp_path: Path,
) -> None:
    """Use a low cap so we don't allocate real 10 MB blobs in tests."""
    # Re-create the app with a stricter KPA_MAX_UPLOAD_BYTES.
    monkeypatch.setenv("KPA_MAX_UPLOAD_BYTES", "16")  # 16 bytes
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", db_url)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:  # type: ignore[return]
        yield session

    app.dependency_overrides[get_session] = _shared_session
    applicant = await _make_applicant(session)

    payload = b"x" * 32  # over 16 bytes

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        response = await c.post(
            f"/v1/applicants/{applicant.id}/resumes",
            files={"file": ("cv.pdf", payload, "application/pdf")},
        )

    assert response.status_code == 413
    rows = (await session.execute(select(Resume).where(Resume.applicant_id == applicant.id))).all()
    assert rows == []
