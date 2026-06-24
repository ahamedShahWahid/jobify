# CLAUDE.md — frontend (unified Vite + React + TS web app)

Load-bearing invariants for the web app: three route-prefixed surfaces under one HashRouter — `/` (applicant/public, `src/sites/web`), `/employers` (recruiter marketing, `src/sites/employers`), `/console` (admin + recruiter ops, `src/sites/console`); shared transport/session/auth/env in `src/shared`. Auto-loaded when working under `frontend/`. Dev/build/env reference is in `frontend/README.md`.

> These are the shared-HashRouter pitfalls — things that silently send users to the wrong surface or leak styles across surfaces.

- **One app, three sibling route subtrees** — `index.html` → `src/main.tsx` → `src/App.tsx` mounts each surface's route fragment under one `<HashRouter>`. All three ship in one static `dist/`; they are NOT separate builds. Each surface mounts its own `SessionProvider` (sessions are independent per surface).
- **Every internal nav literal must carry the surface prefix.** Grep for ALL forms when migrating/adding routes — `grep -rnE "(to=\{?[\"'\`]|navigate\([\"'\`])/(seg)" src` — backtick-template ``to={`/console/${id}`}`` and single-quote `navigate('/console')` slip past quote-only greps.
- **Raw `<a href="/#anchor">` breaks under the shared HashRouter** — it drops the surface prefix and lands on the root (web) surface. Footer/anchor links must be `<Link>` with the prefix, or in-app hash routes.
- **Cross-surface links use in-app hash routes, never absolute dev ports.** The old per-app ports (web 5273, console 5173, employers 5373) no longer map to surfaces after the merge — `localhost:5173` is now the unified app root (= web surface). Link with `#/console/signin`, `#/`, etc. Sweep: `grep -rnE "localhost:(5173|5273|5373)" src`.
- **Per-surface CSS scoping** — each surface is wrapped in `.surface-web` / `.surface-employers` / `.surface-console`; scope per-surface CSS inside that selector to prevent cross-surface bleed.
- **Design tokens are global, NOT per-surface** — they live on `:root` (light) and `:root[data-theme="dark"]` in `src/shared/styles/tokens.css`. Web surface token names are canonical. Surfaces must NOT redefine tokens on `.surface-*`.
- **Each old per-app `.gitignore` is gone** — `frontend/` has its own `.gitignore` (node_modules/dist); the root one does NOT cover it.

## Design system

- **Token home:** `src/shared/styles/tokens.css` — `:root` (light defaults) + `:root[data-theme="dark"]`. All colour/spacing/font values go here; per-surface CSS uses `var(--token)` exclusively.
- **Shared primitives:** `src/shared/styles/components.css` — `.ds-btn` / `.ds-btn-primary` / `.ds-btn-danger` / `.ds-btn-ghost` / `.ds-btn-sm` / `.ds-card` / `.ds-input` / `.ds-badge` (+`.ds-badge-ok/warn/danger/accent`) / `.ds-theme-toggle`. 100 % token-driven, render correctly in both themes. Surfaces keep their own scoped variants; these are the canonical baseline.
- **ThemeProvider** (`src/shared/theme/`) is the **deliberate exception** to the per-surface SessionProvider rule — one global provider wraps all three surfaces. It reads/writes `localStorage` key `jobify-theme`, sets `data-theme` on `<html>`, and exposes `useTheme()` → `{ theme, resolvedTheme, setTheme, toggle }`.
- **No flash on reload:** `index.html` carries an inline pre-paint `<script>` that reads `localStorage["jobify-theme"]` and sets `document.documentElement.dataset.theme` synchronously before any CSS parses — this must never be deferred or moved to a bundle.
- **console `.jc-card`** is intentionally ALWAYS-LIGHT (warm hardcoded palette for candidate preview cards). Do not tokenize it — it is a deliberate design exception, not a migration gap.
- **`frontend/styleguide/`** is a static hand-maintained swatch page — intentionally NOT wired to `tokens.css`. It is documentation, not a build artifact; update it manually when the palette changes significantly.
