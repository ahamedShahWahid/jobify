"""Make PII columns nullable for DSR delete scrubbing.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-29

Per the DSR-delete spec (§2 table), ``delete_user_data`` sets PII columns to
NULL on applicant + resume tombstones. The existing NOT NULL constraints on
``applicants.full_name`` and ``applicants.locations`` prevent this.

Changes:
- ``applicants.full_name`` VARCHAR(200) NOT NULL → nullable
- ``applicants.locations`` VARCHAR(100)[] NOT NULL → nullable
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "applicants",
        "full_name",
        existing_type=sa.String(200),
        nullable=True,
        schema="jobify",
    )
    op.alter_column(
        "applicants",
        "locations",
        existing_type=sa.ARRAY(sa.String(100)),
        nullable=True,
        schema="jobify",
    )


def downgrade() -> None:
    # Restore NOT NULL. Any scrubbed rows (NULL) must be cleaned up manually
    # before downgrading — set them to a sentinel value if needed.
    op.alter_column(
        "applicants",
        "locations",
        existing_type=sa.ARRAY(sa.String(100)),
        nullable=False,
        schema="jobify",
    )
    op.alter_column(
        "applicants",
        "full_name",
        existing_type=sa.String(200),
        nullable=False,
        schema="jobify",
    )
