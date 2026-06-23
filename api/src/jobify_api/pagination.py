"""Opaque cursor + weak-ETag helpers shared by the paginated list routes.

Cursors are base64(JSON) of a small payload — no server state. Each route
module keeps a typed wrapper that owns its payload keys and ordering
semantics; the encoding, decoding and malformed-input contract live here so
a future cross-cutting change (e.g. signing cursors) is one edit, not six.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Any


def encode_cursor(payload: dict[str, Any]) -> str:
    """Pack a JSON-serializable payload into an opaque base64 string."""
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode an opaque cursor. Raises ValueError on any malformed input."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError(f"invalid_cursor: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid_cursor: payload is not an object")
    return payload


def make_weak_etag(*parts: object) -> str:
    """W/\"<sha256-hex>\" of str-rendered parts joined by '|'.

    Weak ETag because the body is computed from joined data — we promise
    semantic equivalence, not byte-exact reproducibility.
    """
    raw = "|".join(str(p) for p in parts)
    return f'W/"{hashlib.sha256(raw.encode("utf-8")).hexdigest()}"'
