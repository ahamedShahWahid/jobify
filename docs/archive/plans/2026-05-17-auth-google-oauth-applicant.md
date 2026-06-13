# Auth — Google OAuth + access JWT + opaque refresh + GET /me (applicant slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship applicant-side Google sign-in end-to-end — `POST /v1/auth/oauth/google` (Google ID-token exchange → our access JWT + opaque refresh), `POST /v1/auth/refresh` (rotation + family-wide reuse detection), `POST /v1/auth/logout` (idempotent revoke), and `GET /v1/me` (current user + applicant payload).

**Architecture:** Client-driven ID-token flow (no backend OAuth redirect). Flutter SDK obtains a Google-signed ID token; backend verifies via Google's JWKS, upserts `users` + `applicants` + `oauth_identities`, and mints an HS256 access JWT plus an opaque rotating refresh token (sha256-hashed at rest, `family_id` for reuse detection). Auth dependency `current_user` re-fetches the user on every request — soft-deletes lock out within the access TTL.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic, PyJWT (HS256), httpx (JWKS), pyantic-settings, structlog.

**Spec ref:** `docs/superpowers/specs/2026-05-17-auth-google-oauth-applicant-design.md` (approved 2026-05-17).

---

## File structure after this plan

```
api/src/kpa/
  auth/                                NEW
    __init__.py                        re-exports
    google_verifier.py                 GoogleIdTokenVerifier (Protocol),
                                       JwksGoogleIdTokenVerifier (real impl),
                                       GoogleClaims, InvalidGoogleTokenError,
                                       GoogleJwksUnavailableError,
                                       get_google_verifier (FastAPI dep)
    tokens.py                          mint_access_token, decode_access_token,
                                       mint_refresh_token, sha256_token_hash
    service.py                         AuthService.sign_in_with_google, refresh, logout
                                       get_auth_service (FastAPI dep)
    dependencies.py                    current_user, optional_current_user,
                                       _extract_bearer_or_raise_401
  routes/
    auth.py                            NEW — POST /v1/auth/oauth/google, /refresh, /logout
    me.py                              NEW — GET /v1/me
  db/
    models.py                          APPEND — OAuthProvider, OAuthIdentity, RefreshToken
    migrations/versions/
      0003_oauth_identities_and_refresh_tokens.py   NEW

  settings.py                          APPEND — KPA_JWT_*, KPA_GOOGLE_*,
                                       KPA_AUTH_REQUIRE_EMAIL_VERIFIED
  app_factory.py                       Build JwksGoogleIdTokenVerifier;
                                       mount auth + me routers
  pyproject.toml                       Add pyjwt[crypto]; promote httpx to runtime
  .env.example                         New env vars

api/tests/
  unit/
    test_settings.py                   APPEND — JWT + Google client id validation
    test_tokens.py                     NEW
    test_google_verifier.py            NEW
  integration/
    conftest.py                        APPEND — FakeGoogleIdTokenVerifier +
                                       get_google_verifier override wiring
    test_auth_signin.py                NEW
    test_auth_refresh.py               NEW
    test_auth_logout.py                NEW
    test_me.py                         NEW

docs/
  IMPLEMENTATION_SPEC.md               EDIT §10 — /v1/auth/oauth/{provider}/callback
                                       → /v1/auth/oauth/google
api/README.md                          APPEND — auth env vars + auth section
```

---

## Task 1: Add dependencies — pyjwt + httpx (runtime)

**Files:**
- Modify: `api/pyproject.toml`

Two libraries:
- `pyjwt[crypto]` — HS256 sign/decode. The `[crypto]` extra installs the `cryptography` library, which is required if we later swap to RS256/EdDSA (one-line change).
- `httpx` — already a dev dep; promote to runtime so the JWKS fetcher can use it in production.

- [ ] **Step 1: Edit `pyproject.toml`**

In `[project].dependencies`, append (preserving alphabetical-by-eye ordering):

```toml
    "httpx>=0.27,<0.28",
    "pyjwt[crypto]>=2.9,<3",
```

In `[dependency-groups].dev`, remove the existing `"httpx>=0.27,<0.28"` line (it's now a runtime dep; keeping it in dev is harmless but misleading).

Final relevant section (for reference; preserve the rest):

```toml
dependencies = [
    "alembic>=1.14,<2",
    "anyio>=4,<5",
    "asyncpg>=0.30,<0.31",
    "fastapi>=0.115,<0.116",
    "httpx>=0.27,<0.28",
    "pydantic>=2.9,<3",
    "pydantic-settings>=2.5,<3",
    "pyjwt[crypto]>=2.9,<3",
    "python-multipart>=0.0.12,<0.1",
    "sqlalchemy[asyncio]>=2.0.36,<2.1",
    "structlog>=24.4,<25",
    "uvicorn[standard]>=0.32,<0.33",
]

[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<0.25",
    "mypy>=1.13,<2",
    "ruff>=0.7,<0.8",
]
```

- [ ] **Step 2: Sync deps**

```bash
cd api
uv sync
```

Expected: `uv.lock` updates. `pyjwt`, `cryptography` install. No errors.

- [ ] **Step 3: Verify imports**

```bash
uv run python -c "import jwt, httpx, cryptography; print('jwt:', jwt.__version__, 'httpx:', httpx.__version__, 'cryptography:', cryptography.__version__)"
```

Expected: prints three versions, no `ImportError`.

- [ ] **Step 4: Lint + tests still green**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"
```

All pass. No new test failures.

- [ ] **Step 5: Commit**

```bash
git add api/pyproject.toml api/uv.lock
git commit -m "$(cat <<'EOF'
chore(api): add pyjwt[crypto] runtime dep + promote httpx

pyjwt drives HS256 access-token signing/decoding for the auth plan.
The [crypto] extra bundles the cryptography lib so a future RS256/EdDSA
swap is a one-line change. httpx becomes a runtime dep because the
Google JWKS fetcher needs it in prod.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Settings extensions — JWT + Google + email-verified gate

**Files:**
- Modify: `api/src/kpa/settings.py`
- Modify: `api/tests/unit/test_settings.py`
- Modify: `api/.env.example`

Seven new env vars per the spec's Configuration table. Each is validated at boot; the app refuses to start on invalid input. Pattern matches existing settings (`db_url`, `allowed_resume_content_types`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_settings.py` (after the existing tests):

```python
def test_jwt_secret_rejects_short_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 31)  # 31 bytes — one short
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "abc.apps.googleusercontent.com",
    )
    with pytest.raises(ValidationError, match="jwt_secret must be at least 32"):
        Settings()


def test_jwt_secret_accepts_32_byte_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "abc.apps.googleusercontent.com",
    )
    s = Settings()
    assert s.jwt_secret == "x" * 32


def test_jwt_ttl_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = Settings()
    assert s.jwt_access_ttl_seconds == 600
    assert s.jwt_refresh_ttl_seconds == 2592000


def test_jwt_ttl_rejects_non_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_JWT_ACCESS_TTL_SECONDS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_google_oauth_client_ids_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "web.apps.googleusercontent.com , ios.apps.googleusercontent.com",
    )
    s = Settings()
    assert s.google_oauth_client_ids == [
        "web.apps.googleusercontent.com",
        "ios.apps.googleusercontent.com",
    ]


def test_google_oauth_client_ids_rejects_bad_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "notagoogleclient.example.com")
    with pytest.raises(ValidationError, match="apps.googleusercontent.com"):
        Settings()


def test_google_jwks_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = Settings()
    assert s.google_jwks_url == "https://www.googleapis.com/oauth2/v3/certs"


def test_auth_require_email_verified_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = Settings()
    assert s.auth_require_email_verified is False
```

At the top of the file, add (or append into existing imports) `ValidationError`:

```python
from pydantic import ValidationError
```

Above the new tests, add a private helper (or co-locate near the existing test that sets env vars):

```python
def _set_minimum_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum env vars required by Settings to construct successfully."""
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "abc.apps.googleusercontent.com",
    )
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
cd api
uv run pytest tests/unit/test_settings.py -v -k "jwt_secret or jwt_ttl or google_oauth_client_ids or google_jwks_url or auth_require"
```

Expected: all new tests fail with `AttributeError` (no `jwt_secret`, etc. on `Settings`) or `ValidationError` because the required field isn't declared.

- [ ] **Step 3: Implement**

Edit `src/kpa/settings.py`. Add fields below the existing ones in the `Settings` class:

```python
    # --- Auth / JWT ---
    jwt_secret: str = Field(..., description="HS256 signing secret. Must be at least 32 bytes.")
    jwt_access_ttl_seconds: int = Field(
        default=600,
        gt=0,
        description="Access token lifetime in seconds.",
    )
    jwt_refresh_ttl_seconds: int = Field(
        default=2592000,
        gt=0,
        description="Refresh token lifetime in seconds (default 30 days).",
    )

    # --- Google OAuth ---
    google_oauth_client_ids: list[str] | str = Field(
        ...,
        description=(
            "CSV of accepted Google OAuth Client IDs (one per platform: web/iOS/Android)."
            " An ID token whose `aud` matches any of these is accepted."
        ),
    )
    google_jwks_url: str = Field(
        default="https://www.googleapis.com/oauth2/v3/certs",
        description="Override for tests + offline dev.",
    )
    google_jwks_cache_ttl_seconds: int = Field(
        default=3600,
        gt=0,
        description="In-process JWKS cache lifetime in seconds.",
    )

    # --- Auth policy ---
    auth_require_email_verified: bool = Field(
        default=False,
        description=(
            "When true, reject Google sign-ins with email_verified=false."
            " Off by default; flippable via env."
        ),
    )
```

Add validators (below the existing `_split_csv` validator):

```python
    @field_validator("jwt_secret")
    @classmethod
    def _enforce_jwt_secret_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) < 32:
            raise ValueError("jwt_secret must be at least 32 bytes (use a cryptographically random secret)")
        return v

    @field_validator("google_oauth_client_ids", mode="before")
    @classmethod
    def _split_google_client_ids(cls, v: object) -> object:
        """Same CSV-parsing behavior as allowed_resume_content_types."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("google_oauth_client_ids")
    @classmethod
    def _enforce_google_client_id_suffix(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if not x.endswith(".apps.googleusercontent.com")]
        if bad:
            raise ValueError(
                f"google_oauth_client_ids must end in .apps.googleusercontent.com; bad entries: {bad}"
            )
        if not v:
            raise ValueError("google_oauth_client_ids must contain at least one entry")
        return v
```

- [ ] **Step 4: Update `.env.example`**

Append to `api/.env.example`:

```
# Auth / JWT
KPA_JWT_SECRET=replace-with-32+-byte-random-string-from-openssl-rand-base64-32
KPA_JWT_ACCESS_TTL_SECONDS=600
KPA_JWT_REFRESH_TTL_SECONDS=2592000

# Google OAuth — CSV of accepted client IDs (web, iOS, Android registered in GCP console)
KPA_GOOGLE_OAUTH_CLIENT_IDS=replace.apps.googleusercontent.com
KPA_GOOGLE_JWKS_URL=https://www.googleapis.com/oauth2/v3/certs
KPA_GOOGLE_JWKS_CACHE_TTL_SECONDS=3600

# Auth policy
KPA_AUTH_REQUIRE_EMAIL_VERIFIED=false
```

- [ ] **Step 5: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_settings.py -v
```

All settings tests pass.

- [ ] **Step 6: Update local `.env`**

The existing `api/.env` file is gitignored but used by `uv run --env-file=.env …`. The integration `client` fixture in `tests/conftest.py` (unit test client, no DB) also sets a fresh env via monkeypatch — that fixture needs the new required vars too. Update it:

Edit `tests/conftest.py` — append two more `monkeypatch.setenv` calls inside the `client` fixture:

```python
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )
```

And update your local `api/.env` file by hand to include the new vars (use real values — `openssl rand -base64 48 | tr -d '=' | head -c 64` for `KPA_JWT_SECRET`).

- [ ] **Step 7: Full unit suite + linters**

```bash
uv run pytest -v -m "not integration"
uv run ruff check src/ tests/
uv run mypy
```

All green.

- [ ] **Step 8: Commit**

```bash
git add api/src/kpa/settings.py api/tests/conftest.py api/tests/unit/test_settings.py api/.env.example
git commit -m "$(cat <<'EOF'
feat(api): add auth + Google OAuth settings with validation

