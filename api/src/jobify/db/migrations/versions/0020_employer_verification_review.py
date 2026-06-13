# api/src/jobify/db/migrations/versions/0020_employer_verification_review.py
"""employers.rejected_at + rejection_reason for admin verification review

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-13

Both nullable. The verification tri-state is DERIVED, not stored as an enum:
  verified_at IS NOT NULL                       -> verified
  rejected_at IS NOT NULL (and verified_at NULL) -> rejected
  otherwise                                      -> pending

Verify and reject are mutually exclusive — each admin action clears the other's
timestamp (re-verifying a rejected employer just works). rejection_reason is the
reviewer's note and is only meaningful while rejected_at is set; clearing the
rejection (by verifying) clears the reason too.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employers",
        sa.Column("rejected_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="jobify",
    )
    op.add_column(
        "employers",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        schema="jobify",
    )


def downgrade() -> None:
    op.drop_column("employers", "rejection_reason", schema="jobify")
    op.drop_column("employers", "rejected_at", schema="jobify")
