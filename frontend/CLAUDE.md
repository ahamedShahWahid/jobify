# CLAUDE.md — frontend (unified Vite + React + TS web app)

Load-bearing invariants for the web app: three route-prefixed surfaces under one HashRouter — `/` (applicant/public, `src/sites/web`), `/employers` (recruiter marketing, `src/sites/employers`), `/console` (admin + recruiter ops, `src/sites/console`); shared transport/session/auth/env in `src/shared`. Auto-loaded when working under `frontend/`. Dev/build/env reference is in `frontend/README.md`.

> These are the shared-HashRouter pitfalls — things that silently send users to the wrong surface or leak styles across surfaces.

- **One app, three sibling route subtrees** — `index.html` → `src/main.tsx` → `src/App.tsx` mounts each surface's route fragment under one `<HashRouter>`. All three ship in one static `dist/`; they are NOT separate builds. Each surface mounts its own `SessionProvider` (sessions are independent per surface).
- **Every internal nav literal must carry the surface prefix.** Grep for ALL forms when migrating/adding routes — `grep -rnE "(to=\{?[\"'\`]|navigate\([\"'\`])/(seg)" src` — backtick-template ``to={`/console/${id}`}`` and single-quote `navigate('/console')` slip past quote-only greps.
- **Raw `<a href="/#anchor">` breaks under the shared HashRouter** — it drops the surface prefix and lands on the root (web) surface. Footer/anchor links must be `<Link>` with the prefix, or in-app hash routes.
- **Cross-surface links use in-app hash routes, never absolute dev ports.** The old per-app ports (web 5273, console 5173, employers 5373) no longer map to surfaces after the merge — `localhost:5173` is now the unified app root (= web surface). Link with `#/console/signin`, `#/`, etc. Sweep: `grep -rnE "localhost:(5173|5273|5373)" src`.
- **Per-surface CSS scoping** — each surface is wrapped in `.surface-web` / `.surface-employers` / `.surface-console`; scope per-surface CSS inside that selector to prevent cross-surface bleed.
- **Design tokens are per-surface** in `src/sites/<surface>/styles/`. The static `frontend/styleguide/` is a hand-maintained snapshot — when a token/font changes in a surface's CSS, update the styleguide swatch to match (it's documentation, not a build artifact).
- **Each old per-app `.gitignore` is gone** — `frontend/` has its own `.gitignore` (node_modules/dist); the root one does NOT cover it.
