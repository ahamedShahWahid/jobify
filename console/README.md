# Jobify Console

Internal operations web console for the Jobify platform — two areas in one app:

- **Moderation (admin)** — audit-log explorer + user suspend/unsuspend. The API has no
  user-search endpoint, so moderation is keyed by user UUID; any actor/user id in the
  audit trail is clickable and pre-fills the action form.
- **Recruiting** — dashboard, jobs CRUD (create/edit/close/delete + applicant rosters
  with match scores and explanations), employer team & invites.

Vite + React 18 + TypeScript, no UI framework — the design system lives in
`src/styles/console.css` ("control-room editorial": dark phosphor base, amber = admin,
teal = recruiter, Bricolage Grotesque / Spline Sans Mono / Newsreader).

## Run

```bash
cd console
npm install
npm run dev        # http://localhost:5173
```

**Demo mode** (default tab on the sign-in screen) needs no backend — the full console
runs against seeded in-memory fixtures (`src/api/demo.ts`). Pick **Admin** or **Recruiter**
as the demo persona: role decides which area you land in and which nav the rail shows
(the backend's `users.role` is single-valued, so the console gates each area to its role
rather than letting out-of-role clicks 403).

**Live mode** talks to the FastAPI service:

1. Start the API (see `api/README.md`) and add the console origin to CORS:
   `JOBIFY_CORS_ALLOW_ORIGINS=http://localhost:8080,http://localhost:5173`
2. Obtain a Bearer access token for an admin or recruiter user (sign in via the
   Flutter app and copy the access token; grant admin with `uv run jobify-grant-admin
   <email>`). Tokens are short-lived (≤10 min) and held in memory only.
3. Paste base URL + token on the sign-in screen.

Admins land in Moderation; recruiters land at the Job Desk. The role chip in the rail
shows who the API thinks you are. Access tokens are short-lived (≤10 min): any `401`
clears the session and routes back to the sign-in gate with an "expired" notice
(`HttpClient`'s `onUnauthorized` hook), rather than stranding you on dead pages.

## Structure

- `src/api/types.ts` — wire types mirroring the FastAPI Pydantic models **verbatim**
  (keep in lockstep with `api/src/jobify/routes/*.py`; don't guess shapes).
- `src/api/client.ts` — `ConsoleClient` interface + `HttpClient` (live, RFC 7807-aware).
- `src/api/demo.ts` — `DemoClient`, the seeded in-memory impl.
- `src/pages/admin/*` — Audit explorer, User actions.
- `src/pages/recruiter/*` — Dashboard, Jobs (+drawer form), Applicants, Team.

`npm run build` runs `tsc -b` then `vite build` → static bundle in `dist/`
(HashRouter, so it serves from any static host with no rewrite rules).