Seven new KPA_ env vars: JWT secret + access/refresh TTLs, Google
client-ID allowlist, JWKS URL + cache TTL, and an email-verified
gate flag. Validators enforce a 32-byte JWT secret floor, the
.apps.googleusercontent.com suffix on client IDs, and >0 TTLs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Token primitives — sign/decode access JWT + opaque refresh

**Files:**
- Create: `api/src/kpa/auth/__init__.py`
- Create: `api/src/kpa/auth/tokens.py`
- Create: `api/tests/unit/test_tokens.py`

`tokens.py` owns the cryptographic primitives. It has no DB or network deps and is pure-functions-around-pyjwt — easy to unit-test.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tokens.py`:

```python
"""Unit tests for kpa.auth.tokens — pure crypto helpers, no DB / no network."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest

from kpa.auth.tokens import (
    AccessTokenError,
    decode_access_token,
    mint_access_token,
    mint_refresh_token,
    sha256_token_hash,
)


_SECRET = "x" * 32
_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_mint_access_token_roundtrip_preserves_claims() -> None:
    token = mint_access_token(
        user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=600
    )
    claims = decode_access_token(token, secret=_SECRET)

    assert claims["sub"] == str(_USER_ID)
    assert claims["role"] == "applicant"
    assert claims["iss"] == "kpa-api"
    assert isinstance(claims["jti"], str) and len(claims["jti"]) == 36
    assert claims["exp"] - claims["iat"] == 600


def test_mint_access_token_includes_iat_and_exp() -> None:
    now = int(time.time())
    token = mint_access_token(
        user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=600
    )
    claims = decode_access_token(token, secret=_SECRET)
    # Allow 5s of slack for clock drift between mint and assertion.
    assert abs(claims["iat"] - now) <= 5
    assert claims["exp"] == claims["iat"] + 600


def test_decode_rejects_wrong_secret() -> None:
    token = mint_access_token(
        user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=600
    )
    with pytest.raises(AccessTokenError, match="invalid_access_token"):
        decode_access_token(token, secret="y" * 32)


def test_decode_rejects_expired_token() -> None:
    # Mint a token that was valid for 1 second; wait briefly to expire.
    token = mint_access_token(
        user_id=_USER_ID, role="applicant", secret=_SECRET, ttl_seconds=1
    )
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


def test_decode_accepts_30s_iat_skew() -> None:
    """Tokens with iat up to 30s in the future are accepted."""
    payload = {
        "iss": "kpa-api",
        "sub": str(_USER_ID),
        "role": "applicant",
        "iat": int(time.time()) + 30,
        "exp": int(time.time()) + 30 + 600,
        "jti": str(uuid4()),
    }
    token = pyjwt.encode(payload, _SECRET, algorithm="HS256")
    claims = decode_access_token(token, secret=_SECRET)
    assert claims["sub"] == str(_USER_ID)


def test_decode_rejects_31s_iat_skew() -> None:
    payload = {
        "iss": "kpa-api",
        "sub": str(_USER_ID),
        "role": "applicant",
        "iat": int(time.time()) + 31,
        "exp": int(time.time()) + 31 + 600,
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
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
cd api
uv run pytest tests/unit/test_tokens.py -v
```

Expected: `ModuleNotFoundError: No module named 'kpa.auth'`.

- [ ] **Step 3: Implement**

Create `src/kpa/auth/__init__.py` (empty for now; will re-export at the end):

```python
"""Authentication package.

Owns the token lifecycle, Google ID-token verification, and the
``current_user`` FastAPI dependency. Domain rules live in :mod:`.service`.
"""
```

Create `src/kpa/auth/tokens.py`:

```python
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
            leeway=_IAT_SKEW_SECONDS,
            options={"require": ["iss", "sub", "iat", "exp", "jti"]},
        )
    except pyjwt.PyJWTError as exc:
        raise AccessTokenError() from exc

    # PyJWT's `leeway` only applies to `exp`/`nbf`; check `iat` ourselves.
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
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_tokens.py -v
```

All pass.

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/auth/__init__.py api/src/kpa/auth/tokens.py api/tests/unit/test_tokens.py
git commit -m "$(cat <<'EOF'
feat(api): add token primitives — HS256 access JWT + opaque refresh

mint_access_token / decode_access_token wrap PyJWT with our claim
shape (iss=kpa-api, sub, role, iat, exp, jti) and a 30s iat-skew
tolerance. mint_refresh_token produces 256-bit base64url strings;
sha256_token_hash is what we persist in kpa.refresh_tokens later.

Decode failures collapse to a single AccessTokenError with the
slug "invalid_access_token" — distinguishing signature from claim
failures would leak a timing oracle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Google ID-token verifier — Protocol + JWKS impl + FastAPI dep

**Files:**
- Create: `api/src/kpa/auth/google_verifier.py`
- Create: `api/tests/unit/test_google_verifier.py`

The Protocol is the seam — production uses `JwksGoogleIdTokenVerifier` (fetches Google's JWKS, caches, validates signatures); tests use a fake (Task 8). The route layer never imports the concrete class — it always goes through the Protocol via `Depends(get_google_verifier)`.

JWKS caching is in-process. Each uvicorn worker maintains its own — fine for our scale (Google's JWKS is small and rotates ~daily; one cache miss per worker per hour is negligible).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_google_verifier.py`:

```python
"""Unit tests for JwksGoogleIdTokenVerifier — no real Google calls.

We use a small in-process httpx MockTransport to return canned JWKS payloads
and pyjwt to sign the ID tokens with a fresh RSA keypair, so we exercise the
real signature path without touching Google.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.utils import to_base64url_uint

