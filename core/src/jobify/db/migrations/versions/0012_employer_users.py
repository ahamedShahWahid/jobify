# api/src/jobify/db/migrations/versions/0012_employer_users.py
"""employer_users table + employers.created_by_user_id

Revision ID: 0012
Revises: 0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employers",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="jobify",
    )
    op.create_foreign_key(
        "fk_employers_created_by_user_id",
        "employers",
        "users",
        ["created_by_user_id"],
        ["id"],
        source_schema="jobify",
        referent_schema="jobify",
    )

    op.create_table(
        "employer_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["jobify.employers.id"],
            name="fk_employer_users_employer_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["jobify.users.id"],
            name="fk_employer_users_user_id",
        ),
        sa.CheckConstraint(
            "role IN ('owner','member')",
            name="ck_employer_users_role",
        ),
        schema="jobify",
    )
    op.create_index(
        "ix_employer_users_pair_live",
        "employer_users",
        ["employer_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="jobify",
    )
    op.create_index(
        "ix_employer_users_user",
        "employer_users",
        ["user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="jobify",
    )


def downgrade() -> None:
    op.drop_index("ix_employer_users_user", table_name="employer_users", schema="jobify")
    op.drop_index("ix_employer_users_pair_live", table_name="employer_users", schema="jobify")
    op.drop_table("employer_users", schema="jobify")
    op.drop_constraint(
        "fk_employers_created_by_user_id", "employers", schema="jobify", type_="foreignkey"
    )
    op.drop_column("employers", "created_by_user_id", schema="jobify")
