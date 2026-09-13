"""applicant preferences: backfill a default row for applicants that never had one

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-13

0021 created applicant_preferences without a backfill on the assumption there
were no existing users, but applicants created before it (local/dev DBs, seeded
accounts) have no row, so GET /v1/applicants/me/preferences returned 500
`applicant_preferences_missing`. Inserts one default row (every column has a
server default) for each live applicant with NO row at all.

Applicants whose only row is soft-deleted are deliberately skipped: that is the
invariant violation the route still surfaces as a 500, and this backfill uses
the same "never existed" rule as the route's on-read provisioning.
"""

from __future__ import annotations

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO jobify.applicant_preferences (applicant_id)
        SELECT a.id
        FROM jobify.applicants a
        WHERE a.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM jobify.applicant_preferences p WHERE p.applicant_id = a.id
          )
        """
    )


def downgrade() -> None:
    # Data-only backfill: backfilled rows are indistinguishable from rows created
    # at signup, and removing them would reintroduce the 500. Nothing to undo.
    pass
