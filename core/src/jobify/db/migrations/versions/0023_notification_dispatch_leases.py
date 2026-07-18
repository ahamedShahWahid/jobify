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

# The worker hard limit is configurable up to 7,200 seconds. Legacy workers do
# not own a dispatch token, so quarantine their in-flight rows beyond that
# maximum plus five minutes before token-aware workers may reclaim them.
_LEGACY_DISPATCH_QUARANTINE_SECONDS = 7_500


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
    # Keep pre-token dispatches in-flight during a rolling deployment. Resetting
    # them to pending here could make a new worker duplicate a non-idempotent
    # provider call that an old worker is still completing.
    op.execute(
        sa.text(
            "UPDATE jobify.notifications "
            "SET locked_until = now() + make_interval(secs => :quarantine_seconds) "
            "WHERE status = 'dispatching' AND deleted_at IS NULL"
        ).bindparams(quarantine_seconds=_LEGACY_DISPATCH_QUARANTINE_SECONDS)
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
