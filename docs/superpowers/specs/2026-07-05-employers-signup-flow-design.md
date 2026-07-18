# Employers self-serve sign-up flow — Design Spec

## Context

The `/employers` surface (split out from `/console` earlier in this same session — see `docs/superpowers/specs/2026-07-05-console-employers-split-design.md`) currently offers three ways in on its sign-in gate: Google OAuth, a "Demo Data" mode against in-memory seeded fixtures, and a "Live API" manual paste-token mode.

A brand-new Google user always provisions with `role=applicant` (`api/src/jobify_api/auth/service.py:154`). The backend already has a fully self-serve path for such a user to become a recruiter: `POST /v1/employers` (`api/src/jobify_api/routes/employers/core.py`) creates an employer, links the caller as its owner, and flips their role `APPLICANT → RECRUITER` via `flip_to_recruiter()` — no admin, invite code, or approval step required. The frontend never exposes this: a first-time visitor who signs in today lands on `/employers/no-access`, which only offers an email address to "get set up," implying the wrong (ops-mediated) model.

Demo Data mode was designed as a way for prospects to explore the product before committing. The product decision now is to retire that in favor of the real thing: sign up for real, and your first job posting is free (this pricing already exists on the marketing page — "Starter ₹0 / first role").

## Goals

- Remove Demo Data mode from `/employers` entirely (toggle UI + `DemoClient` fixture code). Console's own demo mode is untouched.
- Give a brand-new signed-in user (role=applicant, no employer yet) a direct path to create their company and post their first role, with no dead ends and no ops involvement.
- Keep the manual paste-token option on employers' sign-in (useful internally to test against a real backend without going through Google each time).

## Non-goals

- No billing/payment integration — matches the existing free-first-role pricing already live on the marketing page.
- No invite-code or email-domain-allowlist gating for the create-employer step — mirrors the backend's existing self-serve invariant exactly; adding gating here would be a product decision beyond this spec.
- No change to how *existing* recruiters sign in (Google → straight to dashboard, unchanged) or to console's demo mode.

## Design

### 1. Sign-in page (`employers/pages/SignIn.tsx`)

- Remove the `mode` state (`"demo" | "live"`), the Demo/Live mode-tab buttons, the "Explore the full employer workspace..." paragraph, and the "Enter demo workspace" button / `connectDemo` call.
- Google sign-in stays the primary, top-billed option.
- The manual-token form (API base URL + bearer token fields) stays, but is reframed as a secondary, de-emphasized path — a small link/disclosure ("paste an access token instead") rather than a co-equal tab next to Google, since there is no more Demo/Live pairing to tab between.
- Copy: the eyebrow/description should acknowledge first-time use — e.g. replace "recruiters only — new Google users provision as applicants and see the no-access page" with wording that reflects the new reality: new Google users are welcome and will be guided to set up their company (exact copy is an implementation-time wording pass, not load-bearing for this spec).

### 2. `DemoClient` removal

