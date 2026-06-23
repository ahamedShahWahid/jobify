"""Unit tests for the parse task body — direct calls to _parse_resume_async with
mocked storage + an in-memory sessionmaker. No Redis, no real Celery dispatch."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from jobify.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole
from jobify.integrations.parser.base import (
    ParsedResume,
    ParserError,
    TransientParserError,
)
from jobify_worker.tasks.parse import _parse_resume_async

pytestmark = pytest.mark.integration  # uses local Postgres for the session


@pytest_asyncio.fixture
async def sm(migrated_db: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Per-test sessionmaker. Consumes `migrated_db` so Alembic head is applied."""
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _make_resume_row(
    sm: async_sessionmaker[AsyncSession],
    *,
    status: ResumeParseStatus = ResumeParseStatus.PENDING,
) -> UUID:
    """Create a user + applicant + resume row; return resume id."""
    async with sm() as session:
        user = User(email=f"{uuid4()}@ex.com", role=UserRole.APPLICANT)
        session.add(user)
        await session.flush()
        applicant = Applicant(user_id=user.id, full_name="Test")
        session.add(applicant)
        await session.flush()
        resume = Resume(
            applicant_id=applicant.id,
            storage_key=f"resumes/{uuid4()}.pdf",
            original_filename="cv.pdf",
            content_type="application/pdf",
            size_bytes=100,
            parse_status=status,
        )
        session.add(resume)
        await session.commit()
        return resume.id


class _FakeStorage:
    """Returns canned bytes regardless of key."""

    def __init__(self, content: bytes = b"PDFBYTES") -> None:
        self.content = content
        self.read_calls = 0

    async def read(self, key: str) -> bytes:
        self.read_calls += 1
        return self.content

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass


class _FakeParser:
    """Returns a canned ParsedResume."""

    def __init__(self, result: ParsedResume) -> None:
        self.result = result
        self.parse_calls = 0

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        self.parse_calls += 1
        return self.result


class _RaisingParser:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        raise self.exc


async def test_parse_happy_path_persists_parsed_json(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    resume_id = await _make_resume_row(sm)
    storage = _FakeStorage()
    parser = _FakeParser(ParsedResume(parser_name="library.v1", raw_text="hello", email="a@b.com"))

    await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.PARSED
        assert row.parsed_json is not None
        assert row.parsed_json["email"] == "a@b.com"
        assert row.parsed_json["parser_name"] == "library.v1"
        assert row.parse_error is None
    assert storage.read_calls == 1
    assert parser.parse_calls == 1


async def test_parse_parser_error_marks_failed_no_retry(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    resume_id = await _make_resume_row(sm)
    storage = _FakeStorage()
    parser = _RaisingParser(ParserError("password_protected"))

    # ParserError doesn't propagate — task handles it by marking failed.
    await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.FAILED
        assert row.parse_error == "password_protected"


async def test_parse_transient_error_propagates_for_celery_retry(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    resume_id = await _make_resume_row(sm)
    storage = _FakeStorage()
    parser = _RaisingParser(TransientParserError("storage_blip"))

    with pytest.raises(TransientParserError):
        await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    # Row is still in 'parsing' state — the next retry will pick it up.
    # (No commit happens after the parse failure in the transient path.)
    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.PARSING


@pytest.mark.parametrize(
    "initial_status",
    [ResumeParseStatus.PARSED, ResumeParseStatus.FAILED],
)
async def test_parse_idempotent_on_terminal_status(
    sm: async_sessionmaker[AsyncSession],
    initial_status: ResumeParseStatus,
) -> None:
    """If the row is already parsed/failed (terminal), the task no-ops."""
    resume_id = await _make_resume_row(sm, status=initial_status)
    storage = _FakeStorage()
    parser = _FakeParser(ParsedResume(parser_name="library.v1", raw_text="x"))

    await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == initial_status
        # Parser was NOT called — no work done.
    assert parser.parse_calls == 0


async def test_parse_missing_row_is_silent(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    """Worker invoked for a deleted row — log + return, no exception."""
    fake_id = uuid4()
    storage = _FakeStorage()
    parser = _FakeParser(ParsedResume(parser_name="library.v1", raw_text="x"))

    # Should not raise.
    await _parse_resume_async(fake_id, sm=sm, storage=storage, parser=parser)

    assert parser.parse_calls == 0


async def test_parse_unexpected_exception_is_wrapped_as_transient(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    """A generic Exception from the parser is wrapped as TransientParserError so
    Celery autoretries it. The row stays at PARSING (no _mark_failed inline)."""
    resume_id = await _make_resume_row(sm)
    storage = _FakeStorage()
    parser = _RaisingParser(RuntimeError("disk_full"))

    with pytest.raises(TransientParserError, match="unexpected: RuntimeError"):
        await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.PARSING


async def test_mark_failed_skips_when_status_is_not_parsing(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    """If _mark_failed is called on a row that has been mutated externally
    (e.g. admin reset to pending, or another worker already marked it parsed),
    it must not clobber the existing status."""
    from jobify_worker.tasks.parse import _mark_failed

    resume_id = await _make_resume_row(sm, status=ResumeParseStatus.PARSED)

    await _mark_failed(sm, resume_id, reason="should_be_skipped")

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.PARSED  # unchanged
        assert row.parse_error is None  # unchanged


async def test_parse_picks_up_row_already_in_parsing_state(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    """A row left at PARSING (from a prior TransientParserError-and-retry) must
    be re-processed on the retry — not silently skipped."""
    resume_id = await _make_resume_row(sm, status=ResumeParseStatus.PARSING)
    storage = _FakeStorage()
    parser = _FakeParser(ParsedResume(parser_name="library.v1", raw_text="hi", email="a@b.com"))

    await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.PARSED
        assert row.parsed_json is not None
    assert parser.parse_calls == 1
