# Recruiter & Employer Experience — Design Spec

**Date:** 2026-06-06
**Status:** Approved (brainstorm complete) — ready for implementation plan
**Scope:** R1–R4 in a single spec (role-aware app shell, recruiter onboarding, recruiter dashboard + job management, employer team management with invites). Spans **new backend** (R4 only) + **Flutter** (R1–R4).

---

## Execution authorization

The user has granted **blanket permission to proceed through implementation autonomously**. Once the implementation plan is approved, the implementer should NOT stop for per-task or tactical approval checkpoints — execute the plan end to end, surfacing only genuine blockers (ambiguous contract, failing-and-unexplained test, destructive/irreversible action). This matches the user's standing `feedback-autonomous-execution` and `feedback-execution-cadence` preferences.

---

## 1. Problem & context

The KPA Flutter app today is **entirely candidate-facing**: a hardcoded four-tab shell (Feed / Saved / Applications / Profile) and a router that only distinguishes signed-in from signed-out. The backend already ships a near-complete recruiter API (`POST /v1/employers`, `GET /v1/employers/me`, `GET /v1/jobs/me`, `POST`/`PATCH`/`DELETE /v1/jobs`, `GET /v1/jobs/{id}/applicants`, recruiter résumé download) — but **no Flutter UI consumes any of it**, and a recruiter who signed in would land on `/feed` and get a `403 not_an_applicant`.

One capability has **no backend at all**: employer *team management* (an owner adding/removing recruiters). `EmployerUser.role` allows `'owner'`/`'member'` but the model comment says `'member'` is `(future)`, and there is no endpoint to list, add, invite, or remove members.

This spec covers the whole arc:

- **R1 — Role-aware foundation** (Flutter only)
- **R2 — Recruiter onboarding** (Flutter only; backend ready)
- **R3 — Recruiter dashboard + job management** (Flutter only; backend ready)
- **R4 — Employer team management with invites** (new backend + Flutter)

### Core invariant (drives R4 and onboarding)

**Recruiter access is derived from employer membership, not an intrinsic property of the person.** The global `users.role` is a *computed consequence* of live `employer_users` rows:

- Joining an employer by **any** path (onboarding, direct add, accepted invite) bounded-flips `APPLICANT → RECRUITER` (never touches `ADMIN`).
- Losing your **last** membership bounded-flips `RECRUITER → APPLICANT`.

This is safe because `current_user` (`auth/dependencies.py`) re-fetches the user row on every request, so a removed recruiter loses recruiter access within the ≤10-min access-token TTL — no forced logout, no token revocation needed. Rationale: a recruiter typically joins under a company email that ceases to exist after departure; their recruiter access must end when their membership ends.

---

## 2. R1 — Role-aware foundation (Flutter)

### 2.1 Surface role into routing

Extend the auth state so the router can branch **synchronously** (no async provider read mid-redirect):

- `SignedIn` (`app/lib/data/auth/auth_state.dart`) gains `final UserRole role;` (a new `UserRole` enum in the data layer: `applicant`, `recruiter`, `admin`, `unknown` — with `@JsonKey(unknownEnumValue: UserRole.unknown)` semantics; parse from the wire `String`).
- Both `SignedIn` construction sites in `auth_repository_impl.dart` set role:
  - `_exchangeGoogleIdToken` → from `dto.user.role` (the OAuth response already carries it — `AuthUserDto.role`).
  - `refreshSession` → from `meDto.role` (already fetches `/v1/me`).
- `bootstrap_controller.dart` sets role from its `/v1/me` fetch.
- A small `currentRoleProvider` (derives `UserRole?` from `authStateProvider`) is available for widgets that need to branch (e.g., Profile tab content).

### 2.2 Two coexisting shell subtrees, one router

Rather than rebuilding the `keepAlive: true` router on role change (which would drop navigation state), keep **one** `GoRouter` with two `StatefulShellRoute.indexedStack` subtrees:

- **Applicant subtree** (unchanged paths): `/feed`, `/saved`, `/applications`, `/profile` (+ their existing nested routes).
- **Recruiter subtree** (new paths): `/recruiter/dashboard`, `/recruiter/jobs`, `/recruiter/employer`, `/recruiter/profile` (+ nested routes below).

