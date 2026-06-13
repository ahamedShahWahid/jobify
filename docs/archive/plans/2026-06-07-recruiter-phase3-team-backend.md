# Recruiter Phase 3 — Employer Team Management Backend (R4) — Implementation Plan

> Just-in-time plan for the backend half of R4. Source spec:
> `docs/superpowers/specs/2026-06-06-recruiter-employer-experience-design.md` §5.
> Autonomous execution authorized (spec §"Execution authorization").

**Goal:** Add employer team management — member roster (add/role-change/remove) and
an invite flow (create/list/revoke + invitee accept/decline), with owner/member RBAC,
`employer.*` audit rows, role flips derived from membership, and outbox delivery.

## Core invariant (from spec §1)
Recruiter access derives from live `employer_users` rows:
- Any join path → bounded-flip `APPLICANT → RECRUITER` (never `ADMIN`).
- Losing the **last** live membership → bounded-flip `RECRUITER → APPLICANT`.
`current_user` re-fetches per request, so removal takes effect within the access TTL.

## Batches

### A — Schema (model + migration + settings)
- `settings.py`: `employer_invite_ttl_days: int = 14` (`KPA_EMPLOYER_INVITE_TTL_DAYS`).
- `db/models.py`: `EmployerInviteStatus(StrEnum)` = pending/accepted/revoked/expired;
  `EmployerInvite(Base)` per spec §5.2 table (soft-delete trio, FKs, native enum,
  partial-UNIQUE `(employer_id, email) WHERE deleted_at IS NULL AND status='pending'`).
- Migration `0018_employer_invites.py`: create `employer_invite_status` enum + table +
  partial unique index (raw SQL for the multi-predicate index, mirroring 0011).
- **Commit:** `feat(api): employer_invites schema (model + migration 0018)`

### B — RBAC + role-flip helpers
- `auth/dependencies.py`: `_require_employer_member(user, employer_id, session)` (uniform 404
  if no live link) and `_require_employer_owner(...)` (404 if no live link, 403 `not_an_owner`
  if link role != owner). Order: `_require_recruiter`-style role context is implicit via
  membership; member/owner checks run before resource lookups.
- A small `kpa/employers/membership.py` with `flip_to_recruiter(session, user_id)` and
  `maybe_demote_to_applicant(session, user_id) -> bool` (returns demoted flag). Reused by
  employers + invites routes and the existing create-employer path can stay as-is.

### C — Member + employer-invite endpoints (`routes/employers.py`)
- `GET  /v1/employers/{id}/members` (member-read)
- `POST /v1/employers/{id}/members` (owner) — direct-add existing user; 404 `user_not_found`,
  409 `already_a_member`; flip→recruiter; audit `employer.member_added`.
- `PATCH /v1/employers/{id}/members/{user_id}` (owner) — role change; last-owner guard
  (400 `last_owner`); audit `employer.member_role_changed`.
- `DELETE /v1/employers/{id}/members/{user_id}` (owner) — soft-delete link; last-owner +
  sole-owner-self guards; maybe-demote; audit `employer.member_removed`
  (`context.demoted_to_applicant`).
- `POST /v1/employers/{id}/invites` (owner) — create pending invite; 409 on live pending /
  existing membership; outbox `notifications` row (kind `employer_invite`) **only when the
  email maps to an existing user** (no user_id otherwise — documented MVP limit); audit
  `employer.invite_created`.
- `GET  /v1/employers/{id}/invites` (member-read) — live pending invites.
- `DELETE /v1/employers/{id}/invites/{invite_id}` (owner) — mark `revoked`; audit
  `employer.invite_revoked`.
- **Commit:** `feat(api): employer member + invite endpoints (owner/member RBAC)`

### D — Invitee-facing endpoints (`routes/invites.py`, registered in app_factory)
- `GET  /v1/me/invites` — pending, non-expired invites where `email == current_user.email`,
  with employer name. Lazy-expire `pending`→`expired` on read.
- `POST /v1/me/invites/{invite_id}/accept` — email-match + pending + not-expired (410/404 on
  expiry); insert membership(role=invite.role); mark accepted + accepted_user_id;
  flip→recruiter; audit `employer.invite_accepted`.
- `POST /v1/me/invites/{invite_id}/decline` — email-match; mark `revoked`.
- **Commit:** `feat(api): invitee-facing /v1/me/invites accept/decline`

### E — Integration tests (savepoint-isolated, per spec §7.1)
- Member RBAC: member 403 on mutate, member-read ok, 404 user_not_found, 409 already_a_member,
  last-owner guard on demote/remove, sole-owner-cannot-remove-self.
- Role flips: direct add / accept raise applicant→recruiter; last-removal drops
  recruiter→applicant; admin untouched. (Use `concurrent_async_client` where a real refetch
  of `users.role` is asserted.)
- Invites: create (+ outbox row), duplicate-pending 409, revoke, `/v1/me/invites` email-matched,
  accept (membership+flip+audit), accept-after-expiry rejected, accept by wrong user rejected.
- Audit: each mutation writes the expected `employer.*` row with `actor_role` + context.
- **Commit:** `test(api): employer team management integration coverage`

## Definition of Done
All new endpoints behave per spec §5; `uv run pytest -m integration` + unit + `ruff` + `mypy`
green. No change to applicant or existing recruiter flows.
