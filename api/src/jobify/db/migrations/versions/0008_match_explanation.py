"""matches.explanation — JSONB nullable for templated/LLM match explanations

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20

Adds nullable JSONB column. Existing rows stay NULL until the next rescore
populates them via the templated generator.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("explanation", postgresql.JSONB, nullable=True),
        schema="jobify",
    )


def downgrade() -> None:
    op.drop_column("matches", "explanation", schema="jobify")
