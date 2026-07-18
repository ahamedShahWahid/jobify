# P4 Sub-project D — DSR delete (right-to-be-forgotten)

**Status:** approved 2026-05-29 (autonomous; brainstorm constraint pre-locked to "hard-delete PII, keep anonymized aggregates")
**Owner:** backend
**Scope:** sub-project D of the approved P4 plan. Depends on A (audit_logs, PR #25), B (consent, PR #26), and C (DSR export, PR #27 — the user is encouraged to export before deleting).

## 1. Why this slice exists

DPDP-Act-2023 § 12 grants every data principal the right to "erasure of personal data," subject to lawful retention exceptions. § 13 requires fulfillment "within a reasonable time" — interpreted as ≤ 30 days for routine requests. For our scale, immediate.

The audit-log entries `user.dsr_delete_requested` and `user.dsr_deleted` are reserved in the audit-logs spec (PR #25 § 4) and called out in the DSR-export spec (PR #27 § 9). This slice is the only path that emits them.

## 2. Brainstorm constraint (pre-locked design choice)

**Hard-delete PII, keep anonymized aggregates.**

Practical translation:

| Table | Strategy | Why |
|---|---|---|
| `users` | **soft-delete + scrub** (`email=NULL`, `phone=NULL`, `deleted_at=now()`) | Keep row as tombstone so FK references (Application, Match, AuditLog) still resolve. PII is gone. |
| `applicants` | **soft-delete + scrub** (`full_name=NULL`, `locations=NULL`, `notice_period_days=NULL`, `current_ctc=NULL`, `deleted_at=now()`) | Tombstone for downstream FK; PII zeroed. |
| `oauth_identities` | **hard delete** (DELETE rows) | No analytics value; raw identity linkage. |
| `refresh_tokens` | **hard delete** | Session secrets, useless after revocation. |
| `user_consents` | **hard delete** | Operational state, not history (history is in `audit_logs`). |
| `employer_users` (recruiter case) | **hard delete** | Recruiter ↔ employer membership. |
| `resumes` | **soft-delete + scrub** (`parsed_json=NULL`, `original_filename=NULL`, `storage_key=NULL`, `deleted_at=now()`) | Tombstone for `Application` recruiter-side analytics that may have surfaced this resume; PII content gone. Blob deleted separately. |
| `resume` blobs (object storage) | **durable asynchronous hard delete** | Copy each key into `outbox_events` before scrubbing `storage_key`; the outbox sweeper deletes with retries. |
| `applicant_embeddings` | **hard delete** | Vector encodes PII; row has no analytics value once the embedding is gone. |
| `notifications` | **hard delete** | Payload contains PII (e.g., job title in apply confirmations). |
| `saved_jobs` | **hard delete** | Private to user; no employer-side analytics value. |
| `applications` | **KEEP unchanged** (anonymized via tombstoned `applicants.applicant_id`) | Recruiter sees "deleted user" via Applicant's NULL `full_name`. Analytics preserved: apply counts, status transitions, source attribution. |
| `matches` | **KEEP unchanged** (anonymized via tombstoned applicants) | Eval substrate — score components + model_versions intact for offline weight calibration. |
| `audit_logs` | **KEEP unchanged** | Audit rows preserve `actor_user_id` pointing at the tombstone (still resolvable). No DSR removes evidence-of-process. |
| `employers` | **KEEP unchanged** (sole-owner edge case below) | Employer is org property, not personal data. |
| `jobs` | **KEEP unchanged** | Org property. |

### 2.1 Sole-owner employer edge case

If the deleted recruiter was the **last** `EmployerUser(role='owner', deleted_at IS NULL)` for one or more employers, those employers become ownerless. We do NOT auto-delete them — recruiters might have posted jobs that applicants applied to; deleting would orphan applications and matches.

The response includes a `warnings` array:

```json
"warnings": [
  {
    "type": "ownerless_employer",
    "employer_id": "...",
    "employer_name": "...",
    "message": "Employer 'Foo Inc' has no remaining owners. Contact privacy@kpa to reassign or close."
  }
]
```

Admin tooling (deferred to a later sub-project) handles reassignment.

### 2.2 audit_logs FK semantics

`audit_logs.actor_user_id` is `ON DELETE SET NULL` (PR #25 design). With soft-delete-and-scrub, the User row stays, so the FK reference is preserved — audit rows still have a non-NULL `actor_user_id` pointing at the tombstone. The `SET NULL` cascade only fires if we ever HARD-delete the User row (e.g., a future admin sub-project that fully purges tombstones after 7 years).

This is intentional: the export endpoint's audit_history query (`actor_user_id = user.id`) still works for the deleted user — a regulator audit of "what happened around this user's lifecycle" finds every event including the deletion itself.

## 3. Trigger and shape

### 3.1 HTTP endpoint

`DELETE /v1/me/dsr`

- **Verb:** DELETE.
- **Behind:** `current_user`. Any authenticated user can erase their own data.
- **Body (required):** `{"confirmation": "DELETE_MY_ACCOUNT"}`. Exact string match. Other values → 400 `confirmation_mismatch`.
- **Response status:** 200 (not 204) — body carries section counts + warnings for the client to display.

### 3.2 Errors

- 401 — no/invalid bearer.
- 400 `confirmation_mismatch` — body doesn't contain the literal confirmation token.
- 400 `missing_confirmation` — body has no `confirmation` field at all (Pydantic catches; surfaces as 422 technically but we standardize to 400 via the error handler — actually the existing codebase emits 422 here; let's accept Pydantic's default 422 rather than introduce a special-case).
- 404 — never. If the user is already soft-deleted, `current_user` returns 401 `user_not_found` (the dependency re-fetches and filters `deleted_at IS NULL`).
- 500 — assembly error. The `user.dsr_delete_requested` audit row is durable; the deletion may be partially applied. Admin must inspect.

### 3.3 Why DELETE over POST

REST conventional: DELETE indicates resource removal. The resource path `/v1/me/dsr` reads as "my DSR-managed data." A request-body-on-DELETE is unconventional but supported (httpx/Dio/curl all do it) and is the right shape for the confirmation token. The alternative — query-string `?confirmation=...` — leaks the token into access logs.

### 3.4 Idempotency

After successful DELETE, the user's existing JWTs IMMEDIATELY become invalid:
- `current_user` re-fetches the row and finds `deleted_at IS NOT NULL` → 401 `user_not_found`.

So a second DELETE attempt from the same client → 401, not 200. **Operationally idempotent** (the data is gone) but not HTTP-idempotent (200 → 401). The client should accept 401 as "already done" after a DELETE.

## 4. Audit trail

Two audit rows per successful delete, in this exact order:

1. **Pre-assembly:** `audit_log(action="user.dsr_delete_requested", actor=user, resource_type="user", resource_id=user.id, context={"request_id": ...})`.
   - `actor=user` — written + flushed BEFORE any destructive work, so the audit row exists even if assembly throws.
2. **Post-assembly:** `audit_log(action="user.dsr_deleted", actor=user, resource_type="user", resource_id=user.id, context={"request_id": ..., "section_counts": {...}, "warnings": [...]})`.
   - `actor=user` is still the deleted-user row (now tombstoned). The audit row's `actor_user_id` references the tombstone; `actor_role` snapshot preserves the role at action time.

The two audit rows write in the **same transaction** as the destructive work. If anything in the deletion graph fails, all of it rolls back including both audit rows. (The brainstorm-time alternative of "request row durable on failure" — used by export in PR #27 — is wrong here because partial deletion is worse than no deletion. Atomicity beats audit-row durability.)

## 5. Deletion orchestrator

`api/src/jobify_api/dsr/deleter.py`:

```python
async def delete_user_data(
    session: AsyncSession,
    *,
    user: User,
) -> DeleteReport:
    """Walk the deletion graph for a single user.

    Pure executor — does NOT write audit rows. The route handler writes
    user.dsr_delete_requested BEFORE this call and user.dsr_deleted AFTER.

    All work happens in the caller's transaction. If anything raises, the
    caller's txn rolls back and the deletion is fully reversed.
    """
```

### 5.1 Order of operations

The order matters because of FK dependencies and blob storage. Bottom-up by FK depth:

1. **Notifications** — hard delete by `user_id`.
2. **Refresh tokens** — hard delete by `user_id`. Important: also nullifies the `RefreshToken.rotated_from_id` self-FK references (already `SET NULL` per existing FK).
3. **OAuth identities** — hard delete by `user_id`.
4. **User consents** — hard delete by `user_id`.
5. **Employer-user memberships** — hard delete by `user_id`. (Record sole-owner-employer warnings BEFORE deleting so we still see them.)
6. **Saved jobs** — hard delete via `applicant.id` (CASCADE would handle but we do it explicitly for the report counts).
7. **Applicant embeddings** — hard delete via `applicant.id`.
8. **Resume blob intents** — for each Resume row, insert a `blob_delete` outbox event containing the storage key. It commits atomically with the DB scrub; no storage I/O occurs in this transaction.
9. **Resumes** — soft-delete + scrub fields. Keep `applicant_id` FK.
10. **Applicant** — scrub PII fields + set `deleted_at`. Keep `user_id` FK.
11. **User** — scrub PII fields + set `deleted_at`.
12. (Implicit) **applications + matches + audit_logs survive untouched.**

### 5.2 `DeleteReport`

Returned to the route for the response body:

```python
@dataclass
class DeleteReport:
    deleted_at: datetime
    section_counts: dict[str, int]   # e.g., {"notifications": 5, "refresh_tokens": 2, ...}
    warnings: list[OwnerlessEmployerWarning]
```

`OwnerlessEmployerWarning` is a tiny Pydantic model: `{type: str, employer_id: UUID, employer_name: str, message: str}`.

## 6. Storage blob deletion semantics

`sweep_outbox` leases the event and calls `Storage.delete(key)` after the DSR transaction commits. Missing objects are an idempotent success. Transient failures reschedule the event with backoff; terminal failures retain the key and error for inspection and `jobify-requeue-outbox` recovery.

## 7. Sole-owner employer detection

For a recruiter being deleted:

```sql
-- Find employers where the deleted user is the LAST live owner.
SELECT eu.employer_id, e.name
FROM kpa.employer_users eu
JOIN kpa.employers e ON e.id = eu.employer_id
WHERE eu.user_id = :user_id
  AND eu.role = 'owner'
  AND eu.deleted_at IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM kpa.employer_users eu2
    WHERE eu2.employer_id = eu.employer_id
      AND eu2.user_id != :user_id
      AND eu2.role = 'owner'
      AND eu2.deleted_at IS NULL
  )
```

For each result, append an `OwnerlessEmployerWarning` to the report. The employers stay; admin tooling handles them.

Applicant deletes never trigger ownerless-employer warnings (applicants don't own employers).

## 8. Re-signup after deletion

The `_upsert_identity` flow already handles this correctly:
1. OAuth provider claims arrive. No `OAuthIdentity` row matches (deleted in step 3 of the orchestrator).
2. Falls through to email-collision check: `User.email = claims.email AND deleted_at IS NULL`. Tombstone has `email=NULL` AND `deleted_at IS NOT NULL` — no collision.
3. Provisions a fresh user + applicant + identity + seeds consents (PR #26).

The new user has a different `user.id`. The old tombstone is orphaned (no FK points at the new user). Applications/matches FK'd to the old applicant stay anonymized.

## 9. CLAUDE.md updates

Add under "Architecture — non-obvious bits" after the DSR-export section:

```
### DSR delete

- **Soft-delete + scrub, not hard-delete the User row.** Hard-deleting users would CASCADE-wipe applications and matches (FKs to applicants → users), losing recruiter analytics and the eval substrate. The brainstorm constraint was "hard-delete PII, keep anonymized aggregates" — we honor it by tombstoning `users` and `applicants` with PII scrubbed, then hard-deleting the truly-PII tables around them.
- **Application-layer deletion graph, not FK CASCADE.** Several FKs are CASCADE, but the orchestrator walks the graph explicitly so report counts are stable and blob cleanup intents are recorded before storage keys are scrubbed.
- **Atomic transaction.** Unlike the export (whose `dsr_export_requested` row is durable on assembly failure), the delete's `dsr_delete_requested` audit row commits or rolls back atomically with all destructive work. Partial deletion is worse than no deletion.
- **`audit_logs.actor_user_id` references survive** as pointers to the tombstone — soft-delete-and-scrub keeps the User row, so the FK still resolves. `SET NULL` only fires if a future admin sub-project hard-deletes the tombstone (post-retention).
- **Re-signup works** because `_upsert_identity`'s email-collision check filters `deleted_at IS NULL` — tombstoned emails (scrubbed to NULL anyway) don't conflict.
- **Confirmation token in body, not query.** `DELETE /v1/me/dsr` with body `{"confirmation": "DELETE_MY_ACCOUNT"}` — query-string would leak the token into access logs.
- **Sole-owner employer edge case** surfaces a `warnings` entry in the response. The employer stays (admin tooling handles reassignment). Recruiter's `employer_users` rows still hard-delete.
- **Resume blob deletion is durable and asynchronous.** DB scrubbing and cleanup intent are atomic; storage deletion is at-least-once and operator-requeueable.
- **NO retry after a successful DSR delete.** Subsequent calls return 401 `user_not_found` because `current_user` re-fetches and the tombstone is soft-deleted. Clients should treat 401 as "already done" post-DELETE.
```

## 10. Out of scope (call-outs)

- Admin-initiated DSR-delete of another user. Separate admin sub-project.
- 30-day grace period with reversibility. Could ship as a `users.dsr_delete_scheduled_at` column + Celery beat. Not MVP — immediate deletion matches user expectation.
- Periodic alerting/dashboard for terminal failed outbox events.
- Tombstone hard-delete after N-year retention. Defer until we have data retention policy.
- Cross-region replication awareness (the blob delete is single-region). Defer to deploy-target sub-project (P5).
- WhatsApp / SMS unsubscribe at the BSP. Tracked when those channels ship.

## 11. Acceptance

- `DELETE /v1/me/dsr` returns 200 with `{deleted_at, section_counts, warnings}` shape.
- Wrong / missing confirmation → 400 / 422.
- `user.dsr_delete_requested` + `user.dsr_deleted` audit rows written in same txn as deletion.
- After delete: applications + matches survive with anonymized applicant; notifications + resume blobs + applicant_embedding + saved_jobs + oauth_identities + refresh_tokens + user_consents are hard-gone; users + applicants + resumes are tombstoned (PII scrubbed + `deleted_at` set).
- Sole-owner-employer detection surfaces a warning entry per affected employer; employer rows untouched.
- Re-signup after delete creates a fresh user (no email collision against tombstone).
- Existing JWTs become invalid (401 `user_not_found`) post-delete.
- CLAUDE.md updated per § 9.
- All 273 existing integration tests stay green.
