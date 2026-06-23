"""Make resume PII columns nullable for DSR delete scrubbing.

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "resumes",
        "storage_key",
        existing_type=sa.String(512),
        nullable=True,
        schema="jobify",
    )
    op.alter_column(
        "resumes",
        "original_filename",
        existing_type=sa.String(255),
        nullable=True,
        schema="jobify",
    )


def downgrade() -> None:
    # Scrubbed tombstones have NULL values; fill sentinels before restoring
    # NOT NULL so local downgrades do not fail on already-deleted accounts.
    op.execute(
        "UPDATE jobify.resumes "
        "SET storage_key = COALESCE(storage_key, ''), "
        "original_filename = COALESCE(original_filename, '(deleted)')"
    )
    op.alter_column(
        "resumes",
        "original_filename",
        existing_type=sa.String(255),
        nullable=False,
        schema="jobify",
    )
    op.alter_column(
        "resumes",
        "storage_key",
        existing_type=sa.String(512),
        nullable=False,
        schema="jobify",
    )
