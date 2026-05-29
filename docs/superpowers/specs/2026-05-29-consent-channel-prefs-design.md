# P4 Sub-project B — Consent + notification-channel preferences

**Status:** approved 2026-05-29
**Owner:** backend
**Scope:** sub-project B of three approved P4 slices (A → B → C). A shipped via PR #25 (`audit_logs` substrate); this slice writes through that substrate.

## 1. Why this slice exists

CLAUDE.md on the notifications outbox is explicit:

> *Per-user channel preferences / consents deferred to P4. Currently all channels are enabled for all users. When P4 lands, the sweep must gate dispatch on the user's consent record.*

DPDP-Act-2023 § 6(1) requires consent be *specific and informed*. A single global opt-in is non-compliant — each purpose / channel needs its own toggleable record, and § 7 mandates the withdrawal mechanism be "as easy as" the grant mechanism. This slice ships the storage, the API, the seeding, the sweep gate, and the audit trail for every grant/revoke.

The Flutter consent screens (sub-project F) and DSR-export's "include consent history" support (sub-project C) both consume what this PR ships.

## 2. Non-goals

- Flutter consent UI — sub-project F (later).
- Marketing email content — none exist yet; the gating plumbing exists for when they do.
- Recruiter-side consent for posting jobs — that's terms-of-service, not DPDP.
- Granular per-job notification routing rules (e.g., "alert me only about jobs ≥ 12 LPA"). Deferred.
- Backfilling consent for users created **before** this slice's migration — handled by a one-off CLI in this PR (§9), not in the migration itself.

## 3. Storage

```sql
CREATE TABLE kpa.user_consents (
    id           UUID PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES kpa.users(id) ON DELETE CASCADE,
    scope        TEXT NOT NULL,
    granted      BOOLEAN NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ NULL
);

CREATE UNIQUE INDEX ix_user_consents_user_scope_live
    ON kpa.user_consents (user_id, scope) WHERE deleted_at IS NULL;
```

### 3.1 FK ondelete: CASCADE (deliberate, opposite of audit_logs)

`audit_logs.actor_user_id` is `ON DELETE SET NULL` because the audit row outlives the user. `user_consents.user_id` is `ON DELETE CASCADE` because a consent record for a non-existent user is meaningless — the row should disappear with the user.

Both choices are load-bearing for the future DSR-delete (sub-project D, "hard-delete PII, keep anonymized aggregates"). The audit-log entries documenting the user's grants/revokes survive in `audit_logs`; the operational consent state vanishes here.

### 3.2 Soft-delete + partial-UNIQUE

This IS a normal domain table — `CreatedAt`/`UpdatedAt`/`DeletedAt` Annotated types from `db/models.py` apply. We don't track history in this table (history is in `audit_logs`); the partial-UNIQUE on `(user_id, scope) WHERE deleted_at IS NULL` ensures exactly one live row per scope per user.

