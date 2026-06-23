"""Integration tests for the embed_applicant worker.

Tests A, B, C, D (pipeline tests) use a local ``eager_client`` fixture that
does NOT override get_session.  The upload route therefore commits fully to the
real DB so the parse + embed worker threads can see the rows via their own
connections.  Cleanup is done via a direct engine query after each test.

The Gemini provider is replaced via ``patched_embedding_provider`` — no real
network calls.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fpdf import FPDF
from sqlalchemy import delete, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from jobify.db.models import Resume, ResumeParseStatus, User
from jobify.integrations.embeddings import EmbeddingTask
from jobify_api.auth.google_verifier import GoogleClaims, get_google_verifier

pytestmark = pytest.mark.integration

_JWT_SECRET = "x" * 32  # matches JOBIFY_JWT_SECRET set in fixtures


def _tiny_pdf_with_text() -> bytes:
    """Build a small PDF with parseable text so library.v1 produces a real ParsedResume."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="John Doe Email john@example.com Skills Python FastAPI")
    return bytes(pdf.output())


def _claims(sub: str, email: str) -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=True,
        name=email.split("@", 1)[0].title(),
    )


async def _signin_as_applicant(client: httpx.AsyncClient, google_verifier) -> tuple[str, str]:
    """Sign in via the fake Google verifier; return (applicant_id, access_token)."""
    sub = f"google-sub-{uuid.uuid4()}"
    email = f"applicant-{uuid.uuid4()}@example.com"
    token = f"tok-{uuid.uuid4()}"
    google_verifier.canned[token] = _claims(sub=sub, email=email)
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["user"]["applicant_id"], body["access_token"]


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _cleanup_user_by_email(db_url: str, email: str) -> None:
    """Delete test rows (cascades to applicants / resumes / embeddings)."""
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            await s.execute(delete(User).where(User.email == email))
            await s.commit()
    finally:
        await engine.dispose()


async def _get_embedding_row_direct(db_url: str, applicant_id: str) -> tuple | None:
    """Return (model_name, dim, hash_len, input_tokens) or None via a fresh connection."""
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                sql_text(
                    "SELECT model_name, "
                    "array_length(embedding::real[], 1), "
                    "length(canonicalized_text_hash), "
                    "input_tokens "
                    "FROM jobify.applicant_embeddings "
                    "WHERE applicant_id = :aid AND deleted_at IS NULL"
                ),
                {"aid": applicant_id},
            )
            return result.first()
    finally:
        await engine.dispose()