A new recruiter `KpaShellScaffold` variant supplies the recruiter `NavigationDestination`s (Dashboard / Jobs / Employer / Profile). The applicant scaffold is unchanged.

### 2.3 Role-aware redirect

Extend the redirect in `router.dart`:

- `SignedOut` → existing `/signin?next=…` behavior (unchanged).
- `SignedIn` with `role == recruiter` (or `admin`) landing on an **applicant-only** route → redirect to `/recruiter/dashboard`.
- `SignedIn` with `role == applicant` landing on a **recruiter** route → redirect to `/feed`.
- Onboarding flips role live: `_exchangeGoogleIdToken`/me-refresh pushes a new `SignedIn(role: recruiter)` → `_AuthChangeNotifier` fires → redirect re-runs → app re-renders into recruiter mode **without restart**.

`Routes` (`routing/routes.dart`) gains the recruiter path constants.

---

## 3. R2 — Recruiter onboarding (Flutter; backend ready)

### 3.1 Entry point
A **"I'm hiring — post a job"** CTA on the applicant **Profile** screen (and optionally on the empty-feed state). Visible only to `role == applicant`.

### 3.2 Onboarding screen
Route `/onboarding/employer` (top-level, outside both shells). Form:
- **Employer name** — required, 2–200 chars.
- **GST** — optional; if present, exactly 15 chars, client-side format check (mirrors backend `min_length=15, max_length=15`).

Submit → `POST /v1/employers` `{name, gst?}`.

- `201` → refresh `/v1/me` (role now `recruiter`) → push `SignedIn(role: recruiter)` → redirect lands on `/recruiter/dashboard`.
- `409 employer_name_taken` → inline field error on the name field.

### 3.3 Data layer
New Flutter `employers` feature: `EmployerRepository` (+ impl) and `EmployersApi`. DTO `EmployerDto` mirrors `EmployerRead` **exactly**: `{id, name, gst?, verified_at?, created_at}` (`verified_at` nullable → drives a "verified" badge).

---

## 4. R3 — Recruiter dashboard + job management (Flutter; backend ready)

### 4.1 Data layer — DTOs mirrored against real contracts

New `recruiter-jobs` feature in `app/lib/data/jobs/` (or a `recruiter/` subfolder). DTOs mirror the real backend shapes (verified against `routes/jobs.py` + `routes/feed.py`):

