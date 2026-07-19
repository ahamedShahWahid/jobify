"""application stages: pipeline column on applications + stage-events history

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-19

Adds applications.stage (varchar+CHECK, default 'applied' — existing rows are
backfilled by the server default) and jobify.application_stage_events (the
applicant-timeline history; actor_user_id SET NULL survives DSR). Vocabulary
'applied','shortlisted','interview','offer','hired','rejected'. See
docs/superpowers/specs/2026-07-19-application-stages-design.md.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

_VOCAB = "('applied','shortlisted','interview','offer','hired','rejected')"


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "stage",
            sa.String(16),
            nullable=False,
            server_default="applied",
        ),
        schema="jobify",
    )
    op.create_check_constraint(
        "ck_applications_stage",
        "applications",
        f"stage IN {_VOCAB}",
        schema="jobify",
    )

    op.create_table(
        "application_stage_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_stage", sa.String(16), nullable=False),
        sa.Column("to_stage", sa.String(16), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.users.id", ondelete="SET NULL"),
            nullable=True,
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
            f"from_stage IN {_VOCAB}", name="ck_application_stage_events_from"
        ),
        sa.CheckConstraint(
            f"to_stage IN {_VOCAB}", name="ck_application_stage_events_to"
        ),
        schema="jobify",
    )
    op.create_index(
        "ix_application_stage_events_app_created",
        "application_stage_events",
        ["application_id", sa.text("created_at DESC")],
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_stage_events_app_created",
        table_name="application_stage_events",
        schema="jobify",
    )
    op.drop_table("application_stage_events", schema="jobify")
    op.drop_constraint(
        "ck_applications_stage", "applications", schema="jobify", type_="check"
    )
    op.drop_column("applications", "stage", schema="jobify")
