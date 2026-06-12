"""applicant_embeddings — vector(1536) table for matching pipeline

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-19

Adds:
- pgvector extension (CREATE EXTENSION IF NOT EXISTS vector)
- jobify.applicant_embeddings (vector(1536), unique(applicant_id), HNSW index)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension must exist before Vector columns can be created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "applicant_embeddings",
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
            unique=True,
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("canonicalized_text_hash", sa.CHAR(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
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
    # HNSW + cosine ops because §6.3 specifies cosine similarity for matching.
    # HNSW at pgvector defaults (m=16, ef_construction=64) — fine for MVP scale.
    # Tune when applicant count exceeds ~100k or recall/latency targets drift.
    op.execute(
        "CREATE INDEX ix_applicant_embeddings_hnsw "
        "ON jobify.applicant_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobify.ix_applicant_embeddings_hnsw")
    op.drop_table("applicant_embeddings", schema="jobify")
    # Intentionally NOT dropping the vector extension — P2 job_embeddings will need it.
