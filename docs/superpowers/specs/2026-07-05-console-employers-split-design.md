# Split recruiter ops out of `/console` into `/employers`

**Status:** approved for planning
**Scope:** frontend only (`frontend/`)

## Problem

`/console` was built to serve two audiences — jobify-internal admins (moderation,
audit, employer verification) and external recruiters (job postings, applicants,
team/invites) — sharing one sign-in gate, one session, one API client, one nav
shell. That's wrong: recruiters are external users and should never reach the
internal ops console. They need their own workspace, reachable from the
`/employers` marketing site they already land on.

This also explains why "Open the console" showed up as the primary CTA across
the employers marketing funnel (`Chrome.tsx`, `Landing.tsx`, `Verify.tsx`) — it
was, technically, where a recruiter was supposed to end up. That CTA/copy is
part of what's being corrected here.

## Goals

- `/console` becomes strictly jobify-internal (admin role only). No recruiter
  code, copy, nav, or API surface remains there.
- Recruiters get an authenticated workspace under `/employers` — sign-in,
  dashboard, job CRUD, applicants, team/invites, account settings — with a
  demo mode (seeded fixtures, no backend needed) for prospect-facing demos.
- Backend and Flutter app are untouched — server-side role gating on
  `/v1/jobs*`, `/v1/employers*` etc. already doesn't care which frontend
  surface calls it; the Flutter recruiter experience (`2026-06-06-recruiter-employer-experience-design.md`) is separate and unaffected.

## Non-goals

- No new backend endpoints or role/permission changes.
- No visual redesign beyond re-branding the moved nav shell/sign-in gate from
  console's internal-ops aesthetic to the employers surface's existing voice.
- No changes to the Flutter recruiter flow.

## Design

### 1. Console shrinks to admin-only

- `console/area.ts`: `Area` type collapses from `"admin" | "recruiter"` to
  just `"admin"`. `areasForRole`/`landingFor` simplify accordingly — any
  non-admin role maps to no-access.
- `console/components/Shell.tsx`: drop the `"recruiter"` `NAV` section and the
  area-filtering logic (`sections = NAV.filter(...)` becomes unconditional
  since there's only one section left).
- `console/api/client.ts`: `ConsoleClient` interface and `HttpClient` drop
  every recruiter method — `listMyJobs`, `createJob`, `patchJob`, `deleteJob`,
  `listJobApplicants`, `myEmployers`, `listMembers`, `addMember`,
  `changeMemberRole`, `removeMember`, `listInvites`, `createInvite`,
  `revokeInvite`. Keeps `me()` + admin methods (`listAuditLogs`,
  `suspendUser`, `unsuspendUser`, `listEmployersForVerification`,
  `verifyEmployer`, `rejectEmployer`).
- `console/api/demo.ts`: drop recruiter-only fixture sections (`jobs`,
  `applicants`, `members`, `invites` maps and their `DemoClient` methods);
  keep `employers` (referenced by the verification queue), `auditLogs`,
  `suspendedUsers`, `verificationQueue`.
- `console/pages/SignIn.tsx` + `NoAccess`: copy changes to admin-only
  language ("jobify staff only"). **A recruiter who signs in at
  `/console/signin` sees the plain no-access page — no redirect to
  `/employers`.** Drop the "recruiter" demo-role option from the sign-in
  picker.
- `console/pages/recruiter/*`, `console/api/recruiterJobs.ts` are deleted from
  `console` (moved, not duplicated — see below).
- `console/pages/Settings.tsx` stays in console (admin-only now, still "any
  signed-in operator" but that's just admins going forward).

### 2. `/employers` gains an authenticated recruiter workspace

Same surface, same bundle, same `.surface-employers` CSS scope — public
marketing pre-auth, recruiter ops post-auth. New pieces:

- `employers/session.tsx` — its own `createSession()` instance (own
  `SessionProvider`, independent from console's, per the existing
  one-session-per-surface rule in `frontend/CLAUDE.md`).
- `employers/api/client.ts` — new `EmployerClient` interface: `me()` +
  every recruiter method moved from console's `ConsoleClient`.
- `employers/api/demo.ts` — new `DemoClient implements EmployerClient`,
  seeded with the recruiter-relevant fixtures moved from console's demo.ts
  (`employers`, `jobs`, `applicants`, `members`, `invites`). Demo mode is
  reachable from `/employers/signin` the same way console's is today.
- `employers/api/recruiterJobs.ts` moved as-is from console.
- `employers/pages/dashboard/{Dashboard,Jobs,JobComposer,Applicants,Team}.tsx`
  — moved as-is from `console/pages/recruiter/*`, import paths updated.
- `employers/pages/Settings.tsx` — new, near-identical to console's (identity,
  theme, session/log-out; no résumé/DSR data, same as console's rationale).
- `employers/pages/SignIn.tsx` — new gate page at `/employers/signin`:
  Google sign-in (reusing `shared/auth/GoogleSignInButton`) + a demo-mode
  toggle (recruiter role only — no admin option, this surface never serves
  admins). Re-branded copy/voice to match the employers marketing site
  (not console's "OPERATIONS CONSOLE // internal operations" framing).
- `employers/components/Shell.tsx` — new nav shell for the authenticated
  zone, adapted from console's `Shell.tsx` minus the area-switch logic (one
  nav section: Dashboard / Jobs / Team), re-branded wordmark/tagline.
- Routes added to `EmployersRoutes.tsx`: `/employers/signin`,
  `/employers/dashboard`, `/employers/jobs`, `/employers/jobs/new`,
  `/employers/jobs/:jobId/edit`, `/employers/jobs/:jobId/applicants`,
  `/employers/team`, `/employers/settings`, `/employers/no-access`. Gated by
  a `RequireSession`/role check mirroring console's pattern — role must be
  `recruiter`; anything else → `/employers/no-access`.

### 3. Marketing CTA copy

`Chrome.tsx` (masthead + footer), `Landing.tsx` (hero + mid-page + closing
CTAs), `Verify.tsx`: replace `CONSOLE_URL = "#/console/signin"` links/copy
("Open the console") with an in-surface link to `/employers/signin` ("Sign
in" / "Get started"). Since the target is now same-surface, these become
plain `<Link>` (no `target="_blank"`/`rel="noreferrer"`, no `CONSOLE_URL`
constant — same pattern as every other internal nav link on this surface).

## Error handling

- Wrong-role sign-in (recruiter → console, or applicant/admin → employers)
  always lands on that surface's own no-access page. No cross-surface
  redirects in either direction — each surface's gate is self-contained.
- Token/session expiry behavior is unchanged (inherited from
  `shared/session/createSession`, already surface-agnostic).

## Testing

- `npm run build` (`tsc -b && vite build`) must stay clean after the move.
- Manual smoke: sign in as the seeded recruiter test account at
  `/employers/signin`, confirm dashboard/jobs/applicants/team all load; sign
  in as the seeded admin account at `/console/signin`, confirm audit/
  verification/users still work and recruiter nav is gone; confirm a
  recruiter hitting `/console/signin` gets the admin-only no-access page.
