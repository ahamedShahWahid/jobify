"""Add reclaimable leases to notification dispatch.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("dispatch_token", postgresql.UUID(as_uuid=True), nullable=True),
        schema="jobify",
    )
    op.add_column(
        "notifications",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        schema="jobify",
    )
    # Pre-lease deployments could strand rows in dispatching forever. Return
    # them to the claimable state once while rolling out lease ownership.
    op.execute(
        "UPDATE jobify.notifications SET status = 'pending' "
        "WHERE status = 'dispatching' AND deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_notifications_dispatch_recovery_live "
        "ON jobify.notifications (locked_until) "
        "WHERE deleted_at IS NULL AND status = 'dispatching'"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_dispatch_recovery_live",
        table_name="notifications",
        schema="jobify",
    )
    op.drop_column("notifications", "locked_until", schema="jobify")
    op.drop_column("notifications", "dispatch_token", schema="jobify")
