"""Full upload → parse round trip via Celery eager mode.

These tests use a standalone async_client fixture that does NOT override
get_session.  The route therefore uses its own DB sessions that commit fully
to the real DB, which means the worker (running in a thread under eager mode)
can see those rows via its own separate connection.  Cleanup is done manually
at the end of each test via a direct engine query.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fpdf import FPDF
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from jobify.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole
from jobify_api.auth.tokens import mint_access_token
from tests.integration.outbox_helpers import drain_outbox_eager

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set by pipeline_client


def _tiny_pdf_with(text_lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text_lines:
        pdf.cell(text=line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


@pytest_asyncio.fixture
async def pipeline_client(
    migrated_db: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client where the app uses its own DB sessions (no override).

    This allows the upload route's commit to reach the real DB so the worker
    thread (Celery eager mode) can read the row via its own connection.
    Isolation is achieved by cleaning up test rows after each test.
    """
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", migrated_db)
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("JOBIFY_JWT_SECRET", _JWT_SECRET)

    import jobify_worker.celery_app as _celery_mod
    import jobify_worker.worker_app  # noqa: F401  — registers tasks onto celery_app
    from jobify_api.app_factory import create_app
    from jobify_worker.celery_app import celery_app

    app = create_app()

    # Patch eager mode on the already-imported celery_app instance.

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    # Patch the module-level `settings` so the worker's LocalFileStorage points
    # to this test's tmp_path instead of whatever path was set when the module
    # was first imported.
    monkeypatch.setattr(_celery_mod.settings, "storage_root", tmp_path)

    async def _drain_after_upload(response: httpx.Response) -> None:
        if response.status_code == 201 and response.request.url.path.endswith("/resumes"):
            await drain_outbox_eager(migrated_db, app.state.storage)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
        event_hooks={"response": [_drain_after_upload]},
    ) as ac:
        yield ac

    # Reset the worker's cached sessionmaker so subsequent tests with different
    # DB URLs don't silently reuse this one.
    _celery_mod._engine = None
    _celery_mod._sessionmaker = None


async def _make_applicant_direct(db_url: str, *, email: str) -> tuple[str, str]:
    """Create user + applicant rows via a committed transaction.

    Returns (applicant_id, access_token). The token is minted directly using
    the same secret that pipeline_client sets via JOBIFY_JWT_SECRET, so the
    app under test will accept it.
    """
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            user = User(email=email, role=UserRole.APPLICANT)
            s.add(user)
            await s.flush()
            applicant = Applicant(user_id=user.id, full_name="Pipeline Test")
            s.add(applicant)
            await s.commit()
            token = mint_access_token(
                user_id=user.id,
                role=user.role.value,
                secret=_JWT_SECRET,
                ttl_seconds=600,
            )
            return str(applicant.id), token
    finally:
        await engine.dispose()


async def _get_resume_row(db_url: str, resume_id: str) -> Resume:
    """Fetch a resume row via a fresh committed read."""
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            return (await s.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
    finally:
        await engine.dispose()


async def _cleanup(db_url: str, *, emails: list[str]) -> None:
    """Remove test rows for cleanup (cascade deletes resumes via FK)."""
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            await s.execute(delete(User).where(User.email.in_(emails)))
            await s.commit()
    finally:
        await engine.dispose()


async def test_upload_then_parse_populates_parsed_json(
    pipeline_client: httpx.AsyncClient,
    migrated_db: str,
    patched_embedding_provider,
) -> None:
    """Eager mode: .delay() runs the task body inline; by the time the response
    returns, the row is already parsed."""
    email = "pipeline-happy@ex.com"
    applicant_id, access = await _make_applicant_direct(migrated_db, email=email)
    pdf = _tiny_pdf_with(
        [
            "John Doe",
            "Email: john.doe@example.com",
            "Phone: +91-98765-43210",
            "Skills: Python, FastAPI, Postgres",
        ]
    )

    try:
        resp = await pipeline_client.post(
            "/v1/applicants/me/resumes",
            files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert resp.status_code == 201
        resume_id = resp.json()["id"]

        row = await _get_resume_row(migrated_db, resume_id)
        assert (
            row.parse_status == ResumeParseStatus.PARSED
        ), f"expected parsed, got {row.parse_status}; parse_error={row.parse_error}"
        assert row.parsed_json is not None
        assert row.parsed_json["parser_name"] == "library.v1"
        assert row.parsed_json["schema_version"] == 1
        assert row.parsed_json["email"] == "john.doe@example.com"
        assert "python" in row.parsed_json["skills"]
        assert "fastapi" in row.parsed_json["skills"]

        # Verify that the embed worker also ran eagerly and wrote an
        # applicant_embeddings row. pipeline_client uses its own DB pool so
        # we verify via a raw SQL query on a fresh engine.
        from sqlalchemy import text as sql_text
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool

        verify_engine = create_async_engine(migrated_db, poolclass=NullPool)
        try:
            async with verify_engine.connect() as conn:
                result = await conn.execute(
                    sql_text(
                        "SELECT model_name, array_length(embedding::real[], 1) "
                        "FROM jobify.applicant_embeddings WHERE applicant_id = :aid"
                    ),
                    {"aid": applicant_id},
                )
                emb_row = result.first()
        finally:
            await verify_engine.dispose()

        assert emb_row is not None, "no applicant_embeddings row after eager parse+embed"
        assert emb_row[0] == "fake-test-model"
        assert emb_row[1] == 1536
    finally:
        await _cleanup(migrated_db, emails=[email])


async def test_upload_of_unsupported_blob_is_rejected(
    pipeline_client: httpx.AsyncClient,
    migrated_db: str,
) -> None:
    """Upload a .docx content-type with random bytes; the route rejects
    obvious content-type spoofing before storing a resume row."""
    email = "pipeline-failed@ex.com"
    applicant_id, access = await _make_applicant_direct(migrated_db, email=email)
    junk = b"\x00" * 200

    try:
        resp = await pipeline_client.post(
            "/v1/applicants/me/resumes",
            files={
                "file": (
                    "cv.docx",
                    io.BytesIO(junk),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"Authorization": f"Bearer {access}"},
        )
        assert resp.status_code == 415
        assert resp.json()["detail"] == "file content does not match declared resume content_type"
    finally:
        await _cleanup(migrated_db, emails=[email])
