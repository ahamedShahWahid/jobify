"""Add durable external-side-effect outbox.

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    kind = postgresql.ENUM(
        "task_dispatch",
        "blob_delete",
        name="outbox_event_kind",
        schema="jobify",
        create_type=False,
    )
    status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="outbox_event_status",
        schema="jobify",
        create_type=False,
    )
    kind.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", kind, nullable=False),
        sa.Column("status", status, server_default="pending", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="jobify",
    )
    op.execute(
        "CREATE INDEX ix_outbox_events_claimable_live "
        "ON jobify.outbox_events (status, available_at) "
        "WHERE deleted_at IS NULL AND status IN ('pending', 'processing')"
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_claimable_live", table_name="outbox_events", schema="jobify")
    op.drop_table("outbox_events", schema="jobify")
    op.execute("DROP TYPE IF EXISTS jobify.outbox_event_status")
    op.execute("DROP TYPE IF EXISTS jobify.outbox_event_kind")
