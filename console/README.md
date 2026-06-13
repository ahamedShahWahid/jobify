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

## Google sign-in

"Continue with Google" is the primary sign-in path. It exchanges a Google ID token for an
access token against the backend (`POST {VITE_API_BASE_URL}/v1/auth/oauth/google`), then
runs the same role-based landing as a pasted token. Because the backend returns the user's
**existing** DB role, a recruiter gets a recruiter token and an admin an admin token — so it
"just works" for existing recruiters/admins. (First-time Google users provision as
`applicant` and land on the no-access page, which is correct: recruiters are elevated via
`POST /v1/employers`, admins via `uv run jobify-grant-admin <email>`.)

Only the short-lived access token (≤10 min) is held in memory — there is no refresh-token
rotation yet, so any `401` routes back to this screen where Google is one click away.

Build-time config (Vite env — copy `.env.example` → `.env`):

| Var                     | Purpose                                                                       |
| ----------------------- | ----------------------------------------------------------------------------- |
| `VITE_GOOGLE_CLIENT_ID` | Google **Web** OAuth client id (`*.apps.googleusercontent.com`). Unset ⇒ button hidden, muted hint shown; demo + paste-token still work. |
| `VITE_API_BASE_URL`     | API base for the exchange + live calls (default `http://localhost:8000`).      |

To make Google sign-in live:

1. On the Google **Web** OAuth client, add `http://localhost:5173` under **Authorized
   JavaScript origins** (scheme+host+port, no trailing slash; GIS uses no redirect URIs).
2. On the backend: include that same client id in `JOBIFY_GOOGLE_OAUTH_CLIENT_IDS`
   (it's the `aud` the API verifies), and add `http://localhost:5173` to
   `JOBIFY_CORS_ALLOW_ORIGINS`.
3. Set `VITE_GOOGLE_CLIENT_ID` (+ `VITE_API_BASE_URL` if not localhost) in `console/.env`
   and run `npm run dev`.

**Live mode (paste-token)** is the manual fallback below the Google button:

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