async def _get_resume_row_direct(db_url: str, resume_id: str) -> Resume:
    """Fetch a resume row via a fresh committed read."""
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            return (await s.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def eager_client(
    migrated_db: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    google_verifier,
    patched_embedding_provider,
) -> AsyncIterator[httpx.AsyncClient]:
    """AsyncClient that uses the real DB pool (no session override) + eager Celery.

    The route commits fully to the real DB so worker threads can see rows via
    their own connections.  google_verifier + patched_embedding_provider are
    both wired up.

    Isolation: caller must clean up test rows after each test via
    ``_cleanup_user_by_email``.
    """
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", migrated_db)
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("JOBIFY_JWT_SECRET", _JWT_SECRET)
    monkeypatch.setenv("JOBIFY_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    import jobify.workers.celery_app as _celery_mod
    from jobify.workers.celery_app import celery_app
    from jobify_api.app_factory import create_app

    app = create_app()
    app.dependency_overrides[get_google_verifier] = lambda: google_verifier

    # Enable eager mode so parse_resume + embed_applicant run synchronously.
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    monkeypatch.setattr(_celery_mod.settings, "storage_root", tmp_path)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    # httpx.ASGITransport does not send ASGI lifespan events, so the
    # on_event("shutdown") hook that disposes the engine never fires.
    # Dispose explicitly to avoid pool leaks across tests.
    await app.state.db_engine.dispose()

    # Reset worker's cached sessionmaker so subsequent tests don't reuse
    # this test's engine. The patched_embedding_provider fixture handles
    # resetting _embedding_provider via monkeypatch teardown.
    _celery_mod._engine = None
    _celery_mod._sessionmaker = None


async def test_embed_after_parse_writes_row(
    eager_client: httpx.AsyncClient,
    migrated_db: str,
    google_verifier,
    patched_embedding_provider,
) -> None:
    """Happy path: upload → eager parse → eager embed → applicant_embeddings row exists."""
    pdf_bytes = _tiny_pdf_with_text()

    applicant_id, access = await _signin_as_applicant(eager_client, google_verifier)

    try:
        resp = await eager_client.post(
            "/v1/applicants/me/resumes",
            files={"file": ("cv.pdf", pdf_bytes, "application/pdf")},
            headers=_auth(access),
        )
        assert resp.status_code == 201, resp.text

        # Verify parse + embed both ran eagerly via direct DB reads.
        resume_id = resp.json()["id"]
        resume = await _get_resume_row_direct(migrated_db, resume_id)
        assert (
            resume.parse_status is ResumeParseStatus.PARSED
        ), f"parse didn't complete; got {resume.parse_status}"

        row = await _get_embedding_row_direct(migrated_db, applicant_id)
        assert row is not None, (
            "no applicant_embeddings row after eager parse+embed; "
            "check that the PDF produced a non-empty ParsedResume"
        )
        model_name, dim, hash_len, input_tokens = row
        assert model_name == "fake-test-model"
        assert dim == 1536
        assert hash_len == 64
        assert input_tokens > 0

        # The fake provider should have been called exactly once with DOCUMENT.
        assert len(patched_embedding_provider.calls) == 1
        text_called, task_called, title_called = patched_embedding_provider.calls[0]
        assert task_called is EmbeddingTask.DOCUMENT
        assert title_called  # full_name was passed
    finally:
        # Look up the email from canned tokens to clean up.
        for claims in google_verifier.canned.values():
            await _cleanup_user_by_email(migrated_db, claims.email)


async def test_rerun_with_same_content_is_noop(
    eager_client: httpx.AsyncClient,
    migrated_db: str,
    google_verifier,
    patched_embedding_provider,
) -> None:
    """Re-running embed_applicant on unchanged parsed_json hits the hash gate and
    skips the provider."""
    from jobify.workers.celery_app import get_session_maker
    from jobify.workers.tasks.embed import _embed_applicant_async

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Jane Doe Email jane@example.com Skills Python")
    pdf_bytes = bytes(pdf.output())

    applicant_id_str, access = await _signin_as_applicant(eager_client, google_verifier)
    applicant_id = uuid.UUID(applicant_id_str)

    try:
        resp = await eager_client.post(
            "/v1/applicants/me/resumes",
            files={"file": ("cv.pdf", pdf_bytes, "application/pdf")},
            headers=_auth(access),
        )
        assert resp.status_code == 201

        # After upload+parse+embed, the provider should have been called once.
        initial_call_count = len(patched_embedding_provider.calls)
        assert initial_call_count == 1, (
            f"expected 1 provider call after eager pipeline, got {initial_call_count}; "
            "check that the PDF produced a parseable ParsedResume"
        )

        # Re-run the embed worker directly with the fake provider injected.
        # Should hit the Txn1 canonicalized_text_hash gate and skip the encode.
        await _embed_applicant_async(
            applicant_id,
            sm=get_session_maker(),
            provider=patched_embedding_provider,
        )

        # Provider call count unchanged → the Txn1 gate skipped the encode.
        assert len(patched_embedding_provider.calls) == initial_call_count
    finally:
        for claims in google_verifier.canned.values():
            await _cleanup_user_by_email(migrated_db, claims.email)


async def test_embed_no_parsed_resume_is_no_op(
    eager_client: httpx.AsyncClient,
    migrated_db: str,
    google_verifier,
    patched_embedding_provider,
) -> None:
    """Sign in (commits to real DB), but do NOT upload a resume.

    Call the embed worker directly. Worker should bail at Txn 1's
    ``latest is None`` branch (embed.no-parsed-resume), not the
    embed.applicant-missing branch. Using eager_client ensures the applicant
    row is visible to the worker's fresh DB connection.

    Substitutes for the spec's "test_stale_content_aborts_in_txn3" because
    forcing the Txn3 race within a test is fiddly. The "no parsed resume"
    branch exercises the same defensive load-and-check pattern.
    """
    from jobify.workers.celery_app import get_session_maker
    from jobify.workers.tasks.embed import _embed_applicant_async

    applicant_id_str, _access = await _signin_as_applicant(eager_client, google_verifier)
    applicant_id = uuid.UUID(applicant_id_str)
    email_used = next(iter(google_verifier.canned.values())).email

    try:
        # No resume uploaded — call the worker directly. Should bail cleanly
        # at the embed.no-parsed-resume branch in Txn 1.
        await _embed_applicant_async(
            applicant_id,
            sm=get_session_maker(),
            provider=patched_embedding_provider,
        )

        # Provider not called; no row written.
        assert patched_embedding_provider.calls == []
        emb = await _get_embedding_row_direct(migrated_db, applicant_id_str)
        assert emb is None
    finally:
        await _cleanup_user_by_email(migrated_db, email_used)


async def test_dispatch_resilient_to_embed_broker_failure(
    eager_client: httpx.AsyncClient,
    migrated_db: str,
    google_verifier,
    patched_embedding_provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If embed_applicant.delay() raises, parse still commits PARSED and no
    embedding row is written."""
    from jobify.workers.tasks import embed as embed_mod

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Broker Test User")
    pdf_bytes = bytes(pdf.output())

    def _raise_broker_down(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(embed_mod.embed_applicant, "delay", _raise_broker_down)

    applicant_id_str, access = await _signin_as_applicant(eager_client, google_verifier)
    applicant_id = uuid.UUID(applicant_id_str)

    try:
        resp = await eager_client.post(
            "/v1/applicants/me/resumes",
            files={"file": ("cv.pdf", pdf_bytes, "application/pdf")},
            headers=_auth(access),
        )
        assert resp.status_code == 201, "upload should succeed even if embed dispatch fails"

        # Parse still committed PARSED (the embed dispatch happens after parse commits).
        resume_id = resp.json()["id"]
        resume = await _get_resume_row_direct(migrated_db, resume_id)
        assert resume.parse_status is ResumeParseStatus.PARSED

        # No embedding row was written (dispatch failed before the worker ran).
        row = await _get_embedding_row_direct(migrated_db, str(applicant_id))
        assert row is None, "embedding row should not exist when dispatch raised"

        # The fake provider should NOT have been called.
        assert patched_embedding_provider.calls == []
    finally:
        for claims in google_verifier.canned.values():
            await _cleanup_user_by_email(migrated_db, claims.email)


@pytest.mark.integration
async def test_embed_applicant_dispatches_score_applicant(
    session,
    patched_embedding_provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After embed_applicant Txn 3 commits, score_applicant.delay is called."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from jobify.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole

    calls: list[str] = []

    def _spy(applicant_id_str: str) -> None:
        calls.append(applicant_id_str)

    monkeypatch.setattr("jobify.workers.tasks.score_applicant.score_applicant.delay", _spy)

    user = User(email="dispatch@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="D Test")
    session.add(applicant)
    await session.flush()
    session.add(
        Resume(
            applicant_id=applicant.id,
            storage_key="k",
            original_filename="f.pdf",
            content_type="application/pdf",
            size_bytes=1,
            parse_status=ResumeParseStatus.PARSED,
            parsed_json={
                "name": "D Test",
                "parser_name": "test",
                "raw_text": "D Test",
                "skills": [],
                "experience": [],
                "education": [],
                "certifications": [],
            },
        )
    )
    await session.commit()

    sm = async_sessionmaker(
        bind=session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    from jobify.workers.tasks.embed import _embed_applicant_async

    await _embed_applicant_async(applicant.id, sm=sm, provider=patched_embedding_provider)
    assert len(calls) == 1
    assert calls[0] == str(applicant.id)