- `RecruiterJobDto` = `JobRead` + extras:
  `{id, title, description, locations: List<String>, min_exp_years: int, max_exp_years: int, ctc_min: double?, ctc_max: double?, status: String, posted_at, employer_verified: bool, applicant_count: int, surfaced_match_count: int}`.
  Note: `ctc_*` arrive as JSON `float|null` (NOT Decimal strings — this endpoint's `JobRead` types them `float | None`); `status` is a plain string (`"open"`/`"closed"`) → parse to the existing `JobStatus` enum.
- `RecruiterJobsPage` = `{items: List<RecruiterJobDto>, next_cursor: String?}` (opaque base64 cursor).
- `ApplicantOfJobDto` = `{application_id, applicant_id, display_name: String?, email: String?, status: String, applied_at, match_score: double?, match_explanation: {fit, caveat}?}`.
- `ApplicantsOfJobPage` = `{items, next_cursor}`.
- Job create/patch request bodies mirror `JobCreate`/`JobPatch`: `{employer_id, title, description, locations, min_exp_years, max_exp_years, ctc_min?, ctc_max?, status}`; PATCH is all-optional. **`ctc_*` on the request side are Decimal** server-side — send as JSON numbers; the client validates `max >= min` for both exp and CTC bands to mirror the backend `model_validator`.

`RecruiterJobsRepository` methods: `listMyJobs({status?, cursor?})`, `createJob(...)`, `patchJob(id, ...)`, `deleteJob(id)`, `listApplicants(jobId, {cursor?})`, `downloadApplicantResume(applicationId)`.

### 4.2 Screens

- **Recruiter Dashboard** (`/recruiter/dashboard`) — header summary cards (open jobs / total applicants / surfaced matches), summed client-side from the first page(s) of `GET /v1/jobs/me`, plus a "recent jobs" preview list. (No new backend aggregate endpoint; MVP sums client-side. If the job count grows past one page this is approximate — acceptable for MVP, noted as a follow-up to add a `/v1/employers/{id}/stats` endpoint.)
- **My Jobs** (`/recruiter/jobs`) — paginated `GET /v1/jobs/me` using the shared `PagedState<T>` + `loadNextPage` helpers (`presentation/paging/`). A toggle adds `?status=closed` (backend returns open+closed when `status` is passed). Each row: title, status chip, `applicant_count`, `surfaced_match_count`. Row → recruiter job detail.
- **Recruiter Job Detail** (`/recruiter/jobs/:id`) — read view of the job + actions: Edit, Close (status PATCH), View applicants. Distinct from the applicant `JobDetailScreen` (which calls applicant-only `GET /v1/jobs/{id}` and would 403 for a recruiter). MVP may render detail from the `RecruiterJobDto` already in the list rather than a separate fetch.
- **Post / Edit Job** (`/recruiter/jobs/new`, `/recruiter/jobs/:id/edit`) — shared form widget. `employer_id` resolved from `GET /v1/employers/me`: auto if one employer, picker if several. `POST`/`PATCH /v1/jobs`. Client mirrors band validators.
- **Job Applicants** (`/recruiter/jobs/:id/applicants`) — paginated `GET /v1/jobs/{id}/applicants`. Each row: `display_name`/`email`, `applied_at`, `match_score`, `match_explanation.fit`. Tap → **download résumé** via `GET /v1/applications/{id}/resume` (binary; on web trigger a browser download, on mobile open/share — MVP may use the simplest platform-appropriate path and document any deferral, consistent with the DSR-export clipboard precedent).

### 4.3 Mutation → invalidation
On create/patch/delete, invalidate the My-Jobs list controller + the affected job's detail provider (mirrors the applicant-side "no feed mutation, invalidate the list" convention).

---

## 5. R4 — Employer team management with invites (NEW backend + Flutter)

### 5.1 Permission model

`employer_users.role ∈ {owner, member}` (CHECK constraint already allows both):

- **Owner** = "admin of the employer": manage members/invites **and** jobs.
- **Member** = recruiter: post/manage jobs, view applicants; **cannot** manage members/invites.

RBAC for every new endpoint: any **live member** of the employer may *read* the roster/invites; only an **owner** may mutate (add / invite / change-role / remove / revoke).

A shared backend helper `_require_employer_owner(user, employer_id, session)` (and `_require_employer_member(...)` for reads) enforces this, returning uniform `403`/`404` per the codebase's existing stance (don't leak existence).

### 5.2 New data model

New table `employer_invites` (follows the standard soft-delete pattern: `id` uuid4, `created_at`, `updated_at`, `deleted_at`):

| column | type | notes |
|---|---|---|
| `employer_id` | FK → employers.id | |
| `email` | TEXT (normalized lower) | the invitee |
| `role` | TEXT, CHECK `IN ('owner','member')` | role granted on accept |
| `status` | native enum `employer_invite_status` `(pending, accepted, revoked, expired)` | |
| `invited_by_user_id` | FK → users.id, `ON DELETE SET NULL` | |
| `expires_at` | TIMESTAMPTZ | default `now() + KPA_EMPLOYER_INVITE_TTL_DAYS` (default 14) |
| `accepted_user_id` | FK → users.id, nullable | set on accept |
| `token` | TEXT, nullable | reserved for future unauthenticated email-link accept; **MVP acceptance is authenticated + email-matched and does not require it** |

Partial-UNIQUE index `(employer_id, email) WHERE deleted_at IS NULL AND status = 'pending'` — at most one live pending invite per (employer, email).

Migration: hand-written Alembic revision creating the table + the `employer_invite_status` native enum. (Enum *creation* is fine in a normal migration; only *adding a value to an existing* enum needs the autocommit dance — not applicable here.)

### 5.3 New endpoints

