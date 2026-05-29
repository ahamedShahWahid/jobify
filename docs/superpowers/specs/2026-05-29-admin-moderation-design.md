# P4 Sub-project E — Admin moderation

**Status:** approved 2026-05-29 (autonomous; user confirmed continuation)
**Owner:** backend
**Scope:** sub-project E of the approved P4 plan. Builds on A (audit_logs, PR #25) — every admin action writes through `audit_log()`.

## 1. Why this slice exists

There's no path to handle abuse today. A spam applicant signing up with 20 accounts? No lever. An abusive recruiter posting harassing jobs? No lever. A regulator requesting "show me everything user X did"? No tool — the data is in `audit_logs` but no endpoint queries it.

This slice ships the minimum admin surface: suspend a user, unsuspend them, view audit logs with filters. Admins use the API directly via curl/Postman — a Flutter admin UI is deferred (see § 2 non-goals).

## 2. Non-goals

- **Admin web/Flutter UI.** Admins curl the endpoints today. A dedicated admin app lives in a separate slice (probably post-P5 after we pick a deploy target).
- **Job unpublish endpoint** (`admin.job.unpublished`). Recruiters can close their own jobs via `DELETE /v1/jobs/{id}` already; admin override is rare enough to defer until we see real abuse. The action-slug is reserved in CLAUDE.md per PR #25.
- **Admin-initiated DSR-export of another user.** Reserved for a follow-up if/when a regulator asks. Today an admin runs SQL.
- **Admin-initiated DSR-delete of another user.** Same — reserved.
- **MFA for admins.** Sub-project G.
- **Bulk admin operations** (suspend N users at once, bulk audit export). Out of scope.
- **Audit-log retention sweep.** Per PR #25 § 11 — deferred until table grows past ~10M rows.

## 3. New columns on `users`

```sql
ALTER TABLE kpa.users
  ADD COLUMN suspended_at        TIMESTAMPTZ NULL,
  ADD COLUMN suspension_reason   TEXT NULL;
```

- `suspended_at IS NULL` ⇔ active. `IS NOT NULL` ⇔ suspended.
- `suspension_reason` is admin-supplied free text (~255 chars). Optional; surfaced via the suspended-user error to the locked-out user *and* via the audit row.

No `unsuspended_at` column — when the admin unsuspends, both fields go back to NULL. The audit row captures the unsuspension event.

### 3.1 Effect on `current_user`

`auth/dependencies.py:current_user` already rejects `deleted_at IS NOT NULL` with `401 user_not_found`. Add a sibling check:

```python
if user is None or user.deleted_at is not None:
    raise HTTPException(401, detail="user_not_found")
if user.suspended_at is not None:
    raise HTTPException(401, detail="user_suspended")
```

The 401 slug `user_suspended` is new — clients (Flutter) need to distinguish it from `user_not_found` (which means "you're gone") and `invalid_access_token` (which means "refresh me"). For `user_suspended` the refresh interceptor must NOT attempt a refresh; per the existing PR #24 interceptor logic, any 401 with `detail != invalid_access_token` short-circuits to sign-out. That's the right behavior here — suspended users sign out cleanly.

## 4. `_require_admin`

`auth/dependencies.py` gains a sibling to `_require_recruiter`:

```python
async def _require_admin(user: User) -> User:
    """403 not_an_admin if the caller is not an admin."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="not_an_admin")
    return user
```

Used inline by each admin route (not as a `Depends` chain) to keep the import surface narrow.

## 5. Endpoints

All under `/v1/admin/*`. All behind `current_user` + `_require_admin`.

### 5.1 Suspend a user

```
POST /v1/admin/users/{user_id}/suspend
Body: {"reason": "spam_signup"}
```

Required body field `reason` (string, max 255 chars). Sets `suspended_at = now()`, `suspension_reason = reason`. Idempotent — re-suspending an already-suspended user updates the reason and writes a new audit row.

Returns 200 with the (now-suspended) user row:

```json
{
  "id": "...",
  "email": "...",
  "role": "applicant",
  "suspended_at": "...",
  "suspension_reason": "spam_signup"
}
```

Error ladder:
- 401 — `current_user` unauthenticated / suspended / deleted.
- 403 `not_an_admin` — caller isn't admin.
- 404 `user_not_found` — target user doesn't exist or is soft-deleted.
- 400 `cannot_suspend_self` — admin cannot suspend their own account. Defensive guard.
- 422 — body validation.

Writes one `admin.user.suspended` audit row:
- `action="admin.user.suspended"`
- `actor=current_user` (the admin)
- `resource_type="user"`
- `resource_id=target_user.id`
- `context={request_id, reason, target_user_role}`

### 5.2 Unsuspend a user

```
DELETE /v1/admin/users/{user_id}/suspend
```

No body. Clears both `suspended_at` and `suspension_reason`. Idempotent — calling on an already-active user is a 200 no-op (no audit row written if there was no state change, mirrors the consent helper's no-op-on-noop pattern).

Returns 200 with the (now-active) user row.

Writes one `admin.user.unsuspended` audit row when there's an actual state change.

### 5.3 Audit logs viewer

```
GET /v1/admin/audit-logs
  ?actor_user_id=<uuid>
  ?resource_type=<string>
  ?resource_id=<uuid>
  ?action=<string>         (exact match)
  ?from=<iso8601>
  ?to=<iso8601>
  ?cursor=<opaque base64>
  ?limit=<int, default 50, max 200>
```

All filters optional. Combined as AND. Order: `created_at DESC, id DESC` (mirrors the existing `(actor_user_id, created_at DESC)` index path).

Response:

```json
{
  "items": [
    {
      "id": "...",
      "actor_user_id": "..." | null,
      "actor_role": "applicant" | ...,
      "action": "consent.granted",
      "resource_type": "consent",
      "resource_id": "...",
      "context": {...},
      "created_at": "..."
    },
    ...
  ],
  "next_cursor": "..." | null
}
```

Cursor: opaque base64 of `{created_at, id}` — mirrors the existing `/v1/jobs/me` cursor pattern in `routes/jobs.py`.

**No audit row written for the viewer itself.** Per spec § 2 non-goals: regulator-grade self-auditing-of-admins is overkill at MVP scale. Add later if needed; the access logs (Fluent Bit → Elasticsearch) capture every admin GET via `request_id`.

**ETag:** none. The data changes constantly and admins want fresh reads.

## 6. CLI — `kpa-grant-admin`

Without a "create admin" path, the database has no admin user when this PR merges. Add a one-off CLI:

```bash
uv run --env-file=.env kpa-grant-admin user@example.com
```

Behavior:
- Find user by email (live row only).
- Update `role = ADMIN`. Idempotent — if already admin, log "no change" and exit 0.
- Writes one `auth.role.granted` audit row with `context={from_role, to_role, actor="cli"}`. Audit `actor_user_id` is **NULL** (system actor, like the Celery beats).
- If no such user (email mismatch or soft-deleted), exits 1 with a clear error.

Same pattern as `kpa-seed-jobs` and `kpa-seed-consents` (with `_apply_in_session` test seam).

Why a CLI and not a route: bootstrapping. There's no admin to call an admin endpoint to grant admin to themselves. The CLI is the bootstrap; future admin operations (grant another user admin) can ship as a route in a follow-up.

## 7. CLAUDE.md updates

Add to "Architecture — non-obvious bits", under the existing `### Auth + JWT invariants` section (the closest neighbor):

```
### Admin moderation

- **`/v1/admin/*` is gated by `_require_admin` after `current_user`.** Layer order: `current_user` → 401 invariants → `_require_admin` → 403 not_an_admin → DB read. No DB lookups for admin-only resources happen before the role check.
- **Suspended users get 401 `user_suspended`** from `current_user`, not 403. The slug is distinct from `user_not_found` and `invalid_access_token` so clients can show "Your account has been suspended. Contact support." On Flutter the refresh interceptor short-circuits to sign-out for any non-`invalid_access_token` 401 — that means suspended users are signed out cleanly without an attempted refresh.
- **`users.suspended_at` AND `users.suspension_reason` clear together.** Unsuspending is `UPDATE users SET suspended_at=NULL, suspension_reason=NULL`. Never leave a stale reason on an unsuspended row — admin tooling reads (reason IS NOT NULL) as "this user is suspended" defensively.
- **`admin.user.suspended` writes a new audit row on every call**, even if the user is already suspended (re-suspension with a different reason is meaningful audit evidence). `admin.user.unsuspended` is no-op-on-noop — calling unsuspend on an active user writes no audit row.
- **Suspending self is blocked** with 400 `cannot_suspend_self`. The admin cannot lock themselves out — recovery would need direct DB access.
- **`kpa-grant-admin <email>` is the bootstrap path.** No `POST /v1/admin/users/{id}/grant-admin` route — bootstrap chicken-and-egg. Once the first admin exists, follow-ups can ship a route.
- **Audit-log viewer (`GET /v1/admin/audit-logs`)** does NOT write an audit row for the query itself. Self-auditing-of-admins is overkill at MVP scale; access logs (Fluent Bit → Elasticsearch) capture each call's `request_id`.
- **Reserved action slugs (still unused by this PR):** `admin.job.unpublished`, `admin.user.dsr_export_requested`, `admin.user.dsr_deleted`. Don't repurpose them.
```

## 8. Acceptance

- Migration 0016 adds the two columns; round-trip clean.
- `current_user` rejects suspended users with `401 user_suspended`.
- `_require_admin` rejects non-admins with `403 not_an_admin`.
- `POST /v1/admin/users/{id}/suspend` body `{reason}` — sets state, writes audit, returns user with PII.
- `DELETE /v1/admin/users/{id}/suspend` — clears state, writes audit on state change.
- `POST .../suspend` on self → 400.
- `GET /v1/admin/audit-logs` filters work for `actor_user_id`, `resource_type`, `resource_id`, `action`, `from`, `to`; cursor pagination works.
- `kpa-grant-admin <email>` flips role + writes audit; idempotent.
- Integration tests cover happy paths + the 400/403/404 ladder.
- CLAUDE.md updated per § 7.
- All 279 existing integration tests stay green.
