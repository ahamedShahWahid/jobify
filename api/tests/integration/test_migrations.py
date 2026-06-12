"""Verifies alembic upgrade head + downgrade base round-trip."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
async def test_migrated_db_has_users_and_applicants_tables(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'kpa'
        ORDER BY table_name
    """)
    )
    names = {row[0] for row in result}
    assert "users" in names
    assert "applicants" in names


@pytest.mark.integration
async def test_users_has_partial_indexes(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'kpa' AND tablename = 'users'
    """)
    )
    names = {row[0] for row in result}
    assert "ix_users_email_live" in names
    assert "ix_users_phone_live" in names


@pytest.mark.integration
async def test_migrated_db_has_employers_and_jobs_tables(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'kpa'
        ORDER BY table_name
    """)
    )
    names = {row[0] for row in result}
    assert "employers" in names
    assert "jobs" in names


@pytest.mark.integration
async def test_jobs_has_partial_indexes(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'kpa' AND tablename = 'jobs'
    """)
    )
    names = {row[0] for row in result}
    # 0019 replaced ix_jobs_employer_id_live with the wider composite
    # (employer_id, posted_at DESC, id DESC) serving the recruiter list.
    assert "ix_jobs_employer_posted_at_live" in names
    assert "ix_jobs_employer_id_live" not in names
    assert "ix_jobs_status_posted_at_live" in names


@pytest.mark.integration
async def test_employers_name_norm_is_partial_unique(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'kpa'
          AND tablename = 'employers'
          AND indexname = 'ix_employers_name_norm_live'
    """)
    )
    row = result.first()
    assert row is not None
    assert "UNIQUE INDEX" in row[0]
    assert "deleted_at IS NULL" in row[0]


@pytest.mark.integration
async def test_migrated_db_has_job_embeddings_table(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'kpa'
    """)
    )
    names = {row[0] for row in result}
    assert "job_embeddings" in names


@pytest.mark.integration
async def test_job_embeddings_has_hnsw_index(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT indexname, indexdef FROM pg_indexes
        WHERE schemaname = 'kpa' AND tablename = 'job_embeddings'
    """)
    )
    rows = list(result)
    names = {row[0] for row in rows}
    assert "ix_job_embeddings_hnsw" in names
    hnsw_def = next(row[1] for row in rows if row[0] == "ix_job_embeddings_hnsw")
    assert "hnsw" in hnsw_def.lower()
    assert "vector_cosine_ops" in hnsw_def


@pytest.mark.integration
async def test_job_embeddings_job_id_is_unique(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'kpa'
          AND tablename = 'job_embeddings'
          AND indexdef ILIKE '%UNIQUE%job_id%'
    """)
    )
    rows = list(result)
    assert len(rows) >= 1  # job_embeddings_job_id_key or similar


@pytest.mark.integration
async def test_migrated_db_has_matches_table(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'kpa'
    """)
    )
    names = {row[0] for row in result}
    assert "matches" in names


@pytest.mark.integration
async def test_matches_has_partial_indexes(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'kpa' AND tablename = 'matches'
    """)
    )
    names = {row[0] for row in result}
    assert "ix_matches_applicant_job_live" in names
    assert "ix_matches_applicant_surfaced" in names
    assert "ix_matches_job_surfaced" in names


@pytest.mark.integration
async def test_matches_check_constraints_exist(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'kpa.matches'::regclass AND contype = 'c'
    """)
    )
    names = {row[0] for row in result}
    assert "ck_matches_vector_score_range" in names
    assert "ck_matches_structured_score_range" in names
    assert "ck_matches_total_score_range" in names


@pytest.mark.integration
async def test_matches_has_explanation_column(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT column_name, data_type, is_nullable FROM information_schema.columns
        WHERE table_schema = 'kpa' AND table_name = 'matches' AND column_name = 'explanation'
    """)
    )
    row = result.first()
    assert row is not None
    assert row[1] == "jsonb"
    assert row[2] == "YES"


@pytest.mark.integration
async def test_migrated_db_has_applications_and_saved_jobs_tables(
    session: AsyncSession,
) -> None:
    result = await session.execute(
        text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'kpa'
        ORDER BY table_name
    """)
    )
    names = {row[0] for row in result}
    assert "applications" in names
    assert "saved_jobs" in names


@pytest.mark.integration
async def test_applications_has_partial_unique_on_applicant_job(
    session: AsyncSession,
) -> None:
    result = await session.execute(
        text("""
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'kpa'
          AND tablename = 'applications'
          AND indexname = 'ix_applications_applicant_job_live'
    """)
    )
    row = result.first()
    assert row is not None
    assert "UNIQUE INDEX" in row[0]
    assert "deleted_at IS NULL" in row[0]


@pytest.mark.integration
async def test_saved_jobs_has_partial_unique_on_applicant_job(
    session: AsyncSession,
) -> None:
    result = await session.execute(
        text("""
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'kpa'
          AND tablename = 'saved_jobs'
          AND indexname = 'ix_saved_jobs_applicant_job_live'
    """)
    )
    row = result.first()
    assert row is not None
    assert "UNIQUE INDEX" in row[0]
    assert "deleted_at IS NULL" in row[0]


# ---------------------------------------------------------------------------
# Migration 0011 — notifications table
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_migrated_db_has_notifications_table(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'kpa'
        ORDER BY table_name
    """)
    )
    names = {row[0] for row in result}
    assert "notifications" in names


@pytest.mark.integration
async def test_notifications_has_sweeper_partial_index(session: AsyncSession) -> None:
    """ix_notifications_status_send_after_live must exist with the right predicate."""
    result = await session.execute(
        text("""
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'kpa'
          AND tablename = 'notifications'
          AND indexname = 'ix_notifications_status_send_after_live'
    """)
    )
    row = result.first()
    assert row is not None, "sweeper partial index not found"
    indexdef = row[0]
    assert "deleted_at IS NULL" in indexdef


@pytest.mark.integration
async def test_notifications_has_user_inbox_partial_index(session: AsyncSession) -> None:
    """ix_notifications_user_id_created_at_live must exist."""
    result = await session.execute(
        text("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'kpa'
          AND tablename = 'notifications'
    """)
    )
    names = {row[0] for row in result}
    assert "ix_notifications_user_id_created_at_live" in names
