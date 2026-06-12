"""employers + jobs

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-20

Adds:
- jobify.job_status ENUM ('open', 'closed')
- jobify.employers (with partial-unique index on name_norm)
- jobify.jobs (with two partial indexes + two CHECK constraints)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    job_status = postgresql.ENUM(
        "open",
        "closed",
        name="job_status",
        schema="jobify",
        create_type=True,
    )
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "employers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_norm", sa.String(200), nullable=False),
        sa.Column("gst", sa.String(15), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        schema="jobify",
    )
    op.create_index(
        "ix_employers_name_norm_live",
        "employers",
        ["name_norm"],
        unique=True,
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "employer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.employers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("min_exp_years", sa.Integer(), nullable=False),
        sa.Column("max_exp_years", sa.Integer(), nullable=False),
        sa.Column("ctc_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("ctc_max", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="job_status", schema="jobify", create_type=False),
            nullable=False,
            server_default=sa.text("'open'::jobify.job_status"),
        ),
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
            "max_exp_years >= min_exp_years",
            name="ck_jobs_exp_years_ordered",
        ),
        sa.CheckConstraint(
            "ctc_max IS NULL OR ctc_min IS NULL OR ctc_max >= ctc_min",
            name="ck_jobs_ctc_ordered",
        ),
        schema="jobify",
    )
    op.create_index(
        "ix_jobs_employer_id_live",
        "jobs",
        ["employer_id"],
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Plain SQL because op.create_index has no portable way to express
    # `posted_at DESC` ordering on the second column. The (status, posted_at DESC)
    # shape is the feed-query path called out in spec §5 and consumed by P2.3.
    op.execute(
        "CREATE INDEX ix_jobs_status_posted_at_live "
        "ON jobify.jobs (status, posted_at DESC) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobify.ix_jobs_status_posted_at_live")
    op.drop_index("ix_jobs_employer_id_live", table_name="jobs", schema="jobify")
    op.drop_table("jobs", schema="jobify")
    op.drop_index("ix_employers_name_norm_live", table_name="employers", schema="jobify")
    op.drop_table("employers", schema="jobify")
    op.execute("DROP TYPE IF EXISTS jobify.job_status")
