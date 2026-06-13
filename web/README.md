# Jobify Web

The public-facing web property for Jobify — three surfaces in one Vite + React + TS app:

- **Landing** (`/`) — the marketing page: hero, how-matching-works, the explanation
  differentiator, applicant + recruiter value props, CTA.
- **Explore** (`/explore`) — the applicant product: the matched feed, job detail with
  score breakdown + the "why this fits" explanation, and working apply / save / withdraw.
  Tabs for Your matches / Applied / Saved.
- **Trust** (`/trust`) — DPDP transparency: a system-status panel, the three rights
  (consent / export / delete), and a plain-language FAQ.

No UI framework — the design system lives in `src/styles/site.css` ("warm editorial
broadsheet": bone paper, persimmon accent, forest-green "verified", **Fraunces** display /
**Hanken Grotesk** body / **JetBrains Mono** for scores). Deliberately distinct from the
internal `console/` app's dark control-room look.

## Run

```bash
cd web
npm install
npm run dev        # http://localhost:5273
```

Landing and Trust are fully public (no auth). **Explore** needs an applicant session:

- **Continue with Google** (primary) — real sign-in via Google Identity Services. The Google
  ID token is exchanged server-side for a short-lived access token; see below.
- **Demo feed** — six seeded matches, full apply/save flow, no backend (`src/api/demo.ts`).
- **Live token** — paste an applicant access token + API base URL (dev aid). The API must list
  this origin in `JOBIFY_CORS_ALLOW_ORIGINS` (e.g. `http://localhost:5273`). A `401` mid-session
  clears the session and returns to the gate with an "expired" notice.

## Google sign-in

Real applicant sign-in uses Google Identity Services (GIS) `renderButton` on the gate, then
exchanges the Google ID token with the backend (`POST /v1/auth/oauth/google` with
`{ id_token }`), which returns a short-lived access token. **The ID token is exchanged
server-side; only the access token is held in memory** (no refresh-token rotation in v0 — a
`401` returns you to the gate, one click from re-signing in).

Config (Vite env — copy `.env.example` to `.env.local`):

| Var | Meaning |
| --- | --- |
| `VITE_GOOGLE_CLIENT_ID` | Google **Web** OAuth client id (`*.apps.googleusercontent.com`). Unset → the gate shows a muted hint and the button is hidden; demo + paste-token still work. |
| `VITE_API_BASE_URL` | API base for the exchange + live calls (default `http://localhost:8000`). |

To make it live for local dev:

1. **Google Cloud console** — the Web OAuth client must list `http://localhost:5273` under
   **Authorized JavaScript origins** (exact scheme + host + port, no trailing slash; `http`
   for localhost). The GIS token flow does **not** use redirect URIs.
2. **Backend** — include that same client id in `JOBIFY_GOOGLE_OAUTH_CLIENT_IDS` (the `aud`
   the API verifies), and add `http://localhost:5273` to `JOBIFY_CORS_ALLOW_ORIGINS`.

`npm run build` runs `tsc -b` then `vite build` → static bundle in `dist/` (HashRouter, so
it serves from any static host with no rewrite rules).

## Structure

- `src/api/types.ts` — wire types mirroring the FastAPI applicant models **verbatim**
  (`schemas.py`, `feed.py`, `applications.py`, `saved_jobs.py`, `me.py`). Note the feed/jobs
  `EmployerRead` carries `verified: bool`, not the recruiter `verified_at`/`gst`.
- `src/api/client.ts` — `JobifyClient` interface + `HttpClient` (live, problem+json-aware).
- `src/api/demo.ts` — `DemoClient`, seeded in-memory matches with mutable apply/save state.
- `src/auth/gsi.ts` — minimal GIS loader + `renderGoogleButton` (ambient types, no `@types`
  dependency); `src/auth/GoogleSignInButton.tsx` — the React wrapper used by the gate.
- `src/env.ts` + `src/vite-env.d.ts` — typed `import.meta.env` config (`GOOGLE_CLIENT_ID`,
  `API_BASE_URL`).
- `src/pages/Landing.tsx`, `src/pages/Trust.tsx`, `src/pages/explore/*`.
