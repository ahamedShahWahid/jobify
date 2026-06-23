"""oauth_identities and refresh_tokens

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17

Adds:
- jobify.oauth_provider enum
- jobify.oauth_identities (M:1 to users; supports future apple/phone identities)
- jobify.refresh_tokens (rotation + reuse detection)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE jobify.oauth_provider AS ENUM ('google')")

    op.create_table(
        "oauth_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "google",
                name="oauth_provider",
                schema="jobify",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email_at_link", sa.String(length=254), nullable=True),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        schema="jobify",
    )
    op.create_index(
        "ix_oauth_identities_provider_subject_live",
        "oauth_identities",
        ["provider", "provider_subject"],
        unique=True,
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_oauth_identities_user_id_live",
        "oauth_identities",
        ["user_id"],
        schema="jobify",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "replaced_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        schema="jobify",
    )
    op.create_index(
        "ix_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
        schema="jobify",
    )
    op.create_index(
        "ix_refresh_tokens_family_id_active",
        "refresh_tokens",
        ["family_id"],
        schema="jobify",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_refresh_tokens_user_id_active",
        "refresh_tokens",
        ["user_id"],
        schema="jobify",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id_active", table_name="refresh_tokens", schema="jobify")
    op.drop_index(
        "ix_refresh_tokens_family_id_active", table_name="refresh_tokens", schema="jobify"
    )
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens", schema="jobify")
    op.drop_table("refresh_tokens", schema="jobify")

    op.drop_index(
        "ix_oauth_identities_user_id_live", table_name="oauth_identities", schema="jobify"
    )
    op.drop_index(
        "ix_oauth_identities_provider_subject_live", table_name="oauth_identities", schema="jobify"
    )
    op.drop_table("oauth_identities", schema="jobify")

    op.execute("DROP TYPE IF EXISTS jobify.oauth_provider")
