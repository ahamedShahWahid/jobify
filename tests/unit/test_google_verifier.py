"""Unit tests for JwksGoogleIdTokenVerifier — no real Google calls.

We use a small in-process httpx MockTransport to return canned JWKS payloads
and pyjwt to sign the ID tokens with a fresh RSA keypair, so we exercise the
real signature path without touching Google.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.utils import to_base64url_uint

from jobify.auth.google_verifier import (
    GoogleJwksUnavailableError,
    InvalidGoogleTokenError,
    JwksGoogleIdTokenVerifier,
)


def _make_keypair_and_jwks(kid: str) -> tuple[Any, dict[str, Any]]:
    """Return (private_key, jwks_dict) for signing test tokens."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "kid": kid,
                "n": to_base64url_uint(public_numbers.n).decode("ascii"),
                "e": to_base64url_uint(public_numbers.e).decode("ascii"),
            }
        ]
    }
    return private, jwks


def _sign_id_token(
    *,
    private_key: Any,
    kid: str,
    sub: str,
    aud: str,
    email: str,
    email_verified: bool = True,
    iss: str = "https://accounts.google.com",
    iat: int | None = None,
    exp: int | None = None,
) -> str:
    """Sign an ID token as Google would (RS256, JWK kid header)."""
    import jwt as pyjwt  # local import to keep test file lint-friendly

    now = int(time.time())
    payload = {
        "iss": iss,
        "sub": sub,
        "aud": aud,
        "email": email,
        "email_verified": email_verified,
        "iat": iat if iat is not None else now,
        "exp": exp if exp is not None else now + 3600,
        "name": "Test User",
    }
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pyjwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def jwks_url() -> str:
    return "https://example.test/jwks"


@pytest.fixture
def client_id() -> str:
    return "test-client.apps.googleusercontent.com"


def _build_verifier(jwks_url: str, client_id: str, transport: httpx.MockTransport):
    """Construct verifier with the test transport injected.

    The verifier exposes an `_http_factory` hook so tests can replace the
    httpx.AsyncClient with one bound to MockTransport.
    """

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, timeout=5.0)

    return JwksGoogleIdTokenVerifier(
        jwks_url=jwks_url,
        accepted_client_ids=[client_id],
        cache_ttl_seconds=3600,
        http_factory=factory,
    )


async def test_verify_happy_path(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="google-sub-123",
        aud=client_id,
        email="a@example.com",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == jwks_url
        return httpx.Response(200, json=jwks)

    transport = httpx.MockTransport(handler)
    v = _build_verifier(jwks_url, client_id, transport)

    claims = await v.verify(token)

    assert claims.sub == "google-sub-123"
    assert claims.email == "a@example.com"
    assert claims.aud == client_id
    assert claims.email_verified is True


async def test_verify_rejects_wrong_aud(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="x",
        aud="some-other-client.apps.googleusercontent.com",
        email="a@example.com",
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(InvalidGoogleTokenError, match="invalid_google_token"):
        await v.verify(token)


async def test_verify_rejects_wrong_iss(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="x",
        aud=client_id,
        email="a@example.com",
        iss="https://accounts.google.com.evil",
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(InvalidGoogleTokenError):
        await v.verify(token)


async def test_verify_rejects_expired_token(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="x",
        aud=client_id,
        email="a@example.com",
        iat=int(time.time()) - 7200,
        exp=int(time.time()) - 3600,
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(InvalidGoogleTokenError):
        await v.verify(token)


async def test_verify_rejects_unknown_kid(jwks_url: str, client_id: str) -> None:
    private, _jwks = _make_keypair_and_jwks(kid="key-1")
    # Token signed by key-1 but JWKS only returns key-2 → no matching key.
    _, other_jwks = _make_keypair_and_jwks(kid="key-2")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="x",
        aud=client_id,
        email="a@example.com",
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=other_jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(InvalidGoogleTokenError):
        await v.verify(token)


async def test_jwks_cache_is_reused_on_second_call(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="x",
        aud=client_id,
        email="a@example.com",
    )
    fetch_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetch_count
        fetch_count += 1
        return httpx.Response(200, json=jwks)

    transport = httpx.MockTransport(handler)
    v = _build_verifier(jwks_url, client_id, transport)

    await v.verify(token)
    await v.verify(token)
    assert fetch_count == 1


async def test_jwks_unavailable_raises(jwks_url: str, client_id: str) -> None:
    private, _jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="x",
        aud=client_id,
        email="a@example.com",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(GoogleJwksUnavailableError):
        await v.verify(token)


async def test_verify_accepts_aud_as_array(jwks_url: str, client_id: str) -> None:
    """Google sometimes issues tokens with `aud` as a JSON array. We must accept it."""
    private, jwks = _make_keypair_and_jwks(kid="key-1")

    import time as _time

    import jwt as pyjwt

    now = int(_time.time())
    payload = {
        "iss": "https://accounts.google.com",
        "sub": "g-array-aud",
        "aud": [client_id],  # array form
        "email": "a@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 3600,
        "name": "A",
    }
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token = pyjwt.encode(payload, pem, algorithm="RS256", headers={"kid": "key-1"})

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    claims = await v.verify(token)

    assert claims.aud == client_id
    assert isinstance(claims.aud, str)


async def test_jwks_empty_keys_with_cold_cache_raises(jwks_url: str, client_id: str) -> None:
    """A 200 OK with keys=[] when no cache exists must raise GoogleJwksUnavailableError."""
    private, _jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private,
        kid="key-1",
        sub="x",
        aud=client_id,
        email="a@example.com",
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"keys": []}))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(GoogleJwksUnavailableError):
        await v.verify(token)
