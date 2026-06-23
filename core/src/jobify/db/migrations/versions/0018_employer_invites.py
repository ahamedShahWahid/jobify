# api/src/jobify/db/migrations/versions/0018_employer_invites.py
"""employer_invites — owner-managed invitations to join an employer

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-07

Adds:
- jobify.employer_invite_status ENUM ('pending', 'accepted', 'revoked', 'expired')
- jobify.employer_invites table (soft-delete trio, FKs, role CHECK)
- Two partial indexes (at-most-one-live-pending-per-(employer,email) unique +
  an email lookup path), both via raw SQL because op.create_index cannot
  express the multi-predicate WHERE clause that includes status.

Enum *creation* is a normal-migration operation (only ADD VALUE to an existing
enum needs the autocommit dance — not applicable here).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    invite_status = postgresql.ENUM(
        "pending",
        "accepted",
        "revoked",
        "expired",
        name="employer_invite_status",
        schema="jobify",
        create_type=True,
    )
    invite_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "employer_invites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "employer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.employers.id"),
            nullable=False,
        ),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="employer_invite_status", schema="jobify", create_type=False),
            nullable=False,
            server_default=sa.text("'pending'::jobify.employer_invite_status"),
        ),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "accepted_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobify.users.id"),
            nullable=True,
        ),
        sa.Column("token", sa.Text, nullable=True),
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
        sa.CheckConstraint("role IN ('owner','member')", name="ck_employer_invites_role"),
        schema="jobify",
    )

    # At most one live pending invite per (employer, email).
    op.execute(
        "CREATE UNIQUE INDEX ix_employer_invites_pending_live "
        "ON jobify.employer_invites (employer_id, email) "
        "WHERE deleted_at IS NULL AND status = 'pending'"
    )
    # Invitee lookup path: pending invites by email.
    op.execute(
        "CREATE INDEX ix_employer_invites_email_live "
        "ON jobify.employer_invites (email) "
        "WHERE deleted_at IS NULL AND status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobify.ix_employer_invites_email_live")
    op.execute("DROP INDEX IF EXISTS jobify.ix_employer_invites_pending_live")
    op.drop_table("employer_invites", schema="jobify")
    postgresql.ENUM(
        "pending",
        "accepted",
        "revoked",
        "expired",
        name="employer_invite_status",
        schema="jobify",
    ).drop(op.get_bind(), checkfirst=True)
