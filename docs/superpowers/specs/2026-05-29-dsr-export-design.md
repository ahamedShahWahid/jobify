# P4 Sub-project C — DSR export pipeline

**Status:** approved 2026-05-29 (autonomous; follows A→B→C plan locked in earlier)
**Owner:** backend
**Scope:** sub-project C of the approved P4 plan. Depends on A (`audit_logs` substrate, PR #25) and B (consent + sweep gate, PR #26).

## 1. Why this slice exists

DPDP-Act-2023 § 11 grants every data principal the right to access a copy of "the personal data processed about them, and the purpose of such processing." § 13 requires the platform respond "within a reasonable time" — interpreted as ≤ 30 days; for our scale, immediate.

The audit-log entries for `user.dsr_export_requested` and `user.dsr_export_completed` are reserved in the audit-logs spec (PR #25 § 4). This slice is the only path that emits them.

## 2. Non-goals

- DSR-delete (the right-to-be-forgotten redress mechanism) — sub-project D.
- An admin-side DSR portal — admins use SQL today; the user-facing endpoint is what regulators require.
- Async / queued exports — see § 5 below for why sync is acceptable at MVP scale.
- Including the original resume binaries in the export blob. The export references each resume's `storage_key` + content-type + size; binaries are downloaded separately via a follow-up endpoint (deferred until applicant-side download lands; the recruiter-side `/v1/applications/{id}/resume` already exists).
- Rate limiting. MVP-acceptable — if abuse emerges, add a per-user `users.last_dsr_export_at` check.
- Cryptographic export-blob signing. Useful for legal evidence chain-of-custody but out of MVP scope.

## 3. Trigger and shape

### 3.1 HTTP endpoint

`POST /v1/me/dsr/export`

- **Verb:** POST. It writes audit rows (state change). GET would be misleading.
- **Behind:** `current_user`. Applicants, recruiters, and admins can each pull their own export. ADMIN does NOT get an "export any user's data" endpoint via this route — that's an admin sub-project.
- **Body:** none. Future extension might offer format choice (`{format: "json"|"ndjson"}`) but v0 ships JSON-only.
- **Response status:** 200 OK.
- **Response headers:**
  - `Content-Type: application/json; charset=utf-8`
  - `Content-Disposition: attachment; filename="kpa-data-export-{user_id}-{iso_timestamp}.json"`
  - `Cache-Control: no-store` (prevents intermediaries caching personal data).
- **Response body:** the JSON envelope (§ 4).

### 3.2 Errors

- 401 — no/invalid bearer (`current_user`).
- No 403 — every authenticated user has the right to their own data.
- 500 — internal error. The audit row for `user.dsr_export_requested` writes BEFORE the heavy data assembly; if assembly fails, the request row is durable but the `user.dsr_export_completed` row never lands. A regulator audit of "did this user's DSR request fulfill?" can detect the missing-completion case via SQL.

## 4. Export envelope shape

Top-level keys, all required (use `null` or `[]` for empty):

```json
{
  "version": "1",
  "exported_at": "2026-05-29T12:00:00+05:30",
  "exported_for_user_id": "...",
  "user": { ... },
  "applicant": { ... } | null,
  "oauth_identities": [ ... ],
  "resumes": [ ... ],
  "applicant_embedding": { ... } | null,
  "applications": [ ... ],
  "saved_jobs": [ ... ],
  "matches": [ ... ],
  "notifications": [ ... ],
  "user_consents": [ ... ],
  "audit_history": [ ... ],
  "employer_memberships": [ ... ],
  "owned_jobs": [ ... ],
  "redactions": [ ... ],
  "notes": [ ... ]
}
```

### 4.1 Per-section payload

Each table-derived section uses the **same field set as the existing API**. For example, `applications[i]` matches `ApplicationListResponse` items today — including `created_at`, `updated_at`, `status`, `source`, `job_id`. This means the export is self-documenting against the public API; consumers can map fields back to the documented endpoints.

Sections that have no public API today (`refresh_tokens`, `applicant_embedding`):

- **`applicant_embedding`** — includes the vector. `{embedding: [float, ...], dim: 1536, model_id: "gemini-embedding-2", canonicalized_text_hash: "...", created_at, updated_at}`. The vector is hundreds of KB but bounded; acceptable inline.
- **`refresh_tokens`** — NOT included. See § 4.3.

### 4.2 `audit_history`

Every row where `actor_user_id = self.id`, plus every row where `(resource_type, resource_id)` ties to one of the user's domain rows. The simplest defensible scope for v0:

```sql
SELECT * FROM kpa.audit_logs
WHERE actor_user_id = :user_id
   OR (resource_type = 'resume' AND resource_id IN (SELECT id FROM ... resumes for this user))
   OR (resource_type = 'consent' AND resource_id IN (SELECT id FROM user_consents WHERE user_id = :user_id))
ORDER BY created_at DESC
```

For MVP we simplify to **only `actor_user_id = self.id`**. This covers every consent.granted/revoked, every dsr_export_requested, every recruiter resume access INITIATED by the user (zero, for applicants). The `(resource_type, resource_id)` clause matters more for recruiters viewing an applicant's resume — but that's an audit entry against the RECRUITER, not the applicant; it would appear in the recruiter's export, not the applicant's. **Sensitive design choice that the regulator might push back on:** if asked, we'd extend to `resource_id IN ...`-style joins in v1.

### 4.3 `redactions` array

Documents what we EXCLUDED so the user knows the export isn't exhaustive. Example entries:

```json
[
  {"type": "refresh_tokens", "reason": "session secrets — not personal data; would let an exposed export be used to impersonate the user"},
  {"type": "resume_binaries", "reason": "metadata included; binaries downloadable on request from privacy@kpa"}
]
```

This is itself part of DPDP transparency — § 11(b) requires informing the user "of the categories of personal data... processed."

### 4.4 `notes` array

Free-form human notes appended by the builder. Example: `"This export was generated automatically. For data older than {sign-up date}, contact privacy@kpa."` Allows v0 to ship operational context without schema churn.

## 5. Why sync (not async / queued)

At MVP scale: ~ 10 applicants, low single-digit recruiters, < 1,000 total `audit_logs` rows per user. Total assembly time is dominated by the embedding vector serialization (hundreds of KB). Sync completes in < 500ms in the worst observed local case.

**If/when** an applicant accumulates > 10,000 audit rows (multi-year veteran), the embedding query stays trivially small and the audit history grows linearly. We add NDJSON streaming response or async + signed-download-url at that point. Not now.

Sync is a one-way door REVERSIBLE: the endpoint contract is "POST returns the JSON" — switching to "POST returns 202 + status URL" later is a breaking change. To keep options open, we document the v0 sync contract as `format=immediate` in the spec, so a future v0 client knows to handle `202 Accepted` too. Implementation in v0 only emits 200; no behavior change today.

## 6. Audit trail for the export itself

Two audit rows per successful export, in this exact order:

1. **Pre-assembly:** `audit_log(action="user.dsr_export_requested", actor=user, resource_type="user", resource_id=user.id, context={"request_id": ...})`.
2. **Post-assembly, pre-response:** `audit_log(action="user.dsr_export_completed", actor=user, resource_type="user", resource_id=user.id, context={"request_id": ..., "section_counts": {"applications": N, ...}})`.

`section_counts` lets a regulator audit "what did we tell the user" without requiring the export blob itself.

If assembly throws after #1: the request row is durable, the completion row is not. The exception is re-raised — FastAPI's error handler emits 500 with the request_id. Future admin tooling can replay failed requests.

Both audit rows commit with the request — same caller-owns-the-txn contract as everything else. The two rows write in DIFFERENT savepoints so a transient query failure during assembly doesn't roll back the `user.dsr_export_requested` row (which is itself evidence).

## 7. Builder module

`src/kpa/dsr/__init__.py`:

```python
async def build_user_export(
    session: AsyncSession,
    *,
    user: User,
) -> UserExport:
    """Assemble the export envelope. Pure read-only — does not write any
    audit row. The route handler writes the audit rows around this call.

    Raises nothing custom — DB errors propagate to the route, which
    converts to 500 via the standard handler.
    """
```

`UserExport` is a Pydantic v2 model with one field per top-level envelope key. The model is the contract — `model_dump_json(by_alias=True)` produces the wire format.

Per-section helpers (one per table) live as private functions in the same module: `_collect_applicant(session, user)`, `_collect_resumes(session, applicant_id)`, etc. Each returns a list of Pydantic items.

### 7.1 Recruiter-side data

If `user.role == UserRole.RECRUITER`:

- `applicant`, `resumes`, `applicant_embedding`, `applications`, `saved_jobs`, `matches` are `null` / `[]`. The user has no applicant facet.
- `employer_memberships` lists their `EmployerUser` rows with the linked `Employer` snapshot (name, domain, verified_at).
- `owned_jobs` lists every `Job` row at every employer where the recruiter has a live `EmployerUser` link.

Admin role: same as recruiter for v0 (no `EmployerUser` rows expected). All applicant + recruiter sections empty.

## 8. Out of scope (call-outs for later sub-projects)

- Asynchronous DSR with status polling.
- Signed download URLs for large exports.
- Including resume binaries inline (or as a multipart attachment) — needs an applicant-side resume download endpoint first.
- Including the `(resource_type, resource_id)` join in `audit_history` for resources the user owns.
- DSR-export for admins targeting another user — separate admin sub-project.
- Rate limiting — `users.last_dsr_export_at` is a one-line addition when needed.
- Localized notes / cover letter PDF — out of MVP scope.

## 9. CLAUDE.md updates

Add under "Architecture — non-obvious bits" after the consent section:

```
### DSR export

- **Sync HTTP, JSON envelope.** `POST /v1/me/dsr/export` returns the dump immediately as `application/json` with `Content-Disposition: attachment`. MVP-acceptable at our scale; switch to async + signed-URL when audit history exceeds ~10K rows per user.
- **`refresh_tokens` are NEVER in the export.** They are session secrets, not personal data. A `redactions` entry in the envelope documents the exclusion so the user is informed. When MFA ships, the `totp_secret` (and recovery codes) get the same treatment.
- **`audit_history` is `actor_user_id = self.id`** in v0 — not the full `(resource_type, resource_id)` join. Documented limit; expand when a regulator pushes back.
- **Two audit rows per export.** `user.dsr_export_requested` (pre-assembly) and `user.dsr_export_completed` (post-assembly). The request row is durable even if assembly throws — that's a feature, not a bug. Failed-export replay becomes admin tooling later.
- **Reserved action slugs for sub-project D (DSR-delete):** `user.dsr_delete_requested`, `user.dsr_deleted`. Don't reuse these prefixes.
- **Recruiters get a different envelope** — applicant sections are empty, `employer_memberships` + `owned_jobs` populated. Admins get an "all-empty" envelope today (no `EmployerUser` rows).
```

## 10. Acceptance

- `routes/dsr.py:POST /v1/me/dsr/export` returns 200 with a JSON envelope matching § 4.
- Two `audit_logs` rows per export: `user.dsr_export_requested` + `user.dsr_export_completed`.
- `refresh_tokens` never appear in the export; a `redactions` entry documents the exclusion.
- Integration tests cover: applicant happy path, recruiter happy path (verifies `employer_memberships` + `owned_jobs`, asserts applicant sections empty), authentication required (401), refresh-token redaction, audit rows written + counts.
- CLAUDE.md updated per § 9.
- All 268 existing integration tests stay green.
