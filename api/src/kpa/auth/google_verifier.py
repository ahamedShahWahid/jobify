"""Google ID-token verification — Protocol + JWKS-backed impl.

Production uses :class:`JwksGoogleIdTokenVerifier`, which fetches Google's
JWKS, caches the keys in-process, and validates RS256 signatures + iss/aud/exp
claims via PyJWT. Tests use a fake (see ``tests/integration/conftest.py``).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

import httpx
import jwt as pyjwt
import structlog
from fastapi import Request

_GOOGLE_ISSUERS: Final[frozenset[str]] = frozenset(
    {"accounts.google.com", "https://accounts.google.com"}
)
_log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GoogleClaims:
    """Validated subset of a Google ID token's claims."""

    sub: str
    iss: str
    aud: str
    email: str
    email_verified: bool
    name: str | None


class InvalidGoogleTokenError(Exception):
    """Raised when an ID token fails any verification check.

    Always carries the slug ``invalid_google_token`` so callers map it to a
    uniform 401 problem+json.
    """

    def __init__(self) -> None:
        super().__init__("invalid_google_token")


class GoogleJwksUnavailableError(Exception):
    """Raised when JWKS fetch fails and there's no usable cached entry."""

    def __init__(self) -> None:
        super().__init__("google_jwks_unavailable")


class GoogleIdTokenVerifier(Protocol):
    """Async verifier: token → :class:`GoogleClaims` or raises."""

    async def verify(self, id_token: str) -> GoogleClaims: ...


class JwksGoogleIdTokenVerifier:
    """JWKS-backed verifier. Single instance per uvicorn worker."""

    def __init__(
        self,
        *,
        jwks_url: str,
        accepted_client_ids: list[str],
        cache_ttl_seconds: int,
        http_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._jwks_url = jwks_url
        self._accepted_audiences = list(accepted_client_ids)
        self._cache_ttl_seconds = cache_ttl_seconds
        self._http_factory = http_factory or (lambda: httpx.AsyncClient(timeout=5.0))
        self._lock = asyncio.Lock()
        self._cache_keys: dict[str, dict[str, Any]] = {}  # kid → jwk
        self._cache_fetched_at: float = 0.0

    async def verify(self, id_token: str) -> GoogleClaims:
        try:
            unverified_header = pyjwt.get_unverified_header(id_token)
        except pyjwt.PyJWTError as exc:
            raise InvalidGoogleTokenError() from exc

        kid = unverified_header.get("kid")
        if not kid:
            raise InvalidGoogleTokenError()

        key = await self._get_signing_key(kid)
        if key is None:
            raise InvalidGoogleTokenError()

        try:
            claims = pyjwt.decode(
                id_token,
                key=key,
                algorithms=["RS256"],
                audience=self._accepted_audiences,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
        except pyjwt.PyJWTError as exc:
            raise InvalidGoogleTokenError() from exc

        if claims["iss"] not in _GOOGLE_ISSUERS:
            raise InvalidGoogleTokenError()

        email = claims.get("email")
        if not isinstance(email, str) or not email:
            raise InvalidGoogleTokenError()

        raw_aud = claims["aud"]
        if isinstance(raw_aud, list):
            if not raw_aud:
                raise InvalidGoogleTokenError()
            aud_str = raw_aud[0]
        else:
            aud_str = raw_aud
        if not isinstance(aud_str, str):
            raise InvalidGoogleTokenError()

        return GoogleClaims(
            sub=claims["sub"],
            iss=claims["iss"],
            aud=aud_str,
            email=email,
            email_verified=bool(claims.get("email_verified", False)),
            name=claims.get("name") if isinstance(claims.get("name"), str) else None,
        )

    async def _get_signing_key(self, kid: str) -> Any | None:
        """Return the PyJWT-compatible signing key for ``kid``, refreshing if needed."""
        now = time.time()
        async with self._lock:
            if (
                self._cache_keys
                and now - self._cache_fetched_at < self._cache_ttl_seconds
                and kid in self._cache_keys
            ):
                return _jwk_to_pyjwt_key(self._cache_keys[kid])
            # Cache cold, expired, or missing this kid — refetch.
            await self._refetch_locked()
            jwk = self._cache_keys.get(kid)
        return _jwk_to_pyjwt_key(jwk) if jwk else None

    async def _refetch_locked(self) -> None:
        """Fetch JWKS and replace the cache. Lock must be held by caller."""
        try:
            async with self._http_factory() as client:
                resp = await client.get(self._jwks_url)
                resp.raise_for_status()
                body = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            _log.warning("jwks-fetch-failed", url=self._jwks_url, error=str(exc))
            if self._cache_keys:
                # Serve stale on transient failure.
                return
            raise GoogleJwksUnavailableError() from exc

        keys = body.get("keys") if isinstance(body, dict) else None
        if not isinstance(keys, list):
            raise GoogleJwksUnavailableError()

        new_keys = {k["kid"]: k for k in keys if isinstance(k, dict) and "kid" in k}
        if not new_keys:
            # Refuse to downgrade a warm cache. If we never had a cache,
            # this is a genuine "JWKS unavailable" state.
            _log.warning(
                "jwks-fetch-empty",
                url=self._jwks_url,
                had_cached_keys=bool(self._cache_keys),
            )
            if self._cache_keys:
                return
            raise GoogleJwksUnavailableError()

        self._cache_keys = new_keys
        self._cache_fetched_at = time.time()


def _jwk_to_pyjwt_key(jwk: dict[str, Any]) -> Any:
    """Convert a JWKS ``keys[]`` entry to a PyJWT-compatible RSA public key."""
    return pyjwt.algorithms.RSAAlgorithm.from_jwk(jwk)


def get_google_verifier(request: Request) -> GoogleIdTokenVerifier:
    """FastAPI dependency: pull the verifier off ``app.state``.

    Tests override this via ``app.dependency_overrides[get_google_verifier]``.
    """
    verifier: GoogleIdTokenVerifier = request.app.state.google_verifier
    return verifier
