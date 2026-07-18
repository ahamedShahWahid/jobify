"""Add per-claim ownership tokens to outbox processing.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("dispatch_token", postgresql.UUID(as_uuid=True), nullable=True),
        schema="jobify",
    )


def downgrade() -> None:
    op.drop_column("outbox_events", "dispatch_token", schema="jobify")
