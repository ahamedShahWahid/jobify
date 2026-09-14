"""matches: explanation_key column for the LLM-explanation cache

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-14

PERF-01: sha256 hex digest of the inputs that actually vary a surfaced
match's LLM explanation (see jobify.scoring.explainer.explanation_cache_key).
Nullable, set only when the stored explanation came from the LLM explainer's
current generator_version — never for a templated explanation or a
templated-fallback-after-LLM-failure. No index: it is only ever compared for
one (applicant_id, job_id) pair at a time, already reached via the existing
unique partial index on that pair, never queried by value.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("explanation_key", sa.CHAR(64), nullable=True),
        schema="jobify",
    )


def downgrade() -> None:
    op.drop_column("matches", "explanation_key", schema="jobify")
