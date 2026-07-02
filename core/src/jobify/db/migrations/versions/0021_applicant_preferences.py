"""applicant_preferences: desired_role/locations/expected_ctc, single source

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-01

Adds:
- jobify.applicant_preferences (one live row per applicant, partial-unique
  on applicant_id). desired_role is a plain varchar(50), following the
  consent-scope TEXT-in-DB precedent (no native PG enum — avoids the
  add-value migration pain); the 16-value vocabulary is enforced at the
  API boundary by the RoleCategory StrEnum.

Drops:
- jobify.applicants.locations
- jobify.applicants.expected_ctc

No backfill — no existing users on the platform (see docs/superpowers/specs/
2026-07-01-resume-review-preferences-design.md). Downgrade restores both
columns nullable (their pre-migration nullability) but cannot restore data.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applicant_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "applicant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.applicants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("desired_role", sa.String(50), nullable=True),
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("expected_ctc", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expected_ctc >= 0", name="ck_applicant_preferences_expected_ctc_nonneg"
        ),
        schema="jobify",
    )
    op.create_index(
        "ix_applicant_preferences_applicant_live",
        "applicant_preferences",
        ["applicant_id"],
        unique=True,
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_column("applicants", "locations", schema="jobify")
    op.drop_column("applicants", "expected_ctc", schema="jobify")


def downgrade() -> None:
    op.add_column(
        "applicants",
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(100)),
            nullable=True,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        schema="jobify",
    )
    op.add_column(
        "applicants",
        sa.Column("expected_ctc", sa.Numeric(12, 2), nullable=True),
        schema="jobify",
    )

    op.drop_index(
        "ix_applicant_preferences_applicant_live",
        table_name="applicant_preferences",
        schema="jobify",
    )
    op.drop_table("applicant_preferences", schema="jobify")
