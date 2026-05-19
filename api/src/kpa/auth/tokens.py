"""Token primitives — HS256 access JWT + opaque rotating refresh.

Pure functions over PyJWT + secrets + hashlib. No DB, no network.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any, Final
from uuid import UUID, uuid4

import jwt as pyjwt

_ISSUER: Final[str] = "kpa-api"
_ALG: Final[str] = "HS256"
_IAT_SKEW_SECONDS: Final[int] = 30


class AccessTokenError(Exception):
    """Raised on any access-token validation failure.

    The message is always the slug "invalid_access_token" — callers convert
    this to a 401 problem+json. We never leak the underlying PyJWT exception
    to avoid distinguishing signature failures from claim failures (timing
    oracle).
    """

    def __init__(self) -> None:
        super().__init__("invalid_access_token")


def mint_access_token(
    *,
    user_id: UUID,
    role: str,
    secret: str,
    ttl_seconds: int,
) -> str:
    """Mint an HS256 access JWT with the standard KPA claims."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": _ISSUER,
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid4()),
    }
    return pyjwt.encode(payload, secret, algorithm=_ALG)


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    """Decode + validate an access JWT.

    Raises :class:`AccessTokenError` on any failure (signature, iss, exp, iat skew).
    """
    try:
        claims = pyjwt.decode(
            token,
            secret,
            algorithms=[_ALG],
            issuer=_ISSUER,
            options={
                "require": ["iss", "sub", "role", "iat", "exp", "jti"],
                "verify_iat": False,  # we check iat skew manually below
            },
        )
    except pyjwt.PyJWTError as exc:
        raise AccessTokenError() from exc

    # PyJWT leeway would relax exp too; check iat skew manually instead.
    now = int(time.time())
    if claims["iat"] > now + _IAT_SKEW_SECONDS:
        raise AccessTokenError()

    return claims


def mint_refresh_token() -> str:
    """Generate a fresh opaque refresh token.

    32 bytes of entropy → base64url with '=' padding stripped → 43 chars.
    Hash before storing; never persist the raw value.
    """
    raw = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def sha256_token_hash(token: str) -> str:
    """SHA-256 hex digest of the token string.

    sha256 (not bcrypt) is intentional: the input is 256-bit random, so we
    don't need work-factor slowdown or per-row salts — entropy already
    prevents brute-force.
    """
    return hashlib.sha256(token.encode("ascii")).hexdigest()
