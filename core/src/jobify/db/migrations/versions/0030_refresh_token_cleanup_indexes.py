"""refresh_tokens: indexes for the new cleanup_refresh_tokens task

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-14

PERF-08: refresh_tokens had no cleanup at all and no index supporting one.
The new jobify.cleanup_refresh_tokens task (worker/tasks/cleanup_refresh_tokens.py)
deletes rows where ``expires_at < now()`` OR ``revoked_at < cutoff`` — these two
indexes let Postgres serve that OR via a bitmap-or instead of a sequential scan.
``ix_refresh_tokens_revoked_at`` is partial on ``revoked_at IS NOT NULL``: a NULL
row never satisfies ``revoked_at < cutoff``, and the predicate is a subset of
that condition, so the planner can still use it for the cleanup query.

Plain SQL: the revoked_at index needs a WHERE clause op.create_index can express,
but kept alongside the expires_at index in one file since both exist for the
one query in one new task.
"""

from __future__ import annotations

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_refresh_tokens_expires_at ON jobify.refresh_tokens (expires_at)")
    op.execute(
        "CREATE INDEX ix_refresh_tokens_revoked_at "
        "ON jobify.refresh_tokens (revoked_at) "
        "WHERE revoked_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobify.ix_refresh_tokens_revoked_at")
    op.execute("DROP INDEX IF EXISTS jobify.ix_refresh_tokens_expires_at")
