# api/src/jobify/db/migrations/versions/0013_audit_logs.py
"""audit_logs table — append-only P4 DPDP evidence substrate

Revision ID: 0013
Revises: 0012
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "context",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="jobify",
    )

    # Actor timeline: WHERE actor_user_id = $1 ORDER BY created_at DESC.
    # Raw SQL because op.create_index can't portably express DESC ordering.
    op.execute(
        "CREATE INDEX ix_audit_logs_actor_created "
        "ON jobify.audit_logs (actor_user_id, created_at DESC)"
    )

    # Resource timeline: WHERE resource_type = $1 AND resource_id = $2 ORDER BY created_at DESC.
    op.execute(
        "CREATE INDEX ix_audit_logs_resource_created "
        "ON jobify.audit_logs (resource_type, resource_id, created_at DESC)"
    )

    # Action timeline: WHERE action = $1 ORDER BY created_at DESC.
    op.execute(
        "CREATE INDEX ix_audit_logs_action_created ON jobify.audit_logs (action, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobify.ix_audit_logs_action_created")
    op.execute("DROP INDEX IF EXISTS jobify.ix_audit_logs_resource_created")
    op.execute("DROP INDEX IF EXISTS jobify.ix_audit_logs_actor_created")
    op.drop_table("audit_logs", schema="jobify")