from kpa.auth.google_verifier import (
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
        private_key=private, kid="key-1", sub="google-sub-123",
        aud=client_id, email="a@example.com",
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
        private_key=private, kid="key-1", sub="x",
        aud="some-other-client.apps.googleusercontent.com", email="a@example.com",
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(InvalidGoogleTokenError, match="invalid_google_token"):
        await v.verify(token)


async def test_verify_rejects_wrong_iss(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private, kid="key-1", sub="x",
        aud=client_id, email="a@example.com",
        iss="https://accounts.google.com.evil",
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(InvalidGoogleTokenError):
        await v.verify(token)


async def test_verify_rejects_expired_token(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private, kid="key-1", sub="x",
        aud=client_id, email="a@example.com",
        iat=int(time.time()) - 7200, exp=int(time.time()) - 3600,
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
        private_key=private, kid="key-1", sub="x",
        aud=client_id, email="a@example.com",
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=other_jwks))
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(InvalidGoogleTokenError):
        await v.verify(token)


async def test_jwks_cache_is_reused_on_second_call(jwks_url: str, client_id: str) -> None:
    private, jwks = _make_keypair_and_jwks(kid="key-1")
    token = _sign_id_token(
        private_key=private, kid="key-1", sub="x",
        aud=client_id, email="a@example.com",
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
        private_key=private, kid="key-1", sub="x",
        aud=client_id, email="a@example.com",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    v = _build_verifier(jwks_url, client_id, transport)

    with pytest.raises(GoogleJwksUnavailableError):
        await v.verify(token)
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
uv run pytest tests/unit/test_google_verifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'kpa.auth.google_verifier'`.

- [ ] **Step 3: Implement**

Create `src/kpa/auth/google_verifier.py`:

```python
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

        return GoogleClaims(
            sub=claims["sub"],
            iss=claims["iss"],
            aud=claims["aud"],
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

        self._cache_keys = {
            k["kid"]: k for k in keys if isinstance(k, dict) and "kid" in k
        }
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
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_google_verifier.py -v
```

All pass.

- [ ] **Step 5: Lint + types + full unit suite**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"
```

All green.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/auth/google_verifier.py api/tests/unit/test_google_verifier.py
git commit -m "$(cat <<'EOF'
feat(api): add Google ID-token verifier (Protocol + JWKS impl)

JwksGoogleIdTokenVerifier fetches Google's JWKS, caches keys
in-process for KPA_GOOGLE_JWKS_CACHE_TTL_SECONDS, and validates
RS256 signatures + iss/aud/exp via PyJWT. Returns a GoogleClaims
dataclass. The Protocol seam lets tests inject a fake without
touching Google.

Unit tests use httpx.MockTransport + an in-process RSA keypair
to exercise the real signature path with zero network.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Models — OAuthProvider enum + OAuthIdentity + RefreshToken

**Files:**
- Modify: `api/src/kpa/db/models.py`

Two new tables, one new enum. Reuses the existing `UuidPK` / `CreatedAt` / `UpdatedAt` / `DeletedAt` annotated types where applicable. `refresh_tokens` deliberately diverges from the soft-delete pattern (see the spec) — no `deleted_at`; uses `revoked_at` + `revocation_reason` instead.

- [ ] **Step 1: Append to `models.py`**

Add to the imports block at the top (alongside existing imports):

```python
from sqlalchemy import CHAR
```

Append at the bottom of the file:

```python
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
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd api
uv run python -c "from kpa.db.models import OAuthProvider, OAuthIdentity, RefreshToken; print(OAuthIdentity.__tablename__, RefreshToken.__tablename__, list(OAuthProvider))"
```

Expected: `oauth_identities refresh_tokens [<OAuthProvider.GOOGLE: 'google'>]`. No errors.

- [ ] **Step 3: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean.

- [ ] **Step 4: Commit**

```bash
git add api/src/kpa/db/models.py
git commit -m "$(cat <<'EOF'
feat(api): add OAuthIdentity + RefreshToken models

OAuthIdentity is M:1 to users so a single account can link
google/apple/phone identities later without schema migration.
Partial unique index on (provider, provider_subject) WHERE
deleted_at IS NULL.

RefreshToken deliberately diverges from soft-delete: no
deleted_at, uses revoked_at + revocation_reason instead. The
token_hash index is NOT partial — we want to find revoked rows
so reuse detection can revoke the whole family_id.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Migration 0003 — `oauth_identities` + `refresh_tokens`

**Files:**
- Create: `api/src/kpa/db/migrations/versions/0003_oauth_identities_and_refresh_tokens.py`

Hand-written, like 0001 and 0002. Creates the enum, both tables, and all indexes; downgrade is the reverse.

- [ ] **Step 1: Generate a revision file**

```bash
cd api
uv run --env-file=.env alembic revision -m "oauth_identities and refresh_tokens"
```

Note the generated filename (e.g., `<hash>_oauth_identities_and_refresh_tokens.py`) — we'll rename it to `0003_oauth_identities_and_refresh_tokens.py` for consistency with `0001_...` / `0002_...`.

```bash
mv src/kpa/db/migrations/versions/<generated-hash>_oauth_identities_and_refresh_tokens.py \
   src/kpa/db/migrations/versions/0003_oauth_identities_and_refresh_tokens.py
```

- [ ] **Step 2: Write the migration body**

Replace the file's contents with:

```python
"""oauth_identities and refresh_tokens

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17

Adds:
- kpa.oauth_provider enum
- kpa.oauth_identities (M:1 to users; supports future apple/phone identities)
- kpa.refresh_tokens (rotation + reuse detection)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE kpa.oauth_provider AS ENUM ('google')")

    op.create_table(
        "oauth_identities",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.dialects.postgresql.ENUM(
                "google",
                name="oauth_provider",
                schema="kpa",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email_at_link", sa.String(length=254), nullable=True),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        schema="kpa",
    )
    op.create_index(
        "ix_oauth_identities_provider_subject_live",
        "oauth_identities",
        ["provider", "provider_subject"],
        unique=True,
        schema="kpa",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_oauth_identities_user_id_live",
        "oauth_identities",
        ["user_id"],
        schema="kpa",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "family_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "replaced_by_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpa.refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        schema="kpa",
    )
    op.create_index(
        "ix_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
        schema="kpa",
    )
    op.create_index(
        "ix_refresh_tokens_family_id_active",
        "refresh_tokens",
        ["family_id"],
        schema="kpa",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_refresh_tokens_user_id_active",
        "refresh_tokens",
        ["user_id"],
        schema="kpa",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id_active", table_name="refresh_tokens", schema="kpa")
    op.drop_index("ix_refresh_tokens_family_id_active", table_name="refresh_tokens", schema="kpa")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens", schema="kpa")
    op.drop_table("refresh_tokens", schema="kpa")

    op.drop_index("ix_oauth_identities_user_id_live", table_name="oauth_identities", schema="kpa")
    op.drop_index("ix_oauth_identities_provider_subject_live", table_name="oauth_identities", schema="kpa")
    op.drop_table("oauth_identities", schema="kpa")

    op.execute("DROP TYPE IF EXISTS kpa.oauth_provider")
```

- [ ] **Step 3: Smoke-test upgrade + downgrade against local Postgres**

```bash
cd api
uv run --env-file=.env alembic upgrade head

PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\dt kpa.*"
# Expected: alembic_version, applicants, oauth_identities, refresh_tokens, resumes, users (6 tables).

PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\d kpa.oauth_identities"
# Expected: 10 columns. UNIQUE partial index on (provider, provider_subject) WHERE deleted_at IS NULL.
# FK to users with ON DELETE CASCADE.

PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\d kpa.refresh_tokens"
# Expected: 12 columns. UNIQUE index on token_hash. FK to users with ON DELETE CASCADE,
# self-FK on replaced_by_id with ON DELETE SET NULL.

PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c \
  "SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'oauth_provider') ORDER BY enumsortorder;"
# Expected: google.

uv run --env-file=.env alembic downgrade 0002
PGPASSWORD=kpa psql -h localhost -U kpa -d kpa -c "\dt kpa.*"
# Expected: 4 tables (oauth_identities + refresh_tokens gone).

# Restore head so subsequent tasks have the tables.
uv run --env-file=.env alembic upgrade head
```

If any check fails: fix the migration before continuing.

- [ ] **Step 4: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean (migrations dir is excluded from mypy).

- [ ] **Step 5: Commit**

```bash
git add api/src/kpa/db/migrations/versions/0003_oauth_identities_and_refresh_tokens.py
git commit -m "$(cat <<'EOF'
feat(api): add 0003 migration — oauth_identities + refresh_tokens

Creates kpa.oauth_provider enum (google only for now), the
oauth_identities table with partial unique index on (provider,
provider_subject) WHERE deleted_at IS NULL, and the refresh_tokens
table with a UNIQUE token_hash index plus two partial indexes for
family-wide revoke + active-session enumeration.

Round-trips cleanly (upgrade head → downgrade 0002 → upgrade head).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `current_user` dependency

**Files:**
- Create: `api/src/kpa/auth/dependencies.py`
- Create: `api/tests/unit/test_auth_dependencies.py`

Resolves the access JWT to a live `User` row, raising 401 problem+json on any failure. Always re-fetches from DB so soft-deletes lock the user out within the access TTL window. Pure-ASGI bearer extraction (we don't use `fastapi.security.HTTPBearer` because that helper writes its own error JSON shape, bypassing the RFC 7807 handler).

End-to-end exercise lands in Task 12 (`GET /v1/me` integration tests). This task covers only the bearer-extraction unit logic and ensures the module imports cleanly.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_auth_dependencies.py`:

```python
"""Unit tests for kpa.auth.dependencies — bearer extraction only.

Full current_user happy/sad paths live in tests/integration/test_me.py
(needs a real DB session).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from kpa.auth.dependencies import _extract_bearer_or_raise_401


def _request_with_headers(headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/me",
        "headers": headers,
        "state": {},
    }
    return Request(scope)  # type: ignore[arg-type]


def test_extract_bearer_returns_token_when_present() -> None:
    req = _request_with_headers([(b"authorization", b"Bearer abc.def.ghi")])
    assert _extract_bearer_or_raise_401(req) == "abc.def.ghi"


def test_extract_bearer_case_insensitive_scheme() -> None:
    req = _request_with_headers([(b"authorization", b"bearer abc.def.ghi")])
    assert _extract_bearer_or_raise_401(req) == "abc.def.ghi"


def test_extract_bearer_missing_header_raises_401() -> None:
    req = _request_with_headers([])
    with pytest.raises(HTTPException) as info:
        _extract_bearer_or_raise_401(req)
    assert info.value.status_code == 401
    assert info.value.detail == "missing_bearer_token"


def test_extract_bearer_wrong_scheme_raises_401() -> None:
    req = _request_with_headers([(b"authorization", b"Basic abc")])
    with pytest.raises(HTTPException) as info:
        _extract_bearer_or_raise_401(req)
    assert info.value.detail == "missing_bearer_token"


def test_extract_bearer_empty_token_raises_401() -> None:
    req = _request_with_headers([(b"authorization", b"Bearer ")])
    with pytest.raises(HTTPException) as info:
        _extract_bearer_or_raise_401(req)
    assert info.value.detail == "missing_bearer_token"
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
uv run pytest tests/unit/test_auth_dependencies.py -v
```

Expected: `ModuleNotFoundError: No module named 'kpa.auth.dependencies'`.

- [ ] **Step 3: Implement**

Create `src/kpa/auth/dependencies.py`:

```python
"""FastAPI dependencies for authenticated routes.

``current_user`` decodes the Bearer access JWT, re-fetches the user row, and
returns it. Routes use ``Depends(current_user)`` directly; tests inject a fake
via ``app.dependency_overrides[current_user] = lambda: fake_user``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import AccessTokenError, decode_access_token
from kpa.db.models import User
from kpa.db.session import get_session
from kpa.settings import Settings


def _extract_bearer_or_raise_401(request: Request) -> str:
    """Return the Bearer token string, or raise 401 missing_bearer_token."""
    raw = request.headers.get("authorization", "")
    parts = raw.split(" ", 1)
    if (
        len(parts) != 2
        or parts[0].lower() != "bearer"
        or not parts[1].strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
        )
    return parts[1].strip()


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Resolve the Bearer access JWT to a live ``User``.

    Re-fetches the user row on every call: a user soft-deleted N seconds ago
    is locked out within the access TTL (≤10 min), not the refresh TTL.
    """
    settings: Settings = request.app.state.settings
    token = _extract_bearer_or_raise_401(request)

    try:
        claims = decode_access_token(token, secret=settings.jwt_secret)
    except AccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_access_token",
        ) from exc

    try:
        user_id = UUID(claims["sub"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_access_token",
        ) from exc

    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_not_found",
        )

    request.state.current_user_id = user.id
    request.state.current_role = user.role.value
    return user


async def optional_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> User | None:
    """Like :func:`current_user` but returns ``None`` if no Authorization header."""
    if not request.headers.get("authorization"):
        return None
    return await current_user(request, session=session)
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_auth_dependencies.py -v
```

All pass.

- [ ] **Step 5: Lint + types + full unit suite**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"
```

All green.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/auth/dependencies.py api/tests/unit/test_auth_dependencies.py
git commit -m "$(cat <<'EOF'
feat(api): add current_user FastAPI dependency

Pure-ASGI Bearer extraction (no fastapi.security.HTTPBearer — that
helper writes its own JSON error shape that bypasses our RFC 7807
handler). 401 detail slugs: missing_bearer_token /
invalid_access_token / user_not_found.

current_user re-fetches the user row on every authenticated
request; soft-deletes lock out within the access TTL window.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Integration conftest — `FakeGoogleIdTokenVerifier` + dep wiring

**Files:**
- Modify: `api/tests/integration/conftest.py`

Adds:
1. A `FakeGoogleIdTokenVerifier` that maps opaque token strings to `GoogleClaims`.
2. A `google_verifier` fixture returning a fresh fake per test.
3. A version of the `async_client` (and `client`) fixture that **also** overrides `get_google_verifier` to return the fake.
4. The new env vars (KPA_JWT_SECRET, KPA_GOOGLE_OAUTH_CLIENT_IDS) in the env setup.

We modify the existing `async_client` and `client` fixtures rather than creating new ones — every integration test from here on needs the verifier override, and adding parallel fixtures would risk drift.

- [ ] **Step 1: Add the FakeGoogleIdTokenVerifier near the top of the file**

Below the imports in `tests/integration/conftest.py`, add:

```python
from dataclasses import dataclass

from kpa.auth.google_verifier import (
    GoogleClaims,
    GoogleIdTokenVerifier,
    InvalidGoogleTokenError,
    get_google_verifier,
)


@dataclass
class FakeGoogleIdTokenVerifier:
    """Test double: opaque token strings → canned :class:`GoogleClaims`.

    Use this via the ``google_verifier`` fixture; the integration ``client``
    and ``async_client`` fixtures override
    ``app.dependency_overrides[get_google_verifier]`` to return it.
    """

    canned: dict[str, GoogleClaims]

    async def verify(self, id_token: str) -> GoogleClaims:
        if id_token in self.canned:
            return self.canned[id_token]
        raise InvalidGoogleTokenError()


@pytest.fixture
def google_verifier() -> FakeGoogleIdTokenVerifier:
    """A fresh fake per test, with no canned tokens.

    Tests populate ``.canned`` to register their tokens, e.g.:

        google_verifier.canned["applicant_a_token"] = GoogleClaims(...)
    """
    return FakeGoogleIdTokenVerifier(canned={})
```

- [ ] **Step 2: Add env-var setup for JWT + Google to both client fixtures**

Inside each of the existing `client` and `async_client` fixtures, after the existing `monkeypatch.setenv` block (`KPA_ENV`, `KPA_SERVICE_NAME`, `KPA_DB_URL`, `KPA_STORAGE_ROOT`), append:

```python
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )
```

- [ ] **Step 3: Wire the verifier override into both client fixtures**

In each of `client` and `async_client`, **after** the existing `app.dependency_overrides[get_session] = _shared_session` line, change the signature to accept `google_verifier` and add the override:

```python
@pytest.fixture
def client(
    session: AsyncSession,
    db_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    google_verifier: FakeGoogleIdTokenVerifier,
) -> Iterator[TestClient]:
    # … existing env setup + monkeypatch.setenv …

    from kpa.app_factory import create_app
    from kpa.db.session import get_session

    app = create_app()

    async def _shared_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _shared_session
    app.dependency_overrides[get_google_verifier] = lambda: google_verifier

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
```

Do the same for `async_client` — accept the `google_verifier` fixture argument and add the same `dependency_overrides[get_google_verifier]` line right after the existing `get_session` override.

- [ ] **Step 4: Verify the fixtures compile**

```bash
cd api
uv run pytest tests/integration/ --collect-only -q 2>&1 | head -40
```

Expected: collection succeeds for existing integration tests, no `ImportError`. The new fixtures aren't exercised yet but they shouldn't break anything.

- [ ] **Step 5: Run the existing integration suite — should still pass**

```bash
uv run pytest -v -m integration
```

Expected: existing 16 integration tests still pass. The verifier override only fires when `get_google_verifier` is actually resolved, which today is never (no route uses it yet).

- [ ] **Step 6: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean.

- [ ] **Step 7: Commit**

```bash
git add api/tests/integration/conftest.py
git commit -m "$(cat <<'EOF'
test(api): add FakeGoogleIdTokenVerifier + integration dep wiring

Lays the foundation for auth route tests. FakeGoogleIdTokenVerifier
maps opaque token strings to canned GoogleClaims; the client +
async_client fixtures now also override get_google_verifier so
routes pull the fake out of app.state instead of hitting Google.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `POST /v1/auth/oauth/google` — sign in with Google ID token

**Files:**
- Create: `api/src/kpa/auth/service.py`
- Create: `api/src/kpa/routes/auth.py`
- Modify: `api/src/kpa/app_factory.py`
- Create: `api/tests/integration/test_auth_signin.py`

Where the moving parts meet. The route is a thin shim; `AuthService.sign_in_with_google` owns the orchestration: verify ID token → look up `(provider, provider_subject)` → either return the existing user or auto-provision `users` + `applicants` + `oauth_identities` → mint access JWT + opaque refresh.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_auth_signin.py`:

```python
"""Integration tests for POST /v1/auth/oauth/google."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select

from kpa.auth.google_verifier import GoogleClaims
from kpa.db.models import Applicant, OAuthIdentity, OAuthProvider, RefreshToken, User


def _claims(sub: str, email: str, name: str | None = "Test User", verified: bool = True) -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=verified,
        name=name,
    )


async def test_signin_creates_user_applicant_and_identity(
    async_client: httpx.AsyncClient,
    google_verifier,
    session,
) -> None:
    google_verifier.canned["new_user_tok"] = _claims(
        sub="google-sub-new", email="new@example.com", name="New Person"
    )

    resp = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "new_user_tok"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"access_token", "refresh_token", "token_type", "expires_in", "user"}
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 600
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["role"] == "applicant"
    assert body["user"]["is_new_user"] is True
    assert isinstance(body["user"]["applicant_id"], str)
    user_id = uuid.UUID(body["user"]["id"])

    # DB side-effects
    db_user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    assert db_user.email == "new@example.com"

    db_applicant = (
        await session.execute(select(Applicant).where(Applicant.user_id == user_id))
    ).scalar_one()
    assert db_applicant.full_name == "New Person"

    db_identity = (
        await session.execute(
            select(OAuthIdentity).where(OAuthIdentity.user_id == user_id)
        )
    ).scalar_one()
    assert db_identity.provider == OAuthProvider.GOOGLE
    assert db_identity.provider_subject == "google-sub-new"

    db_refresh = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id)
        )
    ).scalar_one()
    assert db_refresh.revoked_at is None


async def test_signin_returning_user_updates_last_seen(
    async_client: httpx.AsyncClient,
    google_verifier,
    session,
) -> None:
    google_verifier.canned["alice_tok"] = _claims(
        sub="google-sub-alice", email="alice@example.com", name="Alice"
    )

    first = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "alice_tok"}
    )
    assert first.status_code == 200
    user_id_1 = first.json()["user"]["id"]

    second = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "alice_tok"}
    )
    assert second.status_code == 200
    body2 = second.json()
    assert body2["user"]["id"] == user_id_1
    assert body2["user"]["is_new_user"] is False

    # Only one user / applicant / identity in DB.
    n_users = (await session.execute(select(User))).scalars().all()
    assert len(n_users) == 1
    n_idents = (await session.execute(select(OAuthIdentity))).scalars().all()
    assert len(n_idents) == 1
    # Two refresh tokens — one per sign-in.
    n_refresh = (await session.execute(select(RefreshToken))).scalars().all()
    assert len(n_refresh) == 2


async def test_signin_rejects_invalid_google_token(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    # No canned tokens registered → fake raises InvalidGoogleTokenError.
    resp = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "garbage"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_google_token"


async def test_signin_email_collision_returns_409(
    async_client: httpx.AsyncClient,
    google_verifier,
) -> None:
    # First Google account with email a@example.com lands successfully.
    google_verifier.canned["acct_a_tok"] = _claims(
        sub="google-sub-A", email="a@example.com", name="A"
    )
    first = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "acct_a_tok"}
    )
    assert first.status_code == 200

    # A different Google sub but the same email → 409.
    google_verifier.canned["acct_b_tok"] = _claims(
        sub="google-sub-B", email="a@example.com", name="A doppelganger"
    )
    second = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "acct_b_tok"}
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "email_belongs_to_other_user"
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
cd api
uv run pytest tests/integration/test_auth_signin.py -v
```

Expected: 404 errors (route doesn't exist yet) or import errors.

- [ ] **Step 3: Implement the AuthService**

Create `src/kpa/auth/service.py`:

```python
"""AuthService — orchestrates sign-in, refresh, and logout.

Per-request: built by :func:`get_auth_service` over the request's AsyncSession,
the app-scoped Google verifier, and Settings. Service methods raise
``HTTPException`` directly (matching the codebase's existing pattern in
``routes/resumes.py``); routes are thin pass-throughs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.google_verifier import (
    GoogleClaims,
    GoogleIdTokenVerifier,
    GoogleJwksUnavailableError,
    InvalidGoogleTokenError,
    get_google_verifier,
)
from kpa.auth.tokens import (
    AccessTokenError,
    decode_access_token,
    mint_access_token,
    mint_refresh_token,
    sha256_token_hash,
)
from kpa.db.models import (
    Applicant,
    OAuthIdentity,
    OAuthProvider,
    RefreshToken,
    User,
    UserRole,
)
from kpa.db.session import get_session
from kpa.settings import Settings

_log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SignInResult:
    user: User
    applicant: Applicant
    access_token: str
    refresh_token: str
    expires_in: int
    is_new_user: bool


@dataclass(frozen=True)
class RefreshResult:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        verifier: GoogleIdTokenVerifier,
        settings: Settings,
    ) -> None:
        self._session = session
        self._verifier = verifier
        self._settings = settings

    async def sign_in_with_google(self, id_token: str) -> SignInResult:
        try:
            claims = await self._verifier.verify(id_token)
        except InvalidGoogleTokenError as exc:
            raise HTTPException(401, "invalid_google_token") from exc
        except GoogleJwksUnavailableError as exc:
            raise HTTPException(503, "google_jwks_unavailable") from exc

        if (
            self._settings.auth_require_email_verified
            and not claims.email_verified
        ):
            raise HTTPException(401, "email_not_verified")

        user, applicant, is_new_user = await self._upsert_identity(claims)

        access = mint_access_token(
            user_id=user.id,
            role=user.role.value,
            secret=self._settings.jwt_secret,
            ttl_seconds=self._settings.jwt_access_ttl_seconds,
        )
        refresh = await self._issue_refresh(user_id=user.id, family_id=uuid4())

        _log.info(
            "auth.signin",
            user_id=str(user.id),
            is_new_user=is_new_user,
            provider="google",
        )
        return SignInResult(
            user=user,
            applicant=applicant,
            access_token=access,
            refresh_token=refresh,
            expires_in=self._settings.jwt_access_ttl_seconds,
            is_new_user=is_new_user,
        )

    async def _upsert_identity(
        self, claims: GoogleClaims
    ) -> tuple[User, Applicant, bool]:
        """Return (user, applicant, is_new_user) for the given Google claims."""
        existing_ident = (
            await self._session.execute(
                select(OAuthIdentity).where(
                    OAuthIdentity.provider == OAuthProvider.GOOGLE,
                    OAuthIdentity.provider_subject == claims.sub,
                    OAuthIdentity.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if existing_ident is not None:
            user = await self._session.get(User, existing_ident.user_id)
            assert user is not None and user.deleted_at is None  # FK + filter invariant
            user.email = claims.email
            existing_ident.last_seen_at = datetime.now(UTC)
            applicant = (
                await self._session.execute(
                    select(Applicant).where(Applicant.user_id == user.id)
                )
            ).scalar_one()
            await self._session.flush()
            return user, applicant, False

        # New identity. Email collision check first.
        collision = (
            await self._session.execute(
                select(User).where(
                    User.email == claims.email, User.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if collision is not None:
            raise HTTPException(409, "email_belongs_to_other_user")

        user = User(
            email=claims.email,
            phone=None,
            role=UserRole.APPLICANT,
            mfa_enabled=False,
        )
        self._session.add(user)
        await self._session.flush()  # populates user.id

        applicant = Applicant(
            user_id=user.id,
            full_name=claims.name or claims.email.split("@", 1)[0],
        )
        self._session.add(applicant)

        identity = OAuthIdentity(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_subject=claims.sub,
            email_at_link=claims.email,
        )
        self._session.add(identity)
        await self._session.flush()
        return user, applicant, True

    async def _issue_refresh(self, *, user_id: UUID, family_id: UUID) -> str:
        """Mint + persist a refresh token. Returns the opaque string."""
        token = mint_refresh_token()
        now = datetime.now(UTC)
        row = RefreshToken(
            user_id=user_id,
            family_id=family_id,
            token_hash=sha256_token_hash(token),
            issued_at=now,
            expires_at=now + timedelta(seconds=self._settings.jwt_refresh_ttl_seconds),
        )
        self._session.add(row)
        await self._session.flush()
        return token


def get_auth_service(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    verifier: GoogleIdTokenVerifier = Depends(get_google_verifier),  # noqa: B008
) -> AuthService:
    return AuthService(
        session=session,
        verifier=verifier,
        settings=request.app.state.settings,
    )
```

- [ ] **Step 4: Implement the route**

Create `src/kpa/routes/auth.py`:

```python
"""Auth routes — Google sign-in, refresh, logout.

Per spec §10 and the auth design doc. ``POST /v1/auth/oauth/google`` replaces
the spec's literal ``/callback`` endpoint because the flow is client-driven
ID-token exchange.

TODO(infra): per-IP and per-user rate limiting (spec §9.3) — requires Redis,
deferred to the P3 / observability plan.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from kpa.auth.service import AuthService, get_auth_service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class GoogleSignInRequest(BaseModel):
    id_token: str = Field(..., min_length=1)


class SignInUser(BaseModel):
    id: UUID
    email: str
    role: str
    applicant_id: UUID
    is_new_user: bool


class SignInResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: SignInUser


@router.post(
    "/oauth/google",
    response_model=SignInResponse,
    status_code=status.HTTP_200_OK,
)
async def sign_in_with_google(
    payload: GoogleSignInRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> SignInResponse:
    result = await service.sign_in_with_google(payload.id_token)
    return SignInResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        user=SignInUser(
            id=result.user.id,
            email=result.user.email or "",
            role=result.user.role.value,
            applicant_id=result.applicant.id,
            is_new_user=result.is_new_user,
        ),
    )
```

- [ ] **Step 5: Wire the router + the Google verifier into `app_factory.py`**

Edit `src/kpa/app_factory.py`:

Add imports near the existing ones:

```python
from kpa.auth.google_verifier import JwksGoogleIdTokenVerifier
from kpa.routes import auth
```

In `create_app()`, **before** the `app.add_middleware(...)` line, build the verifier and stash it:

```python
    app.state.google_verifier = JwksGoogleIdTokenVerifier(
        jwks_url=settings.google_jwks_url,
        accepted_client_ids=(
            settings.google_oauth_client_ids
            if isinstance(settings.google_oauth_client_ids, list)
            else [settings.google_oauth_client_ids]
        ),
        cache_ttl_seconds=settings.google_jwks_cache_ttl_seconds,
    )
```

Add the auth router include alongside the others:

```python
    app.include_router(auth.router)
```

- [ ] **Step 6: Run the new tests**

```bash
uv run pytest tests/integration/test_auth_signin.py -v
```

All four pass. If `test_signin_email_collision_returns_409` fails, the most likely cause is forgetting the `.deleted_at.is_(None)` filter in the email-collision query (it would also match soft-deleted users and never reach the happy path).

- [ ] **Step 7: Full pipeline**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"
uv run pytest -v -m integration
```

All green.

- [ ] **Step 8: Commit**

```bash
git add api/src/kpa/auth/service.py api/src/kpa/routes/auth.py api/src/kpa/app_factory.py api/tests/integration/test_auth_signin.py
git commit -m "$(cat <<'EOF'
feat(api): POST /v1/auth/oauth/google signs in with Google ID token

Client-driven flow: Flutter SDK gets an ID token, posts it here.
AuthService.sign_in_with_google verifies via the JWKS verifier,
looks up (provider, sub) in oauth_identities, and either updates
last_seen_at on the returning row or auto-provisions a fresh
users + applicants + oauth_identities triple.

Same email under a different Google sub → 409
email_belongs_to_other_user. We never silently merge in MVP.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `POST /v1/auth/refresh` — rotation + reuse detection

**Files:**
- Modify: `api/src/kpa/auth/service.py`
- Modify: `api/src/kpa/routes/auth.py`
- Create: `api/tests/integration/test_auth_refresh.py`

The trickiest task. Rotation must be atomic; reuse must revoke the whole family; a concurrent-refresh race must produce exactly one winner. We use a `SELECT … FOR UPDATE` on the refresh row to serialize concurrent calls on the same token.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_auth_refresh.py`:

```python
"""Integration tests for POST /v1/auth/refresh — rotation + reuse detection."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from kpa.auth.google_verifier import GoogleClaims
from kpa.auth.tokens import sha256_token_hash
from kpa.db.models import RefreshToken


def _claims() -> GoogleClaims:
    return GoogleClaims(
        sub="google-sub-1",
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email="alice@example.com",
        email_verified=True,
        name="Alice",
    )


async def _sign_in(client: httpx.AsyncClient, google_verifier, token_tag: str = "tok") -> dict:
    google_verifier.canned[token_tag] = _claims()
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": token_tag})
    assert resp.status_code == 200
    return resp.json()


async def test_refresh_rotates_token(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    first = await _sign_in(async_client, google_verifier)
    refresh1 = first["refresh_token"]

    resp = await async_client.post(
        "/v1/auth/refresh", json={"refresh_token": refresh1}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["refresh_token"] != refresh1
    refresh2 = body["refresh_token"]

    # Old token row is revoked, replaced_by_id points at the new row.
    rows = (await session.execute(select(RefreshToken).order_by(RefreshToken.issued_at))).scalars().all()
    assert len(rows) == 2
    old, new = rows
    assert old.revoked_at is not None
    assert old.revocation_reason == "rotated"
    assert old.replaced_by_id == new.id
    assert new.revoked_at is None
    assert old.family_id == new.family_id


async def test_refresh_reuse_revokes_whole_family(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    first = await _sign_in(async_client, google_verifier)
    refresh1 = first["refresh_token"]

    # First refresh: 200, token rotated.
    r1 = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1})
    assert r1.status_code == 200

    # Reuse the (now revoked) original token → 401 token_reused + family revoked.
    r2 = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1})
    assert r2.status_code == 401
    assert r2.json()["detail"] == "token_reused"

    # Both rows in the family are now revoked.
    rows = (await session.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)
    # At least one row has reason='reuse_detected'.
    assert any(r.revocation_reason == "reuse_detected" for r in rows)


async def test_refresh_unknown_token_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    resp = await async_client.post(
        "/v1/auth/refresh", json={"refresh_token": "definitely-not-real"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_refresh"


async def test_refresh_expired_token_returns_401(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    first = await _sign_in(async_client, google_verifier)
    refresh1 = first["refresh_token"]

    # Manually expire the row.
    row = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == sha256_token_hash(refresh1)
            )
        )
    ).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.flush()

    resp = await async_client.post(
        "/v1/auth/refresh", json={"refresh_token": refresh1}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "expired_refresh"


async def test_concurrent_refresh_race_has_exactly_one_winner(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    first = await _sign_in(async_client, google_verifier)
    refresh1 = first["refresh_token"]

    r1, r2 = await asyncio.gather(
        async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1}),
        async_client.post("/v1/auth/refresh", json={"refresh_token": refresh1}),
    )

    statuses = sorted([r1.status_code, r2.status_code])
    # Exactly one winner: one 200 and one 401 token_reused.
    assert statuses == [200, 401]
    loser = r1 if r1.status_code == 401 else r2
    assert loser.json()["detail"] == "token_reused"
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
uv run pytest tests/integration/test_auth_refresh.py -v
```

Expected: 404 (route doesn't exist yet).

- [ ] **Step 3: Add `AuthService.refresh`**

Edit `src/kpa/auth/service.py`. Add at the bottom of the `AuthService` class (after `_issue_refresh`):

```python
    async def refresh(self, presented_token: str) -> RefreshResult:
        token_hash = sha256_token_hash(presented_token)

        # Lock the row to serialize concurrent calls on the same token.
        result = await self._session.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        row: RefreshToken | None = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(401, "invalid_refresh")

        if row.revoked_at is not None:
            # REUSE detected — revoke the whole family.
            await self._revoke_family(row.family_id, reason="reuse_detected")
            raise HTTPException(401, "token_reused")

        if row.expires_at <= datetime.now(UTC):
            raise HTTPException(401, "expired_refresh")

        # Happy path: rotate.
        new_token = mint_refresh_token()
        now = datetime.now(UTC)
        new_row = RefreshToken(
            user_id=row.user_id,
            family_id=row.family_id,
            token_hash=sha256_token_hash(new_token),
            issued_at=now,
            expires_at=now + timedelta(seconds=self._settings.jwt_refresh_ttl_seconds),
        )
        self._session.add(new_row)
        await self._session.flush()

        row.replaced_by_id = new_row.id
        row.revoked_at = now
        row.revocation_reason = "rotated"
        row.last_used_at = now
        await self._session.flush()

        user = await self._session.get(User, row.user_id)
        assert user is not None
        access = mint_access_token(
            user_id=user.id,
            role=user.role.value,
            secret=self._settings.jwt_secret,
            ttl_seconds=self._settings.jwt_access_ttl_seconds,
        )

        return RefreshResult(
            access_token=access,
            refresh_token=new_token,
            expires_in=self._settings.jwt_access_ttl_seconds,
        )

    async def _revoke_family(self, family_id: UUID, *, reason: str) -> None:
        rows = (
            await self._session.execute(
                select(RefreshToken).where(
                    RefreshToken.family_id == family_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        ).scalars().all()
        now = datetime.now(UTC)
        for r in rows:
            r.revoked_at = now
            r.revocation_reason = reason
        await self._session.flush()
```

- [ ] **Step 4: Add the route**

Edit `src/kpa/routes/auth.py`. Add new schemas and the route below `sign_in_with_google`:

```python
class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh_token(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> RefreshResponse:
    result = await service.refresh(payload.refresh_token)
    return RefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
    )
```

- [ ] **Step 5: Run the new tests**

```bash
uv run pytest tests/integration/test_auth_refresh.py -v
```

All five pass.

If `test_concurrent_refresh_race_has_exactly_one_winner` fails with both responses returning 200: the `.with_for_update()` clause on the refresh lookup is the fix — the second call's `SELECT FOR UPDATE` blocks until the first call commits, at which point the row is already revoked and the second call hits the reuse path.

- [ ] **Step 6: Full pipeline**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"
uv run pytest -v -m integration
```

All green.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/auth/service.py api/src/kpa/routes/auth.py api/tests/integration/test_auth_refresh.py
git commit -m "$(cat <<'EOF'
feat(api): POST /v1/auth/refresh rotates tokens + detects reuse

Rotation is atomic via SELECT … FOR UPDATE on the refresh row.
A presented token whose row is already revoked triggers family-wide
revocation (revocation_reason='reuse_detected') and returns
401 token_reused — the spec §9.1 invariant.

Integration tests cover happy-path rotation, unknown/expired tokens,
the reuse-detection family revocation, and a concurrent-refresh
race that must produce exactly one winner.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `POST /v1/auth/logout` — idempotent revoke

**Files:**
- Modify: `api/src/kpa/auth/service.py`
- Modify: `api/src/kpa/routes/auth.py`
- Create: `api/tests/integration/test_auth_logout.py`

Idempotent by design — unknown / already-revoked tokens still return 204. This prevents an oracle on token existence. The presented token is the only thing revoked; siblings in the family are untouched (there are none active, by rotation invariant).

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_auth_logout.py`:

```python
"""Integration tests for POST /v1/auth/logout."""

from __future__ import annotations

import httpx
from sqlalchemy import select

from kpa.auth.google_verifier import GoogleClaims
from kpa.auth.tokens import sha256_token_hash
from kpa.db.models import RefreshToken


def _claims(sub: str = "google-sub-1", email: str = "a@example.com") -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=True,
        name="A",
    )


async def test_logout_revokes_refresh_token(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    google_verifier.canned["tok"] = _claims()
    signin = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "tok"}
    )
    assert signin.status_code == 200
    refresh = signin.json()["refresh_token"]

    resp = await async_client.post(
        "/v1/auth/logout", json={"refresh_token": refresh}
    )
    assert resp.status_code == 204
    assert resp.content == b""

    row = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == sha256_token_hash(refresh)
            )
        )
    ).scalar_one()
    assert row.revoked_at is not None
    assert row.revocation_reason == "logout"


async def test_logout_then_refresh_returns_401(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    google_verifier.canned["tok"] = _claims()
    signin = await async_client.post(
        "/v1/auth/oauth/google", json={"id_token": "tok"}
    )
    refresh = signin.json()["refresh_token"]

    await async_client.post("/v1/auth/logout", json={"refresh_token": refresh})

    resp = await async_client.post(
        "/v1/auth/refresh", json={"refresh_token": refresh}
    )
    assert resp.status_code == 401
    # The detail can be either token_reused (revoked_at branch in refresh) or
    # token_revoked. Both are acceptable. Spec §9.1 treats logout as a
    # revocation; the refresh flow sees revoked_at and surfaces reuse.
    assert resp.json()["detail"] in {"token_reused", "token_revoked"}


async def test_logout_unknown_token_returns_204(
    async_client: httpx.AsyncClient,
) -> None:
    resp = await async_client.post(
        "/v1/auth/logout", json={"refresh_token": "no-such-token"}
    )
    assert resp.status_code == 204
    assert resp.content == b""


async def test_logout_does_not_affect_other_users(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    google_verifier.canned["alice"] = _claims(sub="alice-sub", email="alice@example.com")
    google_verifier.canned["bob"] = _claims(sub="bob-sub", email="bob@example.com")

    alice = await async_client.post("/v1/auth/oauth/google", json={"id_token": "alice"})
    bob = await async_client.post("/v1/auth/oauth/google", json={"id_token": "bob"})
    assert alice.status_code == bob.status_code == 200
    alice_refresh = alice.json()["refresh_token"]
    bob_refresh = bob.json()["refresh_token"]

    # Alice logs out.
    await async_client.post("/v1/auth/logout", json={"refresh_token": alice_refresh})

    # Bob's refresh still works.
    resp = await async_client.post(
        "/v1/auth/refresh", json={"refresh_token": bob_refresh}
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
uv run pytest tests/integration/test_auth_logout.py -v
```

Expected: 404 (route doesn't exist).

- [ ] **Step 3: Add `AuthService.logout`**

Edit `src/kpa/auth/service.py`. Add inside the `AuthService` class:

```python
    async def logout(self, presented_token: str) -> None:
        """Revoke the presented refresh token. Idempotent: silent on unknown."""
        token_hash = sha256_token_hash(presented_token)
        row = (
            await self._session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return  # No oracle on token existence.

        row.revoked_at = datetime.now(UTC)
        row.revocation_reason = "logout"
        await self._session.flush()
```

- [ ] **Step 4: Add the route**

Edit `src/kpa/routes/auth.py`:

```python
from fastapi.responses import Response


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def logout(
    payload: LogoutRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> Response:
    await service.logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Run the new tests**

```bash
uv run pytest tests/integration/test_auth_logout.py -v
```

All four pass.

- [ ] **Step 6: Full pipeline**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"
uv run pytest -v -m integration
```

All green.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/auth/service.py api/src/kpa/routes/auth.py api/tests/integration/test_auth_logout.py
git commit -m "$(cat <<'EOF'
feat(api): POST /v1/auth/logout revokes the presented refresh

Idempotent by design — unknown / already-revoked tokens still
return 204 so the response can't be used as an oracle for token
existence. Same reasoning as the uniform-404 on GET resume.

Logout sets revocation_reason='logout'; subsequent refresh on
the same token hits the revoked_at branch and surfaces as
token_reused (the family is logically dead).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `GET /v1/me` — current user + applicant payload

**Files:**
- Create: `api/src/kpa/routes/me.py`
- Modify: `api/src/kpa/app_factory.py`
- Create: `api/tests/integration/test_me.py`

The first route that exercises `current_user` end-to-end. Returns the user + applicant payload for the holder of a valid access JWT. For non-applicant roles (none in this slice), the `applicant` key is omitted — but the implementation only handles the applicant branch.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_me.py`:

```python
"""Integration tests for GET /v1/me + current_user end-to-end."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx
import jwt as pyjwt
from sqlalchemy import select

from kpa.auth.google_verifier import GoogleClaims
from kpa.db.models import User


def _claims() -> GoogleClaims:
    return GoogleClaims(
        sub="google-sub-1",
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email="alice@example.com",
        email_verified=True,
        name="Alice",
    )


async def _signin(client: httpx.AsyncClient, google_verifier) -> dict:
    google_verifier.canned["tok"] = _claims()
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert resp.status_code == 200
    return resp.json()


async def test_me_returns_user_and_applicant(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]

    resp = await async_client.get(
        "/v1/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == signin["user"]["id"]
    assert body["email"] == "alice@example.com"
    assert body["role"] == "applicant"
    assert body["applicant"]["id"] == signin["user"]["applicant_id"]
    assert body["applicant"]["full_name"] == "Alice"
    assert body["applicant"]["locations"] == []
    assert body["applicant"]["notice_period_days"] is None


async def test_me_missing_bearer_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    resp = await async_client.get("/v1/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_bearer_token"


async def test_me_invalid_signature_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    # Token signed with the wrong secret.
    forged = pyjwt.encode(
        {
            "iss": "kpa-api",
            "sub": "11111111-1111-1111-1111-111111111111",
            "role": "applicant",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "jti": "00000000-0000-0000-0000-000000000000",
        },
        "wrong-secret-but-still-32-bytes-y",
        algorithm="HS256",
    )
    resp = await async_client.get(
        "/v1/me", headers={"Authorization": f"Bearer {forged}"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_access_token"


async def test_me_expired_token_returns_401(
    async_client: httpx.AsyncClient,
) -> None:
    expired = pyjwt.encode(
        {
            "iss": "kpa-api",
            "sub": "11111111-1111-1111-1111-111111111111",
            "role": "applicant",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
            "jti": "00000000-0000-0000-0000-000000000000",
        },
        "x" * 32,
        algorithm="HS256",
    )
    resp = await async_client.get(
        "/v1/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_access_token"


async def test_me_deleted_user_returns_401(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]
    user_id = signin["user"]["id"]

    db_user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    db_user.deleted_at = datetime.now(UTC)
    await session.flush()

    resp = await async_client.get(
        "/v1/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "user_not_found"
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
uv run pytest tests/integration/test_me.py -v
```

Expected: 404 (route doesn't exist yet).

- [ ] **Step 3: Implement the route**

Create `src/kpa/routes/me.py`:

```python
"""GET /v1/me — current user + role-shaped payload.

This slice only implements the applicant branch. Recruiter / admin shapes
land in their respective auth plans.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import current_user
from kpa.db.models import Applicant, User, UserRole
from kpa.db.session import get_session

router = APIRouter(prefix="/v1", tags=["me"])


class ApplicantRead(BaseModel):
    id: UUID
    full_name: str
    locations: list[str]
    notice_period_days: int | None
    current_ctc: Decimal | None
    expected_ctc: Decimal | None
    years_experience: Decimal | None


class MeResponse(BaseModel):
    id: UUID
    email: str
    role: str
    applicant: ApplicantRead | None = None


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeResponse:
    payload = MeResponse(
        id=user.id,
        email=user.email or "",
        role=user.role.value,
    )
    if user.role == UserRole.APPLICANT:
        row = (
            await session.execute(
                select(Applicant).where(
                    Applicant.user_id == user.id,
                    Applicant.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            # Should not happen — sign-in auto-provisions an applicants row.
            raise HTTPException(500, "applicant_missing")
        payload.applicant = ApplicantRead.model_validate(row, from_attributes=True)
    return payload
```

- [ ] **Step 4: Mount the router in `app_factory.py`**

Edit `src/kpa/app_factory.py`. Add to the imports:

```python
from kpa.routes import me
```

Below the `app.include_router(auth.router)` line, add:

```python
    app.include_router(me.router)
```

- [ ] **Step 5: Run the new tests**

```bash
uv run pytest tests/integration/test_me.py -v
```

All five pass.

- [ ] **Step 6: Full pipeline**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"
uv run pytest -v -m integration
```

All green.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/routes/me.py api/src/kpa/app_factory.py api/tests/integration/test_me.py
git commit -m "$(cat <<'EOF'
feat(api): GET /v1/me returns current user + applicant payload

First route to exercise current_user end-to-end. Reads the
applicants row via the session and shapes the response with
the role branch — only the applicant branch is implemented in
this slice; recruiter/admin land later.

Integration tests cover: happy path, missing bearer (401
missing_bearer_token), invalid signature (401
invalid_access_token), expired token (401 invalid_access_token),
and deleted user with a still-valid token (401 user_not_found —
the always-refetch invariant).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Docs — README + spec §10 update

**Files:**
- Modify: `api/README.md`
- Modify: `IMPLEMENTATION_SPEC.md`

- [ ] **Step 1: Append auth env vars to the README's Configuration table**

Edit `api/README.md`. In the **Configuration** section, after the existing env-var table, append the seven new rows:

```markdown
| `KPA_JWT_SECRET`   | yes      | —       | HS256 signing secret; min 32 bytes |
| `KPA_JWT_ACCESS_TTL_SECONDS`  | no | `600`     | Access token lifetime (10 min default) |
| `KPA_JWT_REFRESH_TTL_SECONDS` | no | `2592000` | Refresh token lifetime (30 d default)  |
| `KPA_GOOGLE_OAUTH_CLIENT_IDS` | yes | —        | CSV of Google Client IDs (web/iOS/Android) |
| `KPA_GOOGLE_JWKS_URL`         | no | `https://www.googleapis.com/oauth2/v3/certs` | Override for tests / offline dev |
| `KPA_GOOGLE_JWKS_CACHE_TTL_SECONDS` | no | `3600` | JWKS in-process cache TTL |
| `KPA_AUTH_REQUIRE_EMAIL_VERIFIED`   | no | `false` | Reject Google sign-ins without `email_verified=true` |
```

- [ ] **Step 2: Add an Auth section**

Below the **Resume uploads** section, add:

````markdown
## Auth

Three sign-in/session endpoints plus one identity endpoint:

```
POST   /v1/auth/oauth/google          # Google ID token → access + refresh
POST   /v1/auth/refresh               # rotate refresh; new access + refresh
POST   /v1/auth/logout                # revoke refresh (idempotent 204)
GET    /v1/me                         # current user + applicant payload
```

The Google flow is **client-driven** — the Flutter app obtains a Google ID
token via the official SDK and POSTs it to `/v1/auth/oauth/google`. The
backend verifies the token against Google's JWKS, upserts the user, and
mints an HS256 access JWT (10 min) plus an opaque rotating refresh token
(30 d, sha256-hashed at rest).

There's no `/callback` redirect endpoint — the spec's prior `/oauth/{provider}/callback`
naming was inaccurate for client-driven flows and was replaced.

Refresh tokens rotate on every successful refresh. Reuse of an
already-rotated token triggers full revocation of the family. See
`docs/superpowers/specs/2026-05-17-auth-google-oauth-applicant-design.md`
for the design rationale.

### Quick test from the shell

```bash
# Mint a JWT secret if you don't have one yet:
openssl rand -base64 48 | tr -d '\n' | tr -d '=' | head -c 64

# Then start the server (with KPA_JWT_SECRET and KPA_GOOGLE_OAUTH_CLIENT_IDS set in .env)
# and hit /v1/me with a valid Bearer access JWT:
ACCESS=...   # from a real Google sign-in
curl -s http://127.0.0.1:8000/v1/me -H "Authorization: Bearer $ACCESS" | python -m json.tool
```
````

- [ ] **Step 3: Update the spec §10 endpoint listing**

Edit `IMPLEMENTATION_SPEC.md`. Find the `POST /v1/auth/oauth/{provider}/callback` line in §10 and replace the **`POST /v1/auth/oauth/...`** block (the three auth lines) with:

```
POST   /v1/auth/oauth/google        # Google ID token → access + refresh (client-driven)
POST   /v1/auth/refresh
POST   /v1/auth/logout
```

Below the indicative endpoint surface, add a one-line note:

> *The original `/oauth/{provider}/callback` naming assumed a backend-redirect flow. The applicant Google sign-in plan landed with a client-driven ID-token exchange (see the design doc) and renamed the endpoint accordingly. The `{provider}` namespace is preserved for the Apple Sign-In plan.*

- [ ] **Step 4: Update the Project layout in the README**

Find the `## Project layout` section in `api/README.md` and update the tree to include the new modules. The relevant additions:

```
api/
├── ...
├── src/kpa/
│   ├── ...
│   ├── auth/
│   │   ├── dependencies.py    # current_user, optional_current_user
│   │   ├── google_verifier.py # JWKS-backed Google ID-token verifier
│   │   ├── service.py         # AuthService — sign-in, refresh, logout
│   │   └── tokens.py          # HS256 access JWT + opaque refresh primitives
│   └── routes/
│       ├── auth.py            # /v1/auth/oauth/google, /refresh, /logout
│       └── me.py              # GET /v1/me
└── ...
```

- [ ] **Step 5: Commit**

```bash
git add api/README.md IMPLEMENTATION_SPEC.md
git commit -m "$(cat <<'EOF'
docs(api): document Google sign-in endpoints + new auth env vars

README gets seven new KPA_ env vars in the Configuration table,
an Auth section explaining the client-driven flow + refresh/reuse
semantics, a /me curl smoke test, and the updated project layout.

IMPLEMENTATION_SPEC.md §10 replaces /v1/auth/oauth/{provider}/callback
with the actual shipped endpoints + a footnote on why the rename
happened.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final check

After all tasks land, run the full local pipeline from `api/`:

```bash
uv run --env-file=.env alembic upgrade head      # idempotent if already at head
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
uv run pytest -v -m "not integration"            # unit only
uv run pytest -v -m integration                  # integration tier
uv run pytest -v                                 # full suite
```

All six must exit 0. Expected total: **~76 tests** (51 from P0+P1.0 + ~9 settings/tokens/verifier/dependencies unit tests + ~16 auth/me integration tests).

Then push the branch and either:
- Open a PR against `feat/p0-db-layer-and-user-model` (stacked) if PR #2 hasn't merged yet.
- Open a PR against `main` if PR #2 already merged.

Hand-test smoke pass (optional but recommended):

```bash
# 1. Start the server with real env vars.
uv run --env-file=.env uvicorn kpa.main:app --reload --port 8000

# 2. Forge a Google ID token (impossible without owning a Google key) — so for
#    real e2e, plug in a Flutter dev build hitting Google Sign-In and POST the
#    resulting id_token to /v1/auth/oauth/google. The endpoint will accept any
#    real Google token whose aud matches one of KPA_GOOGLE_OAUTH_CLIENT_IDS.

# 3. With the access_token from step 2:
curl -s http://127.0.0.1:8000/v1/me -H "Authorization: Bearer <access_token>" | python -m json.tool

# 4. Rotate the refresh:
curl -s -X POST http://127.0.0.1:8000/v1/auth/refresh \
   -H 'Content-Type: application/json' \
   -d '{"refresh_token": "<refresh from step 2>"}' | python -m json.tool

# 5. Reuse the old refresh — must fail 401 token_reused, and the new family is now dead too.
curl -s -X POST http://127.0.0.1:8000/v1/auth/refresh \
   -H 'Content-Type: application/json' \
   -d '{"refresh_token": "<refresh from step 2 — the OLD one>"}' | python -m json.tool

# 6. Confirm /v1/me with the brand-new access still works.
curl -s http://127.0.0.1:8000/v1/me -H "Authorization: Bearer <new access from step 4>" | python -m json.tool
```

---

## Out of scope (intentionally — handled by later plans)

- **Apple Sign-In** — needs a separate plan: new `OAuthProvider` value via ALTER TYPE, code+identity-token verification path, account linking.
- **Phone-OTP** — separate plan: SMS provider integration, OTP storage, 5-min TTL, lockout.
- **Recruiter sign-up + admin TOTP MFA** — separate plans.
- **`/v1/applicants/me/resumes` alias** — small follow-up that wires `current_user.applicant_id` into the existing resume routes once this plan merges.
- **`PATCH /v1/me`** — listed in spec §10 but not on the critical path; lands when the profile editor needs it.
- **Account merging / "link another provider"** — placeholder is the 409 in `email_belongs_to_other_user`; the real merge UX needs design.
- **Rate limiting on `/auth/*`** (spec §9.3) — needs Redis, deferred to P3.
- **Access-token denylist for revoke-on-compromise** — needs Redis, deferred.
- **`GET /v1/auth/sessions`** (list active families) — useful but no consumer yet.
- **DPDP consent screens** (spec §9.2) — separate plan.

---

## Spec traceback

This plan implements the design at `docs/superpowers/specs/2026-05-17-auth-google-oauth-applicant-design.md`. Spec sections → task mapping:

- **OAuth flow shape** → Tasks 4 (verifier) + 9 (route).
- **Endpoints — request/response shapes** → Tasks 9 (sign-in) + 10 (refresh) + 11 (logout) + 12 (/me).
- **Error model** → Tasks 7 (auth dep slugs) + 9–12 (route slugs); RFC 7807 shaping inherits from the existing `error_handler.py`.
- **Data model: `oauth_identities`, `refresh_tokens`** → Tasks 5 (models) + 6 (migration).
- **Token lifecycle (HS256, opaque refresh, rotation, reuse detection, family_id)** → Tasks 3 (primitives) + 9 (sign-in mints) + 10 (refresh rotates).
- **Auth dependency / current_user** → Task 7.
- **Configuration / new env vars** → Task 2.
- **New dependencies (pyjwt, httpx)** → Task 1.
- **Testing strategy (fake verifier + dep override)** → Task 8.
- **Security posture (uniform 401 slugs, idempotent logout, sha256 hashing)** → distributed across Tasks 3, 9, 10, 11.
- **Spec §10 update** → Task 13.