**Members:**
- `GET /v1/employers/{id}/members` (member-read) → `[{user_id, email, display_name?, role, added_at}]`.
- `POST /v1/employers/{id}/members` (owner) — body `{email, role}`. **Direct add of an existing user**: look up account by email; if found → insert `employer_users(role)`, bounded-flip `APPLICANT→RECRUITER`, audit `employer.member_added`. `404 user_not_found` if no account ("use an invite"). `409 already_a_member` if a live link exists.
- `PATCH /v1/employers/{id}/members/{user_id}` (owner) — `{role}`. Promote member→owner / demote owner→member. Guard: cannot demote the **last owner**. Audit `employer.member_role_changed`.
- `DELETE /v1/employers/{id}/members/{user_id}` (owner) — soft-delete the link. Guards: cannot remove the **last owner**; cannot remove **yourself if sole owner**. **After removal, if the user has zero remaining live memberships → bounded-flip `RECRUITER→APPLICANT`.** Audit `employer.member_removed` with `context.demoted_to_applicant: bool`.

**Invites (owner-managed):**
- `POST /v1/employers/{id}/invites` (owner) — `{email, role}`. Create pending invite (`expires_at` default 14d). **Delivery rides the existing notifications outbox** — insert a `notifications` row (channel `email`, a new type e.g. `employer_invite`) so the `LoggingEmailChannel` stub logs `email.sent`; real SES stays deferred. `409` if a live pending invite or an existing membership already covers that email. Audit `employer.invite_created`.
- `GET /v1/employers/{id}/invites` (member-read) → pending invites for the employer.
- `DELETE /v1/employers/{id}/invites/{invite_id}` (owner) — mark `revoked` (soft). Audit `employer.invite_revoked`.

**Invites (invitee-facing):**
- `GET /v1/me/invites` (any signed-in user) → pending, non-expired invites where `invite.email == current_user.email` (with employer name for display).
- `POST /v1/me/invites/{invite_id}/accept` — authorize by `invite.email == current_user.email` + `status == pending` + not expired. → insert `employer_users(role=invite.role)`, mark invite `accepted` + `accepted_user_id`, bounded-flip `APPLICANT→RECRUITER`. Audit `employer.invite_accepted`. (A brand-new signup sees the invite here and accepts — no signup-path change; matching is by email.)
- `POST /v1/me/invites/{invite_id}/decline` — mark `revoked` (reuses the existing status; no separate `declined` value to avoid a needless enum entry); same `email == current_user.email` auth check. (Optional; included for completeness.)
- Expired invites: acceptance returns `410`/`404`; a lazy check flips `pending`→`expired` on read/accept (no beat task required for MVP).

All mutations write one `audit_logs` row in the caller's transaction (per the audit-substrate convention: structlog line first where one already exists, then `audit_log(...)`). Action slugs under the reserved `employer.*` prefix: `employer.member_added`, `employer.member_role_changed`, `employer.member_removed`, `employer.invite_created`, `employer.invite_accepted`, `employer.invite_revoked`.

### 5.4 Employer dashboard + team UI (Flutter)

**Employer tab** (`/recruiter/employer`, 3rd recruiter tab):
- **Employer details**: name, GST, verified badge (from `verified_at`).
- **Org stats** (MVP: client-summed from `/v1/jobs/me`, same approximation as the recruiter dashboard).
- **Member roster** (`GET …/members`): owners see remove + change-role controls; members see read-only.
- **Invite recruiter** (owners): form (email + role) → `POST …/invites`; a **pending-invites list** with revoke.
- Multi-employer: if `GET /v1/employers/me` returns >1, an employer **switcher** selects the active employer (a `keepAlive` provider holding the active employer id); single employer is auto-selected. Job-post `employer_id` and the team views all key off the active employer.

**Invitee surface** (applicant side): a **"Pending invitations"** screen reachable from the applicant Profile (and/or a banner), backed by `GET /v1/me/invites`, with accept/decline. On accept → role flips → recruiter shell.

### 5.5 Mid-session demotion (Flutter)
When a recruiter route returns a role-mismatch (e.g., a recruiter endpoint now `403`s, or a `/v1/me` refresh shows `role == applicant`), the data layer refreshes `/v1/me` and pushes the updated `SignedIn(role: applicant)`; the role-aware redirect then moves them into the applicant shell. Recruiter-owned jobs remain owned by the **employer** (jobs FK the employer, not the user), so removal never orphans postings.

---

## 6. Cross-cutting

### 6.1 Profile tab — role-aware
The Profile screen is shared but branches on `currentRoleProvider`: recruiters see employer info + sign-out + privacy; the résumé / my-applications / feed-oriented links are hidden for them. Applicants see today's Profile unchanged **plus** the onboarding CTA and the "Pending invitations" entry.

