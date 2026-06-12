# api/src/jobify/db/migrations/versions/0019_jobs_recruiter_list_index.py
"""jobs — composite index for the recruiter job-list cursor query

Revision ID: 0019
Revises: 0018

GET /v1/jobs/me filters by employer_id (via the EmployerUser join) and
keysets on (posted_at DESC, id DESC). The existing indexes cover
(employer_id) and (status, posted_at DESC) but neither serves the combined
filter + ordering, so the recruiter list degrades to a sort once an
employer's job count grows.

Plain SQL because op.create_index cannot express DESC column ordering.
The old single-column ix_jobs_employer_id_live is dropped: employer_id is
the new index's leading column, so it was made a redundant prefix.
"""

from __future__ import annotations

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_jobs_employer_posted_at_live "
        "ON jobify.jobs (employer_id, posted_at DESC, id DESC) "
        "WHERE deleted_at IS NULL"
    )
    op.execute("DROP INDEX IF EXISTS jobify.ix_jobs_employer_id_live")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX ix_jobs_employer_id_live "
        "ON jobify.jobs (employer_id) "
        "WHERE deleted_at IS NULL"
    )
    op.execute("DROP INDEX IF EXISTS jobify.ix_jobs_employer_posted_at_live")
