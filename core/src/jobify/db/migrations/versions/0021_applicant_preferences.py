"""applicant_preferences: desired_role/locations/expected_ctc, single source

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-01

Adds:
- jobify.role_category ENUM (16 values)
- jobify.applicant_preferences (one live row per applicant, partial-unique
  on applicant_id)

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

_ROLE_CATEGORY_VALUES = (
    "software_engineering",
    "data_analytics",
    "product_management",
    "design",
    "sales",
    "marketing",
    "customer_support",
    "operations",
    "finance_accounting",
    "hr_recruiting",
    "legal",
    "consulting",
    "business_development",
    "content_communications",
    "administration",
    "other",
)


def upgrade() -> None:
    role_category = postgresql.ENUM(
        *_ROLE_CATEGORY_VALUES,
        name="role_category",
        schema="jobify",
        create_type=True,
    )
    role_category.create(op.get_bind(), checkfirst=True)

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
        sa.Column(
            "desired_role",
            postgresql.ENUM(name="role_category", schema="jobify", create_type=False),
            nullable=True,
        ),
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
    op.execute("DROP TYPE IF EXISTS jobify.role_category")
