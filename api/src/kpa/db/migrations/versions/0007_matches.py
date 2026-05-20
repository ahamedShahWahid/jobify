"""matches — hybrid applicant x job score

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-20

Adds:
- kpa.matches (one row per (applicant_id, job_id) live pair, JSONB metadata)
- Three partial indexes (UPSERT target + two feed-query paths)
- Three CHECK constraints (score ranges)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "applicant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vector_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("structured_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("total_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("score_components", postgresql.JSONB, nullable=False),
        sa.Column("model_versions", postgresql.JSONB, nullable=False),
        sa.Column("surfaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "vector_score >= 0 AND vector_score <= 1",
            name="ck_matches_vector_score_range",
        ),
        sa.CheckConstraint(
            "structured_score >= 0 AND structured_score <= 1",
            name="ck_matches_structured_score_range",
        ),
        sa.CheckConstraint(
            "total_score >= 0 AND total_score <= 1",
            name="ck_matches_total_score_range",
        ),
        schema="kpa",
    )
    # UPSERT target — partial UNIQUE for live rows.
    op.create_index(
        "ix_matches_applicant_job_live",
        "matches",
        ["applicant_id", "job_id"],
        unique=True,
        schema="kpa",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Feed query path: WHERE applicant_id = $1 AND surfaced AND live, ORDER BY total_score DESC.
    # Raw SQL because op.create_index can't portably express DESC ordering.
    op.execute(
        "CREATE INDEX ix_matches_applicant_surfaced "
        "ON kpa.matches (applicant_id, total_score DESC) "
        "WHERE deleted_at IS NULL AND surfaced_at IS NOT NULL"
    )
    # Recruiter "candidates for this job" path (deferred but the index lands now).
    op.execute(
        "CREATE INDEX ix_matches_job_surfaced "
        "ON kpa.matches (job_id, total_score DESC) "
        "WHERE deleted_at IS NULL AND surfaced_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS kpa.ix_matches_job_surfaced")
    op.execute("DROP INDEX IF EXISTS kpa.ix_matches_applicant_surfaced")
    op.drop_index("ix_matches_applicant_job_live", table_name="matches", schema="kpa")
    op.drop_table("matches", schema="kpa")
