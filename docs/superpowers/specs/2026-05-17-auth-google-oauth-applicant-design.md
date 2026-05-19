# Auth — Google OAuth + access JWT + opaque refresh + GET /me (applicant slice) — design

**Date:** 2026-05-17
**Spec ref:** `IMPLEMENTATION_SPEC.md` §5 (users table), §9.1 (identity + tokens), §9.3 (general security), §10 (endpoint surface).
**Status:** Approved by Ahamed. Ready for implementation plan.

This is the first authentication slice. It lands the applicant-side path end-to-end: Google ID token exchange, our own access JWT, opaque rotating refresh token, logout, and `GET /v1/me`. Apple Sign-In, phone-OTP, recruiter sign-up, and admin TOTP MFA are each later plans built on the primitives introduced here.

## Why this slice

A working applicant sign-in unblocks every other product surface that has been path-paramming the applicant id (most importantly the resume upload route from P1.0, which today takes `applicant_id` in the URL because there's no `current_user`). After this plan:

1. The Flutter client can sign in with Google on mobile + web and call any authenticated route with `Authorization: Bearer …`.
2. The resume upload route can be migrated to `/v1/applicants/me/resumes` (separate small plan).
3. The token lifecycle, refresh-token storage table, and `current_user` dependency are reusable by every subsequent auth flow.

## OAuth flow shape

**Client-driven ID token exchange.** Picked over backend-redirect (web-app OAuth) and client-PKCE because:

- The Flutter `google_sign_in` package handles consent identically on iOS, Android, and web with no custom-scheme registration or redirect URI per environment.
- The backend never holds Google's client_secret — only the list of accepted client IDs.
- No browser dance, no httpOnly cookies vs URL-fragment debate: tokens are a plain JSON response.

Sequence:

1. Flutter app invokes Google Sign-In; user consents; SDK returns a Google-signed ID token (JWT).
2. App POSTs `{ id_token }` to our backend.
3. Backend verifies the JWT against Google's JWKS (`https://www.googleapis.com/oauth2/v3/certs`): signature, `iss`, `aud`, `exp`, `iat` (with 30 s skew).
4. Backend looks up an existing `oauth_identities` row keyed on `(provider='google', provider_subject=<sub>)`. If absent, it auto-provisions a fresh `users` row, an `applicants` row, and the `oauth_identities` row. If present, it updates `last_seen_at` and refreshes the user's `email` from claims.
5. Backend mints an HS256 access JWT (10 min) and an opaque refresh token (30 d, fresh `family_id`), stores the refresh as `sha256(token)` in `kpa.refresh_tokens`, and returns both.

The endpoint replaces the spec §10 line `POST /v1/auth/oauth/{provider}/callback` with `POST /v1/auth/oauth/google`. The "callback" naming was inaccurate for a client-driven flow. Spec §10 gets a one-line correction when this plan lands.

## Surface

Three routes under `routes/auth.py`, one under `routes/me.py`:

```
POST   /v1/auth/oauth/google            # exchange Google ID token for our tokens
POST   /v1/auth/refresh                 # rotate refresh; mint new access + refresh
POST   /v1/auth/logout                  # revoke the presented refresh token (idempotent 204)
GET    /v1/me                           # current user + applicant payload
```

All four are mounted on the existing FastAPI app via `app_factory.py`. The first three are unauthenticated entry points; `GET /v1/me` requires a Bearer access JWT.

### Request and response shapes

**`POST /v1/auth/oauth/google`**

```jsonc
// Request
{ "id_token": "<google-signed JWT>" }

// 200 OK
{
  "access_token":  "<HS256 JWT>",
  "refresh_token": "<opaque base64url string, ~43 chars>",
  "token_type":    "Bearer",
  "expires_in":    600,
  "user": {
    "id":           "<uuid>",
    "email":        "ahamed@example.com",
    "role":         "applicant",
    "applicant_id": "<uuid>",
    "is_new_user":  true
  }
}
```

The `applicant_id` field is included as a one-trip convenience so the client doesn't need an immediate `GET /v1/me`. `is_new_user=true` only on the first successful sign-in; the Flutter client uses this to route to onboarding vs the feed.

**`POST /v1/auth/refresh`**

```jsonc
// Request
{ "refresh_token": "<opaque string>" }

// 200 OK — rotation: the presented token is now revoked
{
  "access_token":  "<new HS256 JWT>",
  "refresh_token": "<new opaque string>",
  "token_type":    "Bearer",
  "expires_in":    600
}
```

**`POST /v1/auth/logout`**

```jsonc
// Request
{ "refresh_token": "<opaque string>" }

// 204 No Content — including when the token is unknown (idempotent / oracle-free)
```

**`GET /v1/me`**

```jsonc
// 200 OK
{
  "id":    "<uuid>",
  "email": "ahamed@example.com",
  "role":  "applicant",
  "applicant": {
    "id":                 "<uuid>",
    "full_name":          "Ahamed Wahid",
    "locations":          [],
    "notice_period_days": null,
    "current_ctc":        null,
    "expected_ctc":       null,
    "years_experience":   null
  }
}
```

For non-applicant roles, the `applicant` key is omitted and a `recruiter` or `admin` object substitutes. Only the applicant branch is implemented and tested in this plan.

### Error model

All errors flow through the existing RFC 7807 problem+json handler (`middleware/error_handler.py`). The `detail` slug names below become the `detail` field in the response body — clients should treat them as stable identifiers.

| Status | Slug | Trigger |
|---|---|---|
| 401 | `missing_bearer_token` | No `Authorization: Bearer …` header on `GET /v1/me` |
| 401 | `invalid_access_token` | Access JWT signature / `iss` / `exp` / `iat` failures |
| 401 | `invalid_google_token` | Google ID token verification failed (JWKS / claims) |
| 401 | `email_not_verified` | `KPA_AUTH_REQUIRE_EMAIL_VERIFIED=true` and Google claim is false (off by default) |
| 401 | `invalid_refresh` | Refresh token not found |
| 401 | `expired_refresh` | Refresh past `expires_at` |
| 401 | `token_reused` | Refresh already-rotated; whole family revoked |
| 401 | `token_revoked` | Refresh revoked via logout / admin action |
| 401 | `user_not_found` | Access JWT references a user with `deleted_at IS NOT NULL` |
| 409 | `email_belongs_to_other_user` | Google email matches a different user with a different oauth_identity |
| 503 | `google_jwks_unavailable` | JWKS fetch failed (cache cold + Google unreachable) |

`POST /v1/auth/logout` never returns an error code — always 204, even for unknown / already-revoked refresh tokens. This is a deliberate oracle prevention: the same reasoning as the uniform 404 in `GET /v1/applicants/{aid}/resumes/{rid}` (commit `ac9efdf`).

## Data model

Two new tables, one new enum type, no schema changes to existing tables.

### `kpa.oauth_identities`

M:1 to `users`. Designed so a single user can link multiple identity providers — Apple and phone-OTP will be additional rows when those plans land, with no schema migration.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK, default uuid4 | Existing `UuidPK` alias |
| `user_id` | UUID, FK → `kpa.users.id` ON DELETE CASCADE, nullable=False | One user, many identities |
| `provider` | enum `kpa.oauth_provider` (`google`), nullable=False | `apple` / `phone` added when those plans land via `ALTER TYPE` |
| `provider_subject` | `String(255)`, nullable=False | Google's `sub` claim — opaque, stable, never reused |
| `email_at_link` | `String(254)`, nullable | Snapshot of Google email at link time; `users.email` is the live source of truth |
| `linked_at` | `TIMESTAMPTZ`, server_default `now()`, nullable=False | First time this identity was linked |
| `last_seen_at` | `TIMESTAMPTZ`, server_default `now()`, nullable=False | Updated on every successful sign-in |
| `created_at` / `updated_at` / `deleted_at` | common aliases | Soft delete consistent with users + applicants |

**Indexes:**
- `UNIQUE (provider, provider_subject) WHERE deleted_at IS NULL` — the primary sign-in lookup; partial so a soft-deleted identity doesn't block re-linking.
- `(user_id) WHERE deleted_at IS NULL` — "list this user's linked identities" for a future settings screen.

### `kpa.refresh_tokens`

Append-only by convention. Rows are never deleted; rotation revokes by setting `revoked_at` + `revocation_reason`. No `deleted_at` column — the table's revocation model **diverges deliberately from the soft-delete convention** used by domain tables, and the model file flags this with a one-line comment.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK, default uuid4 | |
| `user_id` | UUID, FK → `kpa.users.id` ON DELETE CASCADE, nullable=False | |
| `family_id` | UUID, nullable=False | Shared across the rotation chain — new on sign-in, inherited on refresh |
| `token_hash` | `CHAR(64)`, nullable=False | `sha256(opaque_token).hexdigest()`; sha256 because the token is already 256-bit entropy, no need for bcrypt |
| `issued_at` | `TIMESTAMPTZ`, server_default `now()`, nullable=False | |
| `expires_at` | `TIMESTAMPTZ`, nullable=False | `issued_at + KPA_JWT_REFRESH_TTL_SECONDS` |
| `replaced_by_id` | UUID, FK → `kpa.refresh_tokens.id` ON DELETE SET NULL, nullable | Set on rotation |
| `revoked_at` | `TIMESTAMPTZ`, nullable | Set when revoked for any reason |
| `revocation_reason` | `String(64)`, nullable | `rotated` / `logout` / `reuse_detected` / `admin` |
| `last_used_at` | `TIMESTAMPTZ`, nullable | Set on successful refresh |
| `created_at` / `updated_at` | common aliases | |

**Indexes:**
- `UNIQUE (token_hash)` — primary lookup on refresh. **Not** partial — we *want* to find revoked rows so we can detect reuse and revoke the family.
- `(family_id) WHERE revoked_at IS NULL` — fast family-wide revocation on reuse.
- `(user_id) WHERE revoked_at IS NULL` — for the future "active sessions" view ( — query filters `expires_at > now()` residually; `now()` is non-IMMUTABLE so it cannot live in the predicate).

### Existing tables — no schema changes

The auto-provisioning flow uses existing `users` and `applicants` columns:

- `users.email` is upserted on every sign-in to track Google's current verified email. `users.phone`, `users.mfa_enabled` remain at their defaults for applicant Google sign-in.
- `users.role` is set to `applicant` on auto-create. Recruiters and admins onboard through different (later) plans.
- `applicants.full_name` is set **only on initial create** from Google's `name` claim (falling back to the local-part of `email` if missing). Subsequent sign-ins never overwrite it — that's user-owned profile data.
- `applicants.locations`, `notice_period_days`, etc. stay null/empty on auto-create. Profile completion lives in a future `PATCH /v1/me` plan.

**Email collision policy:** if the incoming Google email already maps to a different user (i.e. a different `oauth_identities` row, or a `users` row with this email but no Google identity), the sign-in fails with `409 email_belongs_to_other_user`. We do not silently merge — too risky in MVP. Account linking is a future feature with its own UX gate.

## Token lifecycle

### Access JWT — HS256 / `KPA_JWT_SECRET`

Claims:

```jsonc
{
  "iss":  "kpa-api",
  "sub":  "<user_id uuid>",
  "role": "applicant",
  "iat":  1747459200,
  "exp":  1747459800,           // iat + 600 (default)
  "jti":  "<uuid4>"             // unique id; reserved for future denylist
}
```

- `aud` deliberately omitted (single audience).
- `nbf` omitted (`iat` covers our skew tolerance).
- 30 s clock-skew tolerance on **decode only**.
- Role is included so role checks short-circuit without a DB roundtrip — but `users.role` remains the source of truth, re-fetched on every authenticated request (see "Auth dependency" below).

### Refresh token — opaque

- 32 random bytes from `secrets.token_bytes(32)` → base64url-encoded → ~43 chars.
- Stored as `sha256(token).hexdigest()` in `refresh_tokens.token_hash`.
- 30 d lifetime (`KPA_JWT_REFRESH_TTL_SECONDS=2592000`).

### Rotation

Every successful `/v1/auth/refresh` mints a brand-new opaque token and revokes the presented one. The new token shares the presented token's `family_id`. Within a single transaction:

```python
async with session.begin():
    row = await get_active_refresh_row(token)        # SELECT … FOR UPDATE
    if row.revoked_at is not None: revoke_family_and_raise("token_reused")
    if row.expires_at <= now():    raise 401 expired_refresh
    new_row = insert_refresh_row(user_id=row.user_id, family_id=row.family_id, …)
    row.replaced_by_id    = new_row.id
    row.revoked_at        = now()
    row.revocation_reason = "rotated"
```

`SELECT … FOR UPDATE` closes a TOCTOU race where two concurrent refreshes with the same token could both mint successors. The integration suite includes a concurrency test that hits this with `asyncio.gather`.

### Reuse detection

If `/v1/auth/refresh` (or `/v1/auth/logout`) is called with a token whose row exists but has `revoked_at IS NOT NULL`, we treat it as **reuse**: the entire family (matching `family_id`) is revoked with `revocation_reason='reuse_detected'`, and the response is `401 token_reused`. The client must full re-auth.

This is what "refresh reuse triggers full revocation" in spec §9.1 means concretely. The family scoping (not user-wide) keeps the blast radius proportional: a compromised refresh chain on device A doesn't log the user out on devices B and C.

### Sign-in vs refresh: where families come from

- **Sign-in**: generates a new `family_id = uuid4()`. Each device/login chain owns its own family.
- **Refresh**: inherits `family_id` from the (live) presented token.
- **Logout**: revokes only the presented token with `revocation_reason='logout'`. Does **not** revoke siblings in the family — but a family has at most one *active* (non-revoked, non-expired) row at any moment by construction (each refresh either fails or rotates exactly one token forward), so revoking that one row is effectively a full session logout.

### What logout does NOT do

Logout does not revoke the access JWT. Access tokens are stateless and short-lived (≤10 min). Building an access-token denylist needs Redis (spec §11.1, deferred to P3). The threat — a logged-out user's access token remaining usable for up to 10 min — is acceptable in MVP and explicitly noted in the out-of-scope list.

## Auth dependency / `current_user` resolution

A single FastAPI dependency, `current_user`, used by every authenticated route. Lives in `auth/dependencies.py`.

```python
async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = _extract_bearer_or_raise_401(request)        # 401 missing_bearer_token
    claims = decode_access_token(token, settings)         # 401 invalid_access_token
    user = await session.get(User, UUID(claims["sub"]))
    if user is None or user.deleted_at is not None:
        raise HTTPException(401, "user_not_found")
    request.state.current_user_id = user.id
    request.state.current_role = user.role
    return user
```

A companion `optional_current_user` returns `None` when no `Authorization` header is present. Not used in this plan, but ready for `/v1/applicants/me/resumes` later.

**Three deliberate choices** worth flagging in the code:

1. **Always re-fetch user from DB** — a user soft-deleted N seconds ago is locked out within the access TTL (≤10 min), not the refresh TTL (30 d). One indexed point-query per authenticated request (~0.2 ms). Cache it later if it becomes hot.
2. **No `fastapi.security.HTTPBearer`** — that helper writes its own JSON error shape, bypassing our RFC 7807 handler. We extract the header ourselves to keep error responses uniform.
3. **`request.state.current_user_id` and `current_role`** — bound on the request for structlog contextvars, extending the pattern that already binds `request_id` via `RequestIdMiddleware`.

**Role-gated routes** (`require_role(*roles)`) are deliberately out of scope. Nothing in this plan needs them — the only authenticated route here is `/v1/me`, which is applicant-shaped today and reads `User.role` to decide the response shape. The helper lands when recruiter routes need it.

**Testing via `dependency_overrides`** — same pattern already used to override `get_session` in the integration conftest:

```python
app.dependency_overrides[current_user] = lambda: fake_applicant_user
```

## Configuration

New env vars, all prefixed `KPA_`, validated at startup like the rest:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `KPA_JWT_SECRET` | yes | — | HS256 signing secret. Validator rejects < 32 bytes. |
| `KPA_JWT_ACCESS_TTL_SECONDS` | no | `600` (10 min) | Access token lifetime |
| `KPA_JWT_REFRESH_TTL_SECONDS` | no | `2592000` (30 d) | Refresh token lifetime |
| `KPA_GOOGLE_OAUTH_CLIENT_IDS` | yes | — | CSV of accepted Google Client IDs (Web + iOS + Android). Each must end in `.apps.googleusercontent.com`. |
| `KPA_GOOGLE_JWKS_URL` | no | `https://www.googleapis.com/oauth2/v3/certs` | Override for tests + offline dev |
| `KPA_GOOGLE_JWKS_CACHE_TTL_SECONDS` | no | `3600` (1 h) | JWKS in-process cache lifetime |
| `KPA_AUTH_REQUIRE_EMAIL_VERIFIED` | no | `false` | Reject sign-ins with `email_verified=false` (off in MVP, flippable via env) |

`.env.example` gets the seven new lines with placeholder values, matching the file's existing one-line-per-var style.

`Settings` validators:
- `jwt_secret`: `min_length=32`.
- `google_oauth_client_ids`: CSV-parsed via the existing `_split_csv` helper; each entry must end in `.apps.googleusercontent.com`.
- TTL values must be `> 0`.

The `GoogleIdTokenVerifier` is built once at app startup in `app_factory.py` and attached to `app.state.google_verifier`. Its JWKS cache is in-process (`asyncio.Lock` + dict). Multiple uvicorn workers each maintain their own cache — fine for our scale; Google's JWKS is cheap to fetch.

## New dependencies

- `pyjwt[crypto]>=2.9,<3` — HS256 signing + decoding. `[crypto]` brings the `cryptography` library so a future RS256 swap is a one-line change.
- `httpx>=0.27,<0.28` — promoted from `dev` to runtime for fetching Google's JWKS.

## Module layout

```
api/src/kpa/
  auth/                           NEW
    __init__.py
    google_verifier.py            GoogleIdTokenVerifier protocol + impl + InvalidGoogleTokenError
    tokens.py                     mint_access_token, decode_access_token, mint_refresh_token,
                                  sha256_token_hash; uses pyjwt + secrets
    service.py                    AuthService.sign_in_with_google, refresh, logout;
                                  owns upsert + rotation + reuse detection
    dependencies.py               current_user, optional_current_user, _extract_bearer_or_raise_401
  routes/
    auth.py                       NEW — POST /v1/auth/oauth/google, /refresh, /logout
    me.py                         NEW — GET /v1/me
  db/
    models.py                     APPEND — OAuthProvider, OAuthIdentity, RefreshToken
    migrations/versions/
      0003_oauth_identities_and_refresh_tokens.py    NEW

  settings.py                     APPEND — KPA_JWT_*, KPA_GOOGLE_*, KPA_AUTH_REQUIRE_EMAIL_VERIFIED
  app_factory.py                  Build GoogleIdTokenVerifier; mount auth + me routers

api/tests/
  unit/
    test_tokens.py                NEW
    test_google_verifier.py       NEW
    test_settings_auth.py         NEW (or append to test_settings.py)
  integration/
    conftest.py                   APPEND — FakeGoogleIdTokenVerifier + dependency_overrides wiring
    test_auth_signin.py           NEW
    test_auth_refresh.py          NEW
    test_auth_logout.py           NEW
    test_me.py                    NEW
```

## Testing strategy

### Unit (no DB, no network)

- **`test_tokens.py`**: sign/decode roundtrip; reject wrong-secret signature; reject expired token; reject bad `iss`; accept up to 30 s `iat` skew; reject 31 s; refresh token entropy length.
- **`test_google_verifier.py`**: happy path with canned JWKS; reject wrong `iss`, `aud` not in allowlist, expired token, bad signature; JWKS cache reused on second call; JWKS cache refreshed when expired.
- **`test_settings_auth.py`**: reject `KPA_JWT_SECRET < 32` bytes; parse `KPA_GOOGLE_OAUTH_CLIENT_IDS` as CSV; reject client IDs without `.apps.googleusercontent.com` suffix.

### Integration (real Postgres, fake Google verifier injected via `dependency_overrides`)

- **`test_auth_signin.py`**: new user creates `users` + `applicants` + `oauth_identities`; returning user updates `last_seen_at`, `is_new_user=false`; 401 when fake verifier raises; 409 when Google email matches a different existing user.
- **`test_auth_refresh.py`**: rotation succeeds (old revoked `rotated`, new returned); reuse detection (presenting an already-rotated token revokes the whole family, returns 401 `token_reused`); 401 expired; 401 unknown; concurrent refresh race via `asyncio.gather` — exactly one wins.
- **`test_auth_logout.py`**: logout revokes the presented refresh; subsequent refresh fails 401 `token_revoked`; logout on unknown token returns 204 (no oracle); logout does not affect other users' tokens.
- **`test_me.py`**: 200 with applicant payload for valid bearer; 401 missing bearer; 401 invalid bearer; 401 expired bearer; 401 deleted user (set `users.deleted_at`, present a still-valid token).

### Fake Google verifier

```python
class FakeGoogleIdTokenVerifier:
    def __init__(self, canned: dict[str, GoogleClaims] | None = None):
        self._canned = canned or {}
    async def verify(self, id_token: str) -> GoogleClaims:
        if id_token in self._canned: return self._canned[id_token]
        raise InvalidGoogleTokenError("not in fake canned tokens")
```

Tests use opaque tag strings (`"applicant_a_token"`) mapped to fully-formed `GoogleClaims`. Zero network, zero crypto in integration tests. The fake is injected via `app.dependency_overrides[get_google_verifier]`.

Estimated test count: ~25 new (~8 unit + ~17 integration). Combined with the existing 51 → ~76 total.

## Security posture

Concentrating the checks in one place:

- Google ID token signature + claim validation against Google's JWKS (cached in-process).
- `aud` matched against the `KPA_GOOGLE_OAUTH_CLIENT_IDS` allowlist.
- Refresh token rotation + family-wide reuse detection.
- Refresh stored as `sha256` (never plaintext).
- Logout idempotent and oracle-free (always 204).
- 401 errors carry uniform `detail` slugs — slug names listed in the error model table become a stable client contract.
- `KPA_JWT_SECRET` length floor of 32 bytes.

**What this plan does NOT do** (deferred by design):

- Apple Sign-In, phone-OTP, recruiter sign-up, admin TOTP MFA — later plans.
- Account merging / "link an additional provider" — later plan; the 409 surface is the placeholder.
- Access-token denylist (needs Redis) — spec §11.1, deferred to P3.
- Rate limiting on `/auth/*` (spec §9.3) — needs Redis, deferred. TODO marker at the router.
- DPDP consent screens (spec §9.2) — separate plan.
- Cookie-based session for Flutter web — client owns token storage (secure storage on mobile; in-memory + sessionStorage on web).
- `GET /v1/auth/sessions` (list active refresh families) — deferred.
- `PATCH /v1/me` — listed in spec §10 but the read-only `/me` is enough for this plan; PATCH lands when the profile editor needs it.

## Spec updates required

When this plan lands, the implementation spec gets two small edits:

- **§10**, endpoint surface: replace `POST /v1/auth/oauth/{provider}/callback` with `POST /v1/auth/oauth/google` and add a footnote explaining that client-driven ID-token exchange means there's no IdP-initiated callback in the OAuth-redirect sense.
- **§9.1**: no changes — this design implements exactly what's written there for applicant Google sign-in.

## Open questions resolved during brainstorming

| # | Question | Resolution |
|---|---|---|
| 1 | Auth MVP scope | Standard: Google + access JWT + opaque refresh + logout + GET /me. Apple/phone-OTP later plans. |
| 2 | OAuth flow shape | Option A: client-driven ID token exchange (Flutter SDK → backend verifies via Google JWKS). |
| 3 | Identity model | β: separate `oauth_identities` table, M:1 to users. |
| 4 | JWT signing algorithm | HS256 with a single signing secret. RS256 swap is a one-line change later. |
| 5 | First-time provisioning | Auto-create `users` + `applicants` rows. `email_verified` gate behind a config flag, off by default. |
| 6 | Endpoint URL shape | `POST /v1/auth/oauth/google` — namespaced for future providers. |