### 6.2 Component reuse
- Pagination: reuse `PagedState<T>` + `loadNextPage` (`presentation/paging/`) for My Jobs, Applicants, Members.
- Async UI: reuse `AsyncValueWidget`, `KpaErrorView`, `KpaEmptyState`, `KpaLoadingView`.
- Score display: reuse `KpaScoreBadge` for applicant match scores.
- DTO convention: plain `@JsonSerializable` by default, `@freezed` only where `copyWith` is needed.
- Magic strings as enums with `unknownEnumValue` sentinels (`UserRole`, reuse `JobStatus`/`ApplicationStatus`).

### 6.3 Error & RBAC conventions (backend)
- Uniform `404` across unknown / wrong-employer / soft-deleted (don't leak existence) — mirror `_load_recruiter_job`.
- Role checks **before** any id lookup (applicant/member hits `403` before a DB read for the resource).
- Unique-violation detection walks the `__cause__` chain + `await session.rollback()` (mirror `create_employer`).

---

## 7. Testing

### 7.1 Backend (integration, savepoint-isolated)
- Member endpoints: owner-only mutation (member gets `403`), member-read allowed, `404 user_not_found` on direct-add of a non-user, `409 already_a_member`, last-owner guard on demote/remove, sole-owner-cannot-remove-self.
- Role flips: direct add / invite accept raise `APPLICANT→RECRUITER`; removal of last membership drops `RECRUITER→APPLICANT`; `ADMIN` never touched.
- Invites: create (+ outbox `notifications` row written), duplicate-pending `409`, revoke, `GET /v1/me/invites` email-matched only, accept (membership + role flip + audit), accept-after-expiry rejected, accept by wrong user rejected.
- Audit: each mutation writes exactly the expected `employer.*` row(s) with correct `actor_role` snapshot + `context`.
- Use the established three-client pattern; role-flip-visibility tests that need a real refetch use `concurrent_async_client`.

### 7.2 Flutter
- Unit: new repos/controllers (including the role-aware redirect logic and `SignedIn.role` propagation through both sign-in paths + bootstrap + refresh).
- Widget: onboarding form (validation + 409), recruiter dashboard, My Jobs list (pagination + status toggle), job create/edit form (band validators), applicants list, team roster (owner vs member controls), invite form + pending list, invitee accept/decline.
- Reuse `test/helpers/` `MockInterceptor` + `fake_repositories.dart`; add `FakeEmployerRepository`, `FakeRecruiterJobsRepository`, `FakeInvitesRepository`.
- Widget tests use `ThemeData.light(useMaterial3: true)` (avoid `buildTheme`'s GoogleFonts network fetch).

---

## 8. Build order (for the plan)

1. **R1 foundation** — `UserRole` enum, `SignedIn.role`, role-aware redirect, recruiter shell scaffold + empty recruiter routes. (Unblocks everything.)
2. **Employers data layer + R2 onboarding** — `EmployerRepository`, onboarding screen, role-flip-live wiring.
3. **R3 recruiter-jobs data layer + screens** — dashboard, My Jobs, job form, applicants, résumé download.
4. **R4 backend** — migration (`employer_invites` + enum), `_require_employer_owner/member`, member + invite endpoints, audit slugs, outbox wiring, integration tests. *(Atomic commits where a consumer needs the new contract.)*
5. **R4 Flutter** — employer/team tab, invite form + pending list, invitee accept/decline screen, mid-session demotion handling.

Each step is independently testable; backend R4 lands with its tests before the R4 Flutter UI consumes it.

---

## 9. Explicit non-goals / deferred

- Real email delivery (SES) — invites ride the `LoggingEmailChannel` stub via the outbox.
- Unauthenticated email-link invite acceptance (the `token` column is reserved but unused at MVP; acceptance is authenticated + email-matched).
- A dedicated `/v1/employers/{id}/stats` aggregate endpoint (dashboard sums client-side at MVP).
- Employer verification workflow (admin-side) — out of scope; `verified_at` is display-only here.
- Global role demotion auditing beyond the `context.demoted_to_applicant` flag.
- `expired`-status beat task (lazy expiry on read/accept suffices for MVP).
