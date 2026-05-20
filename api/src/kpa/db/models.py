"""SQLAlchemy declarative models for the KPA service.

Per IMPLEMENTATION_SPEC.md §4.2: SQLAlchemy 2.x style with typed Mapped
columns. Never use these as response schemas — separate Pydantic *Read /
*Create / *Update models belong in the domain modules.

Per §5: every domain table carries `id` (UUID), `created_at`, `updated_at`,
and `deleted_at TIMESTAMPTZ NULL` for soft delete.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base. Lives in the `kpa` schema."""

    __table_args__: Any = {"schema": "kpa"}  # noqa: RUF012 — SQLAlchemy base declares this as Any


UuidPK = Annotated[
    uuid.UUID,
    mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),
]
CreatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]
DeletedAt = Annotated[
    datetime | None,
    mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=False,  # partial index added per-table in the migration.
    ),
]


class UserRole(StrEnum):
    APPLICANT = "applicant"
    RECRUITER = "recruiter"
    ADMIN = "admin"


class User(Base):
    """Auth principal — see spec §5."""

    __tablename__ = "users"

    id: Mapped[UuidPK]
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            native_enum=True,
            schema="kpa",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        Index("ix_users_email_live", "email", postgresql_where="deleted_at IS NULL"),
        Index("ix_users_phone_live", "phone", postgresql_where="deleted_at IS NULL"),
        {"schema": "kpa"},
    )


class Applicant(Base):
    """Applicant profile — see spec §5."""

    __tablename__ = "applicants"

    id: Mapped[UuidPK]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default="{}"
    )
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    years_experience: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]


class ResumeParseStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class Resume(Base):
    """Uploaded resume — see spec §6.1 and the P1.0 design doc.

    In this slice, every row is created with parse_status='pending' and never
    transitions. The parse worker plan moves rows through parsing → parsed/failed.
    """

    __tablename__ = "resumes"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[ResumeParseStatus] = mapped_column(
        SAEnum(
            ResumeParseStatus,
            name="resume_parse_status",
            native_enum=True,
            schema="kpa",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ResumeParseStatus.PENDING,
        server_default=ResumeParseStatus.PENDING.value,
    )
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]


class ApplicantEmbedding(Base):
    """One current vector per applicant. Re-embed UPSERTs in place.

    Embedded text source is the canonicalized profile of the *latest* parsed
    resume for the applicant. The canonicalized_text_hash column is the
    idempotency key — re-running the embedding worker on identical content
    is a no-op.
    """

    __tablename__ = "applicant_embeddings"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    canonicalized_text_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]


class OAuthProvider(StrEnum):
    GOOGLE = "google"


class OAuthIdentity(Base):
    """Link between a user and an external identity provider.

    M:1 to users — a single user can have multiple identities. New providers
    (apple, phone) extend ``OAuthProvider`` and ALTER TYPE in their own plan.
    """

    __tablename__ = "oauth_identities"

    id: Mapped[UuidPK]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[OAuthProvider] = mapped_column(
        SAEnum(
            OAuthProvider,
            name="oauth_provider",
            native_enum=True,
            schema="kpa",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email_at_link: Mapped[str | None] = mapped_column(String(254), nullable=True)
    # Distinct from created_at so a future backdated-linking migration
    # (e.g., associating an existing account with a Google identity) can
    # preserve the original link time without rewriting the row's row-level
    # audit columns.
    linked_at: Mapped[CreatedAt]
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        Index(
            "ix_oauth_identities_provider_subject_live",
            "provider",
            "provider_subject",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_oauth_identities_user_id_live",
            "user_id",
            postgresql_where="deleted_at IS NULL",
        ),
        {"schema": "kpa"},
    )


class RefreshToken(Base):
    """Opaque refresh token (sha256-hashed at rest).

    Append-only by convention: rows are never UPDATEd except to set the
    revocation columns and ``last_used_at``. Diverges from the soft-delete
    pattern used by domain tables — no ``deleted_at``. The model is
    `revoked_at` + `revocation_reason` (rotated / logout / reuse_detected /
    admin), as approved in the spec.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[UuidPK]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revocation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    __table_args__ = (
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
        Index(
            "ix_refresh_tokens_family_id_active",
            "family_id",
            postgresql_where="revoked_at IS NULL",
        ),
        Index(
            "ix_refresh_tokens_user_id_active",
            "user_id",
            postgresql_where="revoked_at IS NULL",
        ),
        {"schema": "kpa"},
    )


class JobStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class Employer(Base):
    """Employer organization — see spec §5 and the P2.0 design doc.

    Only the minimal subset needed before recruiter HTTP CRUD lands:
    name (canonical) + name_norm (idempotency key for seeding) + gst +
    verified_at. GSTIN format/checksum validation is a recruiter-side
    concern and not enforced here.
    """

    __tablename__ = "employers"

    id: Mapped[UuidPK]
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_norm: Mapped[str] = mapped_column(String(200), nullable=False)
    gst: Mapped[str | None] = mapped_column(String(15), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        Index(
            "ix_employers_name_norm_live",
            "name_norm",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        {"schema": "kpa"},
    )


class Job(Base):
    """Job posting — see spec §5 and the P2.0 design doc.

    Recruiter HTTP CRUD is out of scope for the current applicant-only
    P2/P3 cut; rows are populated by the seed CLI or future recruiter
    endpoints. No DB-level uniqueness on (employer_id, title) — real
    recruiters re-list roles with identical titles. Seeder idempotency
    is enforced at script level.
    """

    __tablename__ = "jobs"

    id: Mapped[UuidPK]
    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.employers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default="{}"
    )
    min_exp_years: Mapped[int] = mapped_column(Integer, nullable=False)
    max_exp_years: Mapped[int] = mapped_column(Integer, nullable=False)
    ctc_min: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    ctc_max: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(
            JobStatus,
            name="job_status",
            native_enum=True,
            schema="kpa",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=JobStatus.OPEN,
        server_default=JobStatus.OPEN.value,
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        Index(
            "ix_jobs_employer_id_live",
            "employer_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_jobs_status_posted_at_live",
            "status",
            text("posted_at DESC"),
            postgresql_where="deleted_at IS NULL",
        ),
        CheckConstraint(
            "max_exp_years >= min_exp_years",
            name="ck_jobs_exp_years_ordered",
        ),
        CheckConstraint(
            "ctc_max IS NULL OR ctc_min IS NULL OR ctc_max >= ctc_min",
            name="ck_jobs_ctc_ordered",
        ),
        {"schema": "kpa"},
    )
