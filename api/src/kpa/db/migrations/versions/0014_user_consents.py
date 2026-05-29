"""user_consents + Notification.cancelled status

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-29

Adds the operational consent table for P4 DPDP scopes, plus the
NotificationStatus.CANCELLED enum value + Notification.cancelled_at column
that the sweep uses when consent is revoked.

NOTE: ALTER TYPE ... ADD VALUE cannot run inside a transaction with other
DDL. We use op.get_context().autocommit_block() for that statement.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- user_consents ---
    op.create_table(
        "user_consents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("kpa.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="kpa",
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_user_consents_user_scope_live "
        "ON kpa.user_consents (user_id, scope) WHERE deleted_at IS NULL"
    )

    # --- Notification.cancelled_at column ---
    op.add_column(
        "notifications",
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="kpa",
    )

    # --- NotificationStatus.CANCELLED enum value ---
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction.  We commit the
    # preceding DDL then execute on the raw asyncpg connection via run_async,
    # which bypasses SQLAlchemy's transaction tracking and runs outside any
    # transaction block.  This is the async-env equivalent of the synchronous
    # op.get_context().autocommit_block() pattern.
    bind = op.get_bind()
    bind.commit()
    bind.connection.dbapi_connection.run_async(
        lambda conn: conn.execute(
            "ALTER TYPE kpa.notification_status ADD VALUE IF NOT EXISTS 'cancelled'"
        )
    )


def downgrade() -> None:
    # Note: Postgres does NOT support DROP VALUE on enums. The 'cancelled'
    # value stays in the type after downgrade — that's an accepted limitation
    # of Postgres native enums. The model + sweep no longer reference it.

    op.drop_column("notifications", "cancelled_at", schema="kpa")
    op.execute("DROP INDEX kpa.ix_user_consents_user_scope_live")
    op.drop_table("user_consents", schema="kpa")