- Delete `frontend/src/sites/employers/api/demo.ts` outright — nothing in `employers/` references `DemoClient` once the sign-in page stops offering it.
- `frontend/src/shared/session/createSession.tsx`'s config currently requires both `makeLive` and `makeDemo`. Make `makeDemo` **optional** (`makeDemo?: (role?: string) => TClient`). The store's `connectDemo` keeps its existing signature (no breaking change for console's usage), but throws a clear error (`"Demo mode is not available on this surface"`) if called when `config.makeDemo` is absent. This is a defensive-only path — employers' `SignIn.tsx` never wires a button to `connectDemo` once the toggle is removed, so it's unreachable in normal use. Console's config still supplies `makeDemo` and is completely unaffected.
- `frontend/src/sites/employers/session.tsx` drops its `makeDemo` line and its `DemoClient` import.

### 3. Onboarding route

- New page `frontend/src/sites/employers/pages/Onboarding.tsx`, new route `/employers/onboarding`.
- Positioned in the route tree as a sibling of `/employers/settings` and `/employers/no-access`: inside `RequireSession`, but **not** inside the `RequireRecruiter`-gated subtree (a non-recruiter must be able to reach it).
- `RequireRecruiter` (in `EmployersRoutes.tsx`) changes its redirect target based on role:
  - `role === "applicant"` → `/employers/onboarding`
  - any other non-recruiter role (e.g. `admin`) → `/employers/no-access` (unchanged message: "This workspace is for recruiters...")
- Form fields, matching `EmployerCreate` exactly: **Company name** (required, 2–200 chars) and **GST** (optional, exactly 15 chars if provided — no additional format validation beyond length, matching the backend).
- On submit: call the new `EmployerClient.createEmployer(payload)` method → `POST /v1/employers`. On success (201 `EmployerRead`):
  1. Call the session store's new `refreshIdentity()` method (see below) to re-fetch `/v1/me` so `session.identity.role` reflects `recruiter` without requiring a fresh sign-in.
  2. Navigate to `/employers/jobs/new`. `JobComposer.tsx` already auto-selects `employers[0]` when creating a job with no employer chosen yet (`JobComposer.tsx:116-118`), so the newly-created (and only) employer is pre-selected with no further change needed there.
- Error handling: surface the backend's `409 employer_name_taken` as a clear inline message ("That company name is already registered — try a slightly different name") rather than a generic error; surface 422 validation errors (name length, GST length) inline per-field, consistent with the existing `assertJobConstraints`-style validation UX elsewhere in this codebase.

### 4. New shared pieces

- `EmployerClient` interface (`employers/api/client.ts`) gains `createEmployer(payload: EmployerCreate): Promise<EmployerRead>` → `POST /v1/employers`. `EmployerCreate` type added to `employers/api/types.ts` (`{ name: string; gst?: string | null }`).
- `shared/session/createSession.tsx`'s `SessionStore` interface gains `refreshIdentity(): Promise<TIdentity>` — calls `client.me()` on the *existing* connected client and updates `session.identity` in place (no new client, no new token). This is the one piece of shared, cross-surface infrastructure this spec touches; it's additive (new optional-to-use method) and doesn't change existing `connectLive`/`connectGoogle`/`connectDemo`/`signOut` behavior, so console is unaffected.

### 5. What does NOT change

- `JobComposer.tsx`, `Jobs.tsx`, `Dashboard.tsx`, `Team.tsx`, `Applicants.tsx` — no changes; they already work once the caller has recruiter role and an employer.
- Console's sign-in, demo mode, or session handling — untouched.
- Marketing site (`Landing.tsx`, `Chrome.tsx`, `Verify.tsx`) CTAs — all already point at `/employers/signin`, which remains correct; no copy changes required by this spec (the "Start free" / "Sign in" wording already reads fine given the new flow — a first-time user clicking "Sign in" now gets guided to a real free-first-role setup instead of a dead-end).

## Testing / verification plan

- `npm run build` stays clean (this project's sole frontend check).
- Manual smoke test (dev server, live backend — this flow cannot be demo'd since demo mode is gone):
  1. Sign in with a brand-new Google account (or a manually-pasted token for a user with `role=applicant` and no employer) → confirm landing on `/employers/onboarding`, not `/employers/no-access`.
  2. Submit the form with a valid name → confirm redirect to `/employers/jobs/new` with the new employer pre-selected in the composer.
  3. Post a role → confirm it appears in `/employers/jobs` and `/employers/dashboard` tiles update.
  4. Sign in with an existing admin-role account on `/employers` → confirm they still land on `/employers/no-access` with the admin-appropriate message, not onboarding.
  5. Attempt to create a second employer with a name that collides with an existing one → confirm the inline "already registered" message, not a raw 409.
  6. Confirm the Demo Data toggle no longer appears anywhere on `/employers/signin`, and confirm `/console/signin`'s demo mode is unaffected.

## Files touched (implementation-time reference, not exhaustive)

- Modify: `employers/pages/SignIn.tsx`, `employers/session.tsx`, `employers/api/client.ts`, `employers/api/types.ts`, `employers/EmployersRoutes.tsx`, `shared/session/createSession.tsx`
- Create: `employers/pages/Onboarding.tsx`
- Delete: `employers/api/demo.ts`
