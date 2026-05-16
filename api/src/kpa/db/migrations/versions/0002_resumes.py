"""resumes

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    parse_status = postgresql.ENUM(
        "pending",
        "parsing",
        "parsed",
        "failed",
        name="resume_parse_status",
        schema="kpa",
        create_type=True,
    )
    parse_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "applicant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "parse_status",
            postgresql.ENUM(
                name="resume_parse_status",
                schema="kpa",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("parsed_json", postgresql.JSONB(), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
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
        schema="kpa",
    )
    op.create_index(
        "ix_resumes_applicant_id",
        "resumes",
        ["applicant_id"],
        schema="kpa",
    )


def downgrade() -> None:
    op.drop_index("ix_resumes_applicant_id", table_name="resumes", schema="kpa")
    op.drop_table("resumes", schema="kpa")
    op.execute("DROP TYPE IF EXISTS kpa.resume_parse_status")
    # Schema persists — dropping it would destroy alembic_version.
