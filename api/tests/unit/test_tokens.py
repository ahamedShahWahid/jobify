"""Unit tests for jobify.auth.tokens — pure crypto helpers, no DB / no network."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest

from jobify.auth.tokens import (
    AccessTokenError,
    decode_access_token,
    mint_access_token,
    mint_refresh_token,
    sha256_token_hash,
)

_SECRET = "x" * 32
_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_mint_access_token_roundtrip_preserves_claims() -> None:
    token = mint_access_token(user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=600)
    claims = decode_access_token(token, secret=_SECRET)

    assert claims["sub"] == str(_USER_ID)
    assert claims["role"] == "applicant"
    assert claims["iss"] == "jobify-api"
    assert isinstance(claims["jti"], str) and len(claims["jti"]) == 36
    assert claims["exp"] - claims["iat"] == 600


def test_mint_access_token_includes_iat_and_exp() -> None:
    now = int(time.time())
    token = mint_access_token(user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=600)
    claims = decode_access_token(token, secret=_SECRET)
    # Allow 5s of slack for clock drift between mint and assertion.
    assert abs(claims["iat"] - now) <= 5
    assert claims["exp"] == claims["iat"] + 600


def test_decode_rejects_wrong_secret() -> None:
    token = mint_access_token(user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=600)
    with pytest.raises(AccessTokenError, match="invalid_access_token"):
        decode_access_token(token, secret="y" * 32)


def test_decode_rejects_expired_token() -> None:
    # Mint a token that was valid for 1 second; wait briefly to expire.
    token = mint_access_token(user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=1)
    time.sleep(2)
    with pytest.raises(AccessTokenError, match="invalid_access_token"):
        decode_access_token(token, secret=_SECRET)


def test_decode_rejects_bad_issuer() -> None:
    # Forge a token with the right secret but a wrong iss claim.
    payload = {
        "iss": "evil-api",
        "sub": str(_USER_ID),
        "role": "applicant",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "jti": str(uuid4()),
    }
    forged = pyjwt.encode(payload, _SECRET, algorithm="HS256")
    with pytest.raises(AccessTokenError, match="invalid_access_token"):
        decode_access_token(forged, secret=_SECRET)


def test_decode_rejects_missing_role() -> None:
    """Defence in depth: a forged token missing `role` must be rejected."""
    payload = {
        "iss": "jobify-api",
        "sub": str(_USER_ID),
        # role intentionally omitted
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "jti": str(uuid4()),
    }
    forged = pyjwt.encode(payload, _SECRET, algorithm="HS256")
    with pytest.raises(AccessTokenError):
        decode_access_token(forged, secret=_SECRET)


def test_decode_accepts_30s_iat_skew() -> None:
    """Tokens with iat up to 30s in the future are accepted."""
    payload = {
        "iss": "jobify-api",
        "sub": str(_USER_ID),
        "role": "applicant",
        "iat": int(time.time()) + 30,
        "exp": int(time.time()) + 30 + 600,
        "jti": str(uuid4()),
    }
    token = pyjwt.encode(payload, _SECRET, algorithm="HS256")
    claims = decode_access_token(token, secret=_SECRET)
    assert claims["sub"] == str(_USER_ID)


def test_decode_rejects_iat_skew_beyond_window() -> None:
    """iat must be within 30s of now; 60s in the future is clearly over the limit."""
    payload = {
        "iss": "jobify-api",
        "sub": str(_USER_ID),
        "role": "applicant",
        "iat": int(time.time()) + 60,
        "exp": int(time.time()) + 60 + 600,
        "jti": str(uuid4()),
    }
    token = pyjwt.encode(payload, _SECRET, algorithm="HS256")
    with pytest.raises(AccessTokenError):
        decode_access_token(token, secret=_SECRET)


def test_mint_refresh_token_is_high_entropy_and_base64url() -> None:
    t1 = mint_refresh_token()
    t2 = mint_refresh_token()

    # 32 random bytes → base64url with '=' padding stripped → 43 chars.
    assert len(t1) == 43
    assert t1 != t2  # vanishingly unlikely to collide
    # Only base64url alphabet:
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert set(t1) <= allowed


def test_sha256_token_hash_is_64_hex_chars() -> None:
    h = sha256_token_hash("any-string")
    assert len(h) == 64
    assert set(h) <= set("0123456789abcdef")


def test_sha256_token_hash_is_deterministic() -> None:
    assert sha256_token_hash("a") == sha256_token_hash("a")
    assert sha256_token_hash("a") != sha256_token_hash("b")
