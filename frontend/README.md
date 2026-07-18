# Jobify Frontend

One Vite + React + TS app; two surfaces under one HashRouter:

- `/employers` — recruiter marketing (`src/sites/employers`)
- `/console` — internal admin + recruiter ops (`src/sites/console`)

The applicant-facing web surface (`src/sites/web`) was removed — the Flutter app
(`app/`) is the applicant client (iOS/Android/web). `/` redirects to `/employers`.

Shared transport/session/auth/env live in `src/shared`.

## Entry points

One app, one bootstrap: `index.html` → `src/main.tsx` → `src/App.tsx` (a single
`<HashRouter>` that mounts each surface's route fragment). Routes are hash-based, so
every URL lives under `/#/`. Per surface:

| Surface | Dev entry URL | Route module | Mount root |
| --- | --- | --- | --- |
| **employers** (recruiter marketing) | `http://localhost:5173/#/employers` | `src/sites/employers/EmployersRoutes.tsx` | `/employers` |
| **console** (jobify-internal admin ops) | `http://localhost:5173/#/console/signin` | `src/sites/console/ConsoleRoutes.tsx` | `/console` |

- **employers** — `/employers` (landing) and `/employers/verify`.
- **console** — entered at `/console/signin`; jobify-internal admin ops only (audit trail, employer verification, user actions).
- **employers** (in addition to the marketing pages) — an authenticated recruiter workspace entered at `/employers/signin`; signed-in recruiters land on `/employers/dashboard` (jobs, applicants, team & invites, settings).

Each surface mounts its own `SessionProvider` (from `src/shared/session`) inside its
route fragment, so sessions are independent per surface. In production both ship
in one static `dist/` served from a single origin — the surfaces are sibling route
subtrees, not separate builds.

## Run

    cd frontend
    npm install
    cp .env.example .env   # set VITE_GOOGLE_CLIENT_ID, VITE_API_BASE_URL
    npm run dev            # http://localhost:5173

The console surface needs 5173 in the API's `JOBIFY_CORS_ALLOW_ORIGINS`
and the dev origin in the Google Web OAuth client's Authorized JavaScript origins.

## Build / typecheck

    npm run build          # tsc -b && vite build → dist/

## CSS scoping

Each surface is wrapped in a `.surface-employers` or `.surface-console` class;
per-surface CSS is scoped inside that selector to prevent cross-surface bleed.

## Design tokens

Tokens are global, not per-surface: `src/shared/styles/tokens.css` defines every
color/spacing/font variable once on `:root` (light) and `:root[data-theme="dark"]`
(dark). Surfaces consume `var(--token)` — they must not redefine tokens on
`.surface-*`. See `frontend/CLAUDE.md` for the full design-system rules.
The static `frontend/styleguide/` is a hand-maintained snapshot of those tokens.
