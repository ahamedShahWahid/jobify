"""notifications — outbox notification rows

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-20

Adds:
- kpa.notification_status ENUM ('pending', 'dispatching', 'sent', 'failed')
- kpa.notification_channel ENUM ('email', 'in_app')
- kpa.notifications table with soft-delete trio, JSONB payload, and two
  partial indexes (sweeper query path + user inbox path).

Both partial indexes are created via raw SQL (op.execute) because:
- The sweeper index uses a multi-value ``status IN ('pending', 'dispatching')``
  predicate that op.create_index cannot express cleanly.
- The user inbox index uses DESC ordering on created_at, which op.create_index
  also doesn't support portably.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create both enum types first.
    notification_status = postgresql.ENUM(
        "pending",
        "dispatching",
        "sent",
        "failed",
        name="notification_status",
        schema="kpa",
        create_type=True,
    )
    notification_status.create(op.get_bind(), checkfirst=True)

    notification_channel = postgresql.ENUM(
        "email",
        "in_app",
        name="notification_channel",
        schema="kpa",
        create_type=True,
    )
    notification_channel.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column(
            "channel",
            postgresql.ENUM(name="notification_channel", schema="kpa", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="notification_status", schema="kpa", create_type=False),
            nullable=False,
            server_default=sa.text("'pending'::kpa.notification_status"),
        ),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "send_after",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text, nullable=True),
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

    # Sweeper query path: pending/dispatching rows due for delivery.
    # Uses raw SQL because op.create_index cannot express multi-value IN predicates.
    op.execute(
        "CREATE INDEX ix_notifications_status_send_after_live "
        "ON kpa.notifications (status, send_after) "
        "WHERE deleted_at IS NULL AND status IN ('pending', 'dispatching')"
    )

    # User inbox query path: all live rows for a user, newest first.
    # Uses raw SQL because op.create_index cannot portably express DESC ordering.
    op.execute(
        "CREATE INDEX ix_notifications_user_id_created_at_live "
        "ON kpa.notifications (user_id, created_at DESC) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS kpa.ix_notifications_user_id_created_at_live")
    op.execute("DROP INDEX IF EXISTS kpa.ix_notifications_status_send_after_live")
    op.drop_table("notifications", schema="kpa")
    postgresql.ENUM(
        "pending",
        "dispatching",
        "sent",
        "failed",
        name="notification_status",
        schema="kpa",
    ).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "email",
        "in_app",
        name="notification_channel",
        schema="kpa",
    ).drop(op.get_bind(), checkfirst=True)
