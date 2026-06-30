"""Shared helpers for the admin sub-routers.

The ``{created_at, id}`` keyset-cursor pair is used by both the audit-log viewer
and the employer-verification list — kept here so neither sub-module owns it (a
duplicated copy would be the kind of drift ``api/CLAUDE.md`` warns about).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException

from jobify_api.pagination import decode_cursor, encode_cursor


def encode_admin_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    return encode_cursor({"c": created_at.isoformat(), "i": str(row_id)})


def decode_admin_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = decode_cursor(cursor)
        return datetime.fromisoformat(payload["c"]), uuid.UUID(payload["i"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid_cursor") from exc
