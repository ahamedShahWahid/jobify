"""Wire shapes for the application endpoints.

Kept separate from the handler logic in ``applications.py`` so the request/response
contracts read on their own. ``ApplicationListItem`` composes the shared
``JobRead`` / ``EmployerRead`` from ``routes.schemas``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from jobify_api.routes.schemas import EmployerRead, JobRead


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    status: str  # "applied" | "withdrawn"
    source: str
    created_at: datetime
    updated_at: datetime


class ApplicationListItem(BaseModel):
    application: ApplicationRead
    job: JobRead
    employer: EmployerRead


class ApplicationListResponse(BaseModel):
    items: list[ApplicationListItem]
    next_cursor: str | None


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "feed"


class WithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str  # must be "withdrawn"
