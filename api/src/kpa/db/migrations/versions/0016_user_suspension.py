# api/src/kpa/db/migrations/versions/0016_user_suspension.py
"""users.suspended_at + suspension_reason for admin moderation

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-29

Both nullable. suspended_at IS NULL <=> user is active. Clearing the
suspension always clears BOTH columns (admin tooling reads
suspension_reason IS NOT NULL as 'this user is suspended' defensively).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("suspended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="kpa",
    )
    op.add_column(
        "users",
        sa.Column("suspension_reason", sa.Text(), nullable=True),
        schema="kpa",
    )


def downgrade() -> None:
    op.drop_column("users", "suspension_reason", schema="kpa")
    op.drop_column("users", "suspended_at", schema="kpa")
