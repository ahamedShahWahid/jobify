# Jobify Frontend

One Vite + React + TS app; three surfaces under one HashRouter:

- `/` — applicant + public marketing (`src/sites/web`)
- `/employers` — recruiter marketing (`src/sites/employers`)
- `/console` — internal admin + recruiter ops (`src/sites/console`)

Shared transport/session/auth/env live in `src/shared`.

## Run

    cd frontend
    npm install
    cp .env.example .env   # set VITE_GOOGLE_CLIENT_ID, VITE_API_BASE_URL
    npm run dev            # http://localhost:5173

Live surfaces (web, console) need 5173 in the API's `JOBIFY_CORS_ALLOW_ORIGINS`
and the dev origin in the Google Web OAuth client's Authorized JavaScript origins.

## Build / typecheck

    npm run build          # tsc -b && vite build → dist/

## CSS scoping

Each surface is wrapped in a `.surface-web`, `.surface-employers`, or `.surface-console`
class; per-surface CSS is scoped inside that selector to prevent cross-surface bleed.

## Design tokens

Each surface owns its own CSS-variable token system in `src/sites/<surface>/styles/`.
The static `frontend/styleguide/` is a hand-maintained snapshot of those tokens.
