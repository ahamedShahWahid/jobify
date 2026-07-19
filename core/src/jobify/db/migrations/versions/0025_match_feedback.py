"""match_feedback: applicant thumbs up/down on surfaced matches

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-19

Adds jobify.match_feedback — one live row per (applicant_id, job_id), rating
varchar+CHECK ('up'/'down') per the consent-scope/desired_role precedent (no
native PG enum). 'down' rows exclude the job from that applicant's feed.
Partial-unique on the pair; (rating, created_at DESC) partial index serves the
admin Match QA list + summary. See docs/superpowers/specs/
2026-07-19-match-feedback-design.md.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "applicant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.applicants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.String(8), nullable=False),
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
        sa.CheckConstraint("rating IN ('up', 'down')", name="ck_match_feedback_rating"),
        schema="jobify",
    )
    op.create_index(
        "ix_match_feedback_applicant_job_live",
        "match_feedback",
        ["applicant_id", "job_id"],
        unique=True,
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_match_feedback_rating_created_at",
        "match_feedback",
        ["rating", sa.text("created_at DESC")],
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_match_feedback_rating_created_at",
        table_name="match_feedback",
        schema="jobify",
    )
    op.drop_index(
        "ix_match_feedback_applicant_job_live",
        table_name="match_feedback",
        schema="jobify",
    )
    op.drop_table("match_feedback", schema="jobify")