`deleted_at` exists for future admin-side reset flows (the user's consent rows being soft-deleted by an admin during a DSR cycle), not for normal grant/revoke. **Toggling `granted` boolean is the normal path; soft-delete is the exception.**

### 3.3 No `granted_at` column

The codebase's `updated_at` column updates on every flip via the `UpdatedAt` Annotated type. Adding a separate `granted_at` would duplicate the same information. Queries that want "when did this consent reach its current state?" use `updated_at`.

## 4. Scopes (v0)

```python
class ConsentScope(StrEnum):
    EMAIL_TRANSACTIONAL = "email_transactional"   # default true
    EMAIL_MARKETING = "email_marketing"           # default false
    IN_APP_NOTIFICATIONS = "in_app_notifications" # default true
    # Reserved for later sub-projects — defined in v0 to avoid enum migration churn:
    WHATSAPP_NOTIFICATIONS = "whatsapp_notifications"      # default false (no impl)
    SMS_NOTIFICATIONS = "sms_notifications"                # default false (no impl)
    PROFILE_VISIBILITY_RECRUITERS = "profile_visibility_recruiters"  # default false
    THIRD_PARTY_SHARING_RECRUITERS = "third_party_sharing_recruiters"  # default false (no impl)
```

The DB column is plain `TEXT` (mirrors `audit_logs.action`) — unknown values are rejected at the API boundary via Pydantic enum validation, not at the DB. Future scope additions don't need migrations.

`DEFAULT_CONSENTS: dict[ConsentScope, bool]` is the single source of truth for v0 defaults; sub-project F's consent screen will read it for the "reset to defaults" affordance.

### 4.1 The legally-borderline default on `email_transactional`

DPDP-Act-2023 does not have GDPR's clean "contractual necessity" carveout. We default `email_transactional=true` at signup because (a) match notifications when the applicant applied to a job are integral to the service and (b) the user can revoke immediately via `PATCH /v1/me/consents/{scope}`. The signup screen MUST display a notice ("by signing up, you agree to receive service-related communications") for legal coverage — that's a sub-project F responsibility, called out here for traceability.

## 5. Seeding — eager at signup

`auth/service.py:AuthService._upsert_identity` is the only path that creates a `User` row (Google OAuth is the only sign-in flow today). On the new-user branch, after `self._session.add(identity)` and before the final `flush()`:

```python
await seed_default_consents(self._session, user=user, request_id=request_id)
```

`request_id` propagates through `AuthService` from the request handler — see §6.

`seed_default_consents` inserts seven rows (one per scope) and writes seven `audit_logs` entries with `action="consent.seeded"`. All in the same transaction — eight units of work commit-or-rollback atomically. Sign-in failure leaves no orphan consent rows.

**Why eager over lazy:** all later reads are simple `SELECT`s with no fallback path; the sweep stays trivial; and changing a default later affects only *new* signups (existing users' explicit values aren't unilaterally revoked, which is the legally-correct migration story).

## 6. Helper API — `src/kpa/consent/__init__.py`

```python
async def get_consent(
    session: AsyncSession,
    *,
    user: User,
    scope: ConsentScope,
) -> bool:
    """Return current grant state. Raises LookupError if no live row exists
    (means seeding was skipped — a bug for users created after this slice,
    or a pre-existing user the backfill CLI missed). Callers MAY catch and
    fall back to DEFAULT_CONSENTS[scope]."""


async def set_consent(
    session: AsyncSession,
    *,
    user: User,
    scope: ConsentScope,
    granted: bool,
    request_id: str | None = None,
) -> UserConsent:
    """UPSERT the consent row + write one audit_logs entry. Same txn.
    No-op (no audit row written) if the requested state matches the
    current state — DPDP doesn't want spurious "consent.granted" entries
    when the user just re-affirms the existing state. Returns the row
    either way."""


async def seed_default_consents(
    session: AsyncSession,
    *,
    user: User,
    request_id: str | None = None,
) -> list[UserConsent]:
    """Insert one row per ConsentScope using DEFAULT_CONSENTS as values, +
    one audit_logs entry per row (action='consent.seeded'). Single txn.
    Idempotent: skips scopes that already have a live row (so the backfill
    CLI is safe to re-run)."""
```

Caller owns the txn — same contract as `audit_log()`. The helper does `session.flush()`, never `session.commit()`.

### 6.1 `set_consent` no-op-on-noop

If the user PATCHes `{granted: true}` and the current state is already `true`, we return the existing row unchanged and write NO audit row. Reason: a regulator audit of "how many times did the user consent to marketing emails?" should not show inflated counts from accidental re-toggles in the UI.

## 7. API — `routes/consents.py`

### `GET /v1/me/consents`

Returns the three live rows for the authenticated user:

```json
{
  "items": [
    {"scope": "email_transactional", "granted": true,  "updated_at": "..."},
    {"scope": "email_marketing",     "granted": false, "updated_at": "..."},
    {"scope": "in_app_notifications","granted": true,  "updated_at": "..."}
  ]
}
```

No cursor pagination (max ~7 rows per user). No ETag (the user is reading their own state, which they just changed — cache invalidation isn't useful here).

Scopes with NO live row are **not** included in the response — that surfaces backfill misses cleanly (a missing scope is a bug, not a "default fallback").

### `PATCH /v1/me/consents/{scope}`

Body: `{"granted": bool}`. Returns the updated row (same shape as an item in `GET`).

- Unknown scope (path param doesn't parse to `ConsentScope`) → 422.
- `granted` missing or non-boolean → 422.
- No-op (already in the requested state) → 200, no audit row written.
- Soft-deleted row (`deleted_at IS NOT NULL`) → 404 `consent_not_found` (admin DSR action — should never happen in normal flow).

Behind `current_user` only — no `_require_applicant` / `_require_recruiter`. Applicants, recruiters, and admins all manage their own consents.

`request_id` flows from `request.state.request_id` into the `set_consent` call → into the `audit_logs.context.request_id`.

## 8. Sweep integration — load-bearing change to `workers/tasks/sweep_notifications.py`

### 8.1 New status value

`NotificationStatus.CANCELLED = "cancelled"` joins the existing `pending | dispatching | sent | failed`. The status column is a **native Postgres enum** (`SAEnum(..., native_enum=True)`), so the migration needs `ALTER TYPE kpa.notification_status ADD VALUE 'cancelled'`. That statement **cannot run inside a transaction** with other DDL — the migration must use `op.get_context().autocommit_block()` (see plan Task 1, Step 2).

### 8.2 New nullable column

`Notification.cancelled_at TIMESTAMPTZ NULL` — set when the sweep marks a row cancelled because of consent withdrawal. Distinct from `sent_at` so a regulator audit can answer "was this message ever sent" vs "was it suppressed at delivery." Same migration as the status enum value.

### 8.3 Gate insertion point

`sweep_notifications.py:_dispatch_one` currently:
1. Loads `Notification` (line 159).
2. Loads `User` (line 162) — fails to FAILED if missing.
3. Dispatches via channel adapter (line 175).
4. Updates state (sent / failed / retry).

Add a **new step 2.5** between user load and channel dispatch:

```python
scope = _scope_for_notification(n)  # email → email_transactional; in_app → in_app_notifications
try:
    granted = await get_consent(session, user=user, scope=scope)
except LookupError:
    # Backfill miss — fall back to default. Future DSR-delete may also
    # cascade the consent row away; default is the safe behavior.
    granted = DEFAULT_CONSENTS[scope]

if not granted:
    n.status = NotificationStatus.CANCELLED
    n.cancelled_at = func.now()
    n.last_error = f"consent_revoked:{scope.value}"
    _log.info(
        "sweep.cancelled-no-consent",
        notification_id=str(notification_id),
        user_id=str(user.id),
        scope=scope.value,
    )
    await session.commit()
    return
```

`_scope_for_notification(n)` is a private mapping function in the same file. For v0:

```python
def _scope_for_notification(n: Notification) -> ConsentScope:
    if n.channel == NotificationChannel.EMAIL:
        return ConsentScope.EMAIL_TRANSACTIONAL  # No marketing kinds emitted yet.
    if n.channel == NotificationChannel.IN_APP:
        return ConsentScope.IN_APP_NOTIFICATIONS
    raise ValueError(f"unmapped channel: {n.channel}")
```

When marketing kinds ship later, the mapping will check `n.kind` against a known-marketing set and return `EMAIL_MARKETING` for those.

### 8.4 Inbox endpoint exclusion

`routes/notifications.py:list_notifications` (the `GET /v1/notifications` inbox) currently excludes `status='failed'`. Extend to also exclude `status='cancelled'` — the user explicitly didn't want these, so they shouldn't appear in the inbox.

### 8.5 No retry from `CANCELLED`

Unlike `FAILED` (which can be admin-retried via a future tool), `CANCELLED` is terminal. A user re-granting consent does NOT resurrect cancelled rows. Reason: the original event might be stale (a job was withdrawn; the email about it is no longer relevant). Re-granting consent affects only *new* notifications.

## 9. Backfill CLI — `kpa-seed-consents`

`src/kpa/cli/seed_consents.py` (new). Pattern mirrors `kpa-seed-jobs`: opens an engine, calls a `_apply_in_session(session, report)` helper that the integration test can drive directly.

For each live `User`, calls `seed_default_consents(session, user=user)` (which is itself idempotent). Run once after the migration lands; safe to re-run.

Registered in `pyproject.toml`'s `[project.scripts]`:

```toml
kpa-seed-consents = "kpa.cli.seed_consents:main"
```

## 10. CLAUDE.md updates

Add under "Architecture — non-obvious bits":

```
### Consent + notification-channel preferences

- **`user_consents` is the operational state**, `audit_logs` is the
  history. Every grant/revoke writes one audit row via `audit_log()` in
  the same txn. No-op flips (granted=true → granted=true) write no audit
  row — DPDP auditability is about state changes, not re-affirmations.
- **`ON DELETE CASCADE` on `user_id`** — opposite of `audit_logs`
  (SET NULL). Consent for a non-existent user is meaningless; the row
  vanishes with the user. The audit-log entries documenting their
  grants survive.
- **Eager seeding at signup.** `_upsert_identity` calls
  `seed_default_consents(...)` on the new-user branch in the same txn.
  All later reads are simple SELECTs — no default-fallback logic in the
  hot path. Changing a default later affects only NEW signups.
- **`email_transactional` defaults to `true`** at signup —
  legally-borderline call. The signup UI MUST notify the user (sub-
  project F handles this). All other scopes default to `false`.
- **Sweep gate.** `sweep_notifications._dispatch_one` looks up consent
  between the user load and the channel dispatch. No consent →
  `status=CANCELLED`, `cancelled_at=now()`, terminal. Re-granting does
  NOT resurrect cancelled rows.
- **`CANCELLED` is a Postgres native-enum value** added via
  `ALTER TYPE ... ADD VALUE` inside an autocommit block (Alembic 0014).
  This is the canonical example of a future enum-extension migration.
- **Scopes are a `StrEnum` at the API boundary, plain TEXT in the DB.**
  Same pattern as `audit_logs.action`. Reserved scopes (WhatsApp, SMS,
  recruiter visibility, third-party sharing) ship in v0 with default
  `false` so adding their impls later doesn't need an enum migration.
```

## 11. Out of scope (call-outs)

- Flutter consent screens (sub-project F).
- Marketing-email content (no marketing kinds emit today).
- DSR-export's "include consent history" support — sub-project C will query `audit_logs WHERE action LIKE 'consent.%' AND actor_user_id = X`.
- Admin-side consent override (DSR-delete cycle initiated by admin) — sub-project D.
- WhatsApp / SMS adapters — providers TBD per spec § 14 #5.

## 12. Acceptance

- `0014_user_consents.py` upgrades + downgrades cleanly (including the autocommit-block enum extension).
- `UserConsent` model + `ConsentScope` StrEnum + `Notification.cancelled_at` declared.
- `get_consent` / `set_consent` / `seed_default_consents` ship with unit + integration tests covering: happy path, no-op-on-noop, soft-delete handling, idempotent re-seed.
- `auth/service.py:_upsert_identity` seeds on new-user. Integration test asserts 7 `user_consents` + 7 `audit_logs` rows on first sign-in.
- `GET` + `PATCH /v1/me/consents` endpoints behind `current_user` with the §7 wire shape.
- `sweep_notifications._dispatch_one` gates on consent. Integration test: revoke `email_transactional` → next sweep marks pending email row `CANCELLED`; `GET /v1/notifications` excludes it.
- `kpa-seed-consents` CLI backfills pre-existing users. Integration test verifies idempotency.
- CLAUDE.md updated per §10.
- All 252 existing integration tests stay green.
