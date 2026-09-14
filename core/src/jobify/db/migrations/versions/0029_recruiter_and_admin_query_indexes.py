"""recruiter list, admin audit log, and lower(email) lookup indexes

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-14

Four independent hot-query indexes identified by a performance review, added
together because they land in one migration but touch unrelated tables:

- ``ix_applications_job_created_live`` — GET /v1/jobs/{id}/applicants keysets
  on (created_at DESC, id DESC) filtered by job_id; no existing index leads
  with job_id (both application indexes lead with applicant_id), so the
  recruiter pipeline list was a sequential scan + sort. The same index also
  serves the applicant_count subquery /v1/jobs/me now uses in place of an
  outer join (see the accompanying query change in
  jobify_api.routes.jobs.recruiter).
- ``ix_audit_logs_created_id`` — GET /v1/admin/audit-logs with no filters
  (the common case) keysets on (created_at DESC, id DESC); audit_logs had no
  index at all until now (append-only, no soft-delete column).
- ``ix_users_email_lower_live`` / ``ix_employer_invites_email_lower_live`` —
  every live call site compares ``func.lower(email) == <already-lowercased
  value>`` (team_service.add_member, routes/invites.py, dsr export/deleter),
  which a plain btree index on ``email`` cannot serve. Expression indexes on
  ``lower(email)`` match those queries exactly. The plain ``ix_users_email_live``
  index is kept: auth/service.py and scripts/grant_admin.py still compare
  ``User.email ==`` (exact case) against the Google-claimed email.

Plain SQL throughout: op.create_index cannot express DESC ordering or a
functional (lower(...)) index expression.
"""

from __future__ import annotations

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_applications_job_created_live "
        "ON jobify.applications (job_id, created_at DESC, id DESC) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_audit_logs_created_id ON jobify.audit_logs (created_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX ix_users_email_lower_live "
        "ON jobify.users (lower(email)) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_employer_invites_email_lower_live "
        "ON jobify.employer_invites (lower(email)) "
        "WHERE deleted_at IS NULL AND status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobify.ix_employer_invites_email_lower_live")
    op.execute("DROP INDEX IF EXISTS jobify.ix_users_email_lower_live")
    op.execute("DROP INDEX IF EXISTS jobify.ix_audit_logs_created_id")
    op.execute("DROP INDEX IF EXISTS jobify.ix_applications_job_created_live")
