# Design-System Harmonization (in favour of web) — Design

**Status:** approved (brainstorm) — 2026-06-24
**Surfaces:** `frontend/` unified Vite + React app — `web` (`/`), `employers` (`/employers`), `console` (`/console`).

## Goal

Collapse the **four divergent design languages** in `frontend/` into **one** design
system, taking the **web** surface's warm-editorial look as canonical, and add a
real **light/dark theme** that works across every surface and component.

After this work:

- All three surfaces share one token vocabulary (web's), one type stack
  (Fraunces / Hanken Grotesk / JetBrains Mono), and one accent (persimmon).
- A single `ThemeProvider` toggles light/dark for the whole app via
  `data-theme` on `<html>`, persisted to `localStorage`, defaulting to the OS
  preference, with no flash on load.
- Shared component primitives (`.btn`, `.card`, `.input`/`.field`, `.badge`,
  `.table`) render correctly in both themes from the shared tokens.

## Background — the current state (why this is needed)

Each surface defines its own palette/fonts/accent; only `--brand-blue #0048a8`
is shared. Verified in-repo on 2026-06-24:

| Surface | Identity today | tokens defined on | `var()` uses | hex literals |
|---|---|---|---|---|
| web | warm paper `#f4efe3`, persimmon `#d8472a`, Fraunces/Hanken/JetBrains | `.surface-web` | 430 | ~19 |
| employers | cool navy/amber, Archivo/IBM Plex | `.surface-employers` | 192 | 17 (+22 rgba) |
| console | **dark** `#080b09`, amber/teal, Bricolage/Newsreader/Spline | `.surface-console` | 200 | 38 |
| styleguide | oxblood `#7a1f2b`, Spectral/Martian Mono | own | — | — |

Two facts shape the plan:

1. **Surfaces are ~90% variable-driven.** Once a shared token set carries light
   *and* dark values, dark mode mostly "just works"; the real work is
   de-hardcoding the ~74 stray literals and renaming each surface's bespoke
   variable names onto web's vocabulary.
2. **Tokens live on the `.surface-*` wrapper class, not `:root`.** Migration
   moves the canonical token definitions to `:root` (global) + a
   `:root[data-theme="dark"]` override block; the `.surface-*` wrappers stay for
   surface-specific component scoping but stop redefining the core palette.

There is **no theme-switching anywhere today** — dark mode is net-new
infrastructure.

## Decisions (locked during brainstorm)

1. **Console → full light by default**, *and* dark mode for the whole frontend
   (not just console). Console's existing dark palette becomes the basis for the
   shared **dark** theme.
2. **Depth: tokens + components.** Unify the token layer and the shared
   component primitives. Bespoke page layouts keep their structure but inherit
   the unified tokens.
3. **Architecture: a shared `tokens.css` layer** in `src/shared/styles/`,
   imported once, consumed by all surfaces. One source of truth.
4. **Styleguide left untouched** — it stays intentionally divergent
   documentation; note this in `frontend/CLAUDE.md`.

Consequence to expect (not a regression): **employers and console visibly change
colour identity** to warm-paper + persimmon. That is the explicit "in favour of
web" intent.

## Token vocabulary (web's names are canon)

Keep the names web already uses (minimizes churn on the 430-usage canon). The
shared layer defines them on `:root` for light and overrides them under
`:root[data-theme="dark"]` for dark.

| Token | Light (web, canonical) | Dark (harmonized from console) |
|---|---|---|
| `--paper` | `#f4efe3` | `#0d110e` |
| `--paper-2` (recessed) | `#ece4d3` | `#080b09` |
| `--paper-3` (deeper/hover) | `#e4dac4` | `#1a201a` |
| `--panel` (raised card) | `#faf7ef` | `#121712` |
| `--ink` | `#221c16` | `#e9e4d6` |
| `--ink-soft` | `#6c6354` | `#b7b2a3` |
| `--ink-faint` | `#9b917e` | `#6f7868` |
| `--line` | `#d9cfb9` | `#232b23` |
| `--line-strong` | `#c4b89c` | `#34402f` |
| `--brand-blue` | `#0048a8` | `#0048a8` |
| `--brand-blue-deep` | `#003c8f` | `#003c8f` |
| `--brand-blue-tint` | `#e1ecf8` | `rgba(79,140,255,0.16)` |
| `--brand-blue-bright` | `#0048a8` | `#4f8cff` |
| `--accent` (persimmon) | `#d8472a` | `#ff6a48` |
| `--accent-deep` | `#b23a20` | `#d8472a` |
| `--accent-wash` | `#f3d9cf` | `rgba(255,106,72,0.14)` |
| `--forest` (verified/good) | `#1f4034` | `#6fdc8c` |
| `--forest-soft` | `#cfdcd2` | `rgba(111,220,140,0.16)` |
| `--gold` (warn) | `#b8842f` | `#ffb000` |
| `--danger` | `#b23a20` | `#ff5d49` |
| `--shadow` | `18px 22px 0 -8px rgba(34,28,22,0.08)` | `0 18px 40px -18px rgba(0,0,0,0.6)` |
| `--serif` | `"Fraunces", Georgia, serif` | (same) |
| `--sans` | `"Hanken Grotesk", system-ui, sans-serif` | (same) |
| `--mono` | `"JetBrains Mono", monospace` | (same) |
| `--maxw` | `1180px` | (same) |

`--danger` and `--panel` are net-new names (web didn't have them); employers
(`--good`, rgba lines) and console (`--bg0..3`, `--acc`, `--acc-teal`,
`--muted`, `--hairline*`) map their bespoke names onto this table during their
migration tasks. Console's four `--bg0..3` collapse onto
`--paper-2`/`--paper`/`--panel`/`--paper-3` respectively (dark values restore
the original console look).

Dark values are a starting point; final values get tuned for WCAG-AA contrast
during the per-surface tasks and the visual-QA task.

## Architecture

### Files

- **Create `frontend/src/shared/styles/tokens.css`** — `:root` light block +
  `:root[data-theme="dark"]` dark block (the table above). The single source of
  truth for colour/type/spacing tokens.
- **Create `frontend/src/shared/styles/base.css`** — `html`/`body` reset,
  global background/ink/font application (moved off the `.surface-*` blocks so it
  applies before a surface mounts), `box-sizing`, `color-scheme: light dark`,
  smooth-scroll. Sets `background: var(--paper); color: var(--ink)`.
- **Create `frontend/src/shared/styles/components.css`** — shared primitives
  `.btn` (+ `.btn-primary`/`.btn-ghost`), `.card`, `.input`/`.field`, `.badge`,
  `.table`, link styles — all on semantic tokens, theme-agnostic.
- **Create `frontend/src/shared/theme/ThemeProvider.tsx`** — context provider.
- **Create `frontend/src/shared/theme/useTheme.ts`** — `useTheme()` hook
  re-export (kept separate so non-provider modules import the hook without
  dragging the provider; mirrors the repo's context/provider split convention).
- **Create `frontend/src/shared/theme/ThemeToggle.tsx`** — sun/moon control.
- **Modify `frontend/src/main.tsx`** — import the three shared CSS files (before
  `App`, so they sit first in the cascade) and wrap `<App/>` in `<ThemeProvider>`.
- **Modify `frontend/index.html`** — (a) collapse three Google-Fonts `<link>`
  bundles to the one web bundle; (b) add an inline pre-paint `<script>` in
  `<head>` that reads `localStorage["jobify-theme"]` (or `prefers-color-scheme`)
  and sets `document.documentElement.dataset.theme` before first paint.
- **Modify** each surface CSS (`web/styles/site.css`, `employers/styles/site.css`,
  `console/styles/console.css`) — drop local token definitions, consume shared
  tokens, de-hardcode literals.
- **Modify** each surface chrome (`web/components/Chrome.tsx`,
  `employers/components/Chrome.tsx`, `console/components/Shell.tsx`) — mount
  `<ThemeToggle/>` in the header.
- **Modify `frontend/CLAUDE.md`** — document the shared token layer, the
  `:root` (not `.surface-*`) token home, the global single `ThemeProvider`
  exception to the per-surface rule, and that the styleguide is intentionally
  divergent.

### Theme mechanism

- `ThemeProvider` state: `theme ∈ {light, dark, system}` (persisted to
  `localStorage["jobify-theme"]`); `resolvedTheme ∈ {light, dark}` after
  applying `prefers-color-scheme` for `system`. On change it sets
  `document.documentElement.dataset.theme = resolvedTheme` and listens to the
  `prefers-color-scheme` media query while in `system` mode.
- **Single provider at the App root** — theme targets the one `<html>` element,
  so it is global. This is the deliberate exception to the per-surface
  `SessionProvider` rule (sessions are independent; theme is not).
- **No flash:** the inline `index.html` script sets `data-theme` before React
  hydrates; `ThemeProvider` reads the same key and stays consistent.

## Phasing (each phase independently shippable + reviewable)

- **P1 — Foundation.** `tokens.css` + `base.css` + `components.css` skeleton;
  `ThemeProvider`/`useTheme`/`ThemeToggle`; `main.tsx` wiring; `index.html`
  fonts trimmed + pre-paint script. No surface visibly changes yet (surfaces
  still define their own tokens locally and win the cascade). Build green.
- **P2 — web.** Remove web's local token block (move any non-token rules to
  base/keep in surface), let it consume shared tokens; mount toggle. Verify
  **light is pixel-stable** vs. before, and **dark** renders. This validates the
  token table on the canon before touching the others.
- **P3 — employers.** Remap `--amber/--slate/--good/...` and the 17 hex + 22
  rgba literals onto shared tokens; warm-paper identity in light; dark works;
  mount toggle.
- **P4 — console.** The big one: flip default from dark to **light** (consume
  shared light tokens); map its `--bg0..3/--acc/--acc-teal/--muted/--hairline*`
  and 38 literals so the **dark** theme restores the original console look;
  mount toggle.
- **P5 — component primitives.** Converge surface buttons/cards/inputs/badges
  /tables onto `components.css` where it reduces divergence without rewriting
  bespoke page sections.

## Testing

- **`npm run build`** (`tsc -b && vite build`, the CI gate) green after every
  phase.
- **Playwright** visual pass of each surface in **light and dark** at the end of
  P2/P3/P4 and P5: load surface, toggle theme, screenshot, assert key
  `getComputedStyle` colours resolve to the expected token (not a stale
  hardcoded value), and assert **no flash** (pre-paint script sets `data-theme`
  before paint). Reuse the user's running dev server / a pinned port; scroll the
  inner `main.overflow-y-auto` pane, not `window`.
- **Contrast spot-check** of ink-on-paper and accent-on-paper in dark for
  WCAG-AA.

## Out of scope

- The static `frontend/styleguide/` (left divergent, per decision 4).
- The Flutter `app/` client (separate design system; not part of `frontend/`).
- Rewriting bespoke page-section layouts beyond token/primitive adoption.
- Backend, routing, or content changes.

## Risks

- **Console light conversion (P4)** is the largest visual change and the most
  hardcoded surface (38 literals). Isolated to its own phase so it can be
  reviewed/reverted independently.
- **Cascade order** — shared CSS must load before surface CSS. Guaranteed by
  importing the shared files in `main.tsx` ahead of `App`. Verify in the built
  bundle.
- **Flash of wrong theme** — mitigated by the inline pre-paint script; covered
  by a Playwright assertion.
