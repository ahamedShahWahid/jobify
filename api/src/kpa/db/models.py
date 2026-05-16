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

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
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
        SAEnum(UserRole, name="user_role", native_enum=True, schema="kpa"),
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
