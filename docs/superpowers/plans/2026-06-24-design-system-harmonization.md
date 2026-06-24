# Design-System Harmonization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the four divergent per-surface design languages in `frontend/` into one shared token system (web's warm-editorial look as canon) with a real app-wide light/dark theme.

**Architecture:** A shared `src/shared/styles/{tokens,base,components}.css` layer defines web's token vocabulary on `:root` (light) plus a `:root[data-theme="dark"]` override block. A single `ThemeProvider` at the App root sets `data-theme` on `<html>`, persisted to `localStorage`, defaulting to OS preference, with an inline pre-paint script preventing flash. Each surface stops defining its own tokens and consumes the shared ones; employers/console remap their bespoke variable names onto web's vocabulary.

**Tech Stack:** Vite + React + TypeScript, plain CSS custom properties (no CSS-in-JS, no Tailwind), HashRouter, three route-prefixed surfaces under one app.

## Global Constraints

- **Token names are web's existing names** — `--paper`, `--paper-2`, `--paper-3`, `--panel`, `--ink`, `--ink-2`, `--ink-soft`, `--ink-faint`, `--line`, `--line-strong`, `--line-faint`, `--brand-blue`(+`-deep`/`-tint`/`-bright`), `--accent`(+`-deep`/`-wash`/`-ink`), `--forest`(+`-soft`), `--gold`, `--danger`, `--ok`, `--shadow`, `--serif`, `--sans`, `--mono`, `--maxw`, `--ease`. Do not invent `--bg`/`--surface` names.
- **Tokens live on `:root`** (global) + `:root[data-theme="dark"]`, never on `.surface-*`.
- **Type stack is web's three families only**: `--serif: "Fraunces"`, `--sans: "Hanken Grotesk"`, `--mono: "JetBrains Mono"`. Drop Archivo/IBM Plex/Bricolage/Newsreader/Spline/Martian.
- **Accent is persimmon** (`--accent`). Console's area-keyed amber/teal accents collapse to the single shared accent.
- **One global `ThemeProvider`** at the App root — the deliberate exception to the per-surface `SessionProvider` rule (theme targets the single `<html>`).
- **localStorage key is exactly `jobify-theme`**, values `light` | `dark` | `system`; the inline `index.html` script and `ThemeProvider` must read the same key.
- **Shared CSS imports come before `App`** in `main.tsx` so they sit first in the cascade; surface CSS (imported in each `*Routes.tsx`) loads after and may still override structurally but must use shared tokens for colour/type.
- **CI gate after every task:** `cd frontend && npm run build` (`tsc -b && vite build`) must be green.
- **Styleguide (`frontend/styleguide/`) is out of scope** — left intentionally divergent.
- **No `console.log` / debug code left in committed `.tsx`.**
- Branch is `design-system-harmonize-web` (already created off `origin/main`). Commit per task.

---

### Task 1: Shared foundation — tokens, base, theme provider, fonts, pre-paint

Creates the shared token layer, the theme machinery, and wires fonts. **No surface visibly changes yet** — surfaces still define their own tokens on `.surface-*`, which win the cascade until their own migration task. This task only adds the foundation and proves it builds and toggles.

**Files:**
- Create: `frontend/src/shared/styles/tokens.css`
- Create: `frontend/src/shared/styles/base.css`
- Create: `frontend/src/shared/styles/components.css`
- Create: `frontend/src/shared/theme/ThemeContext.ts`
- Create: `frontend/src/shared/theme/ThemeProvider.tsx`
- Create: `frontend/src/shared/theme/useTheme.ts`
- Create: `frontend/src/shared/theme/ThemeToggle.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/index.html`

**Interfaces:**
- Produces:
  - `tokens.css` defining all Global-Constraints token names on `:root` (light) and `:root[data-theme="dark"]` (dark).
  - `ThemeProvider` (default export named `ThemeProvider`): `({ children }: { children: ReactNode }) => JSX.Element`.
  - `useTheme()` → `{ theme: Theme; resolvedTheme: "light" | "dark"; setTheme: (t: Theme) => void; toggle: () => void }` where `type Theme = "light" | "dark" | "system"`.
  - `ThemeToggle` (named export): `() => JSX.Element` — a button that calls `toggle()`.
  - localStorage key `jobify-theme`; `<html data-theme="light|dark">` contract.

- [ ] **Step 1: Create `tokens.css`** with the full light + dark token sets.

```css
/* frontend/src/shared/styles/tokens.css
   The single source of truth for Jobify's design tokens.
   Canon = the web surface's warm-editorial palette. Light on :root,
   dark under :root[data-theme="dark"]. Surfaces consume these names;
   they must NOT redefine them on .surface-* anymore. */

:root {
  color-scheme: light;

  /* surfaces / backgrounds */
  --paper: #f4efe3;     /* page background */
  --paper-2: #ece4d3;   /* recessed surface */
  --paper-3: #e4dac4;   /* deeper / hover */
  --panel: #faf7ef;     /* raised card */

  /* ink / text */
  --ink: #221c16;
  --ink-2: #3b362c;     /* secondary ink */
  --ink-soft: #6c6354;
  --ink-faint: #9b917e;

  /* lines */
  --line: #d9cfb9;
  --line-strong: #c4b89c;
  --line-faint: rgba(34, 28, 22, 0.06);

  /* brand blue (the logo) */
  --brand-blue: #0048a8;
  --brand-blue-deep: #003c8f;
  --brand-blue-tint: #e1ecf8;
  --brand-blue-bright: #0048a8;  /* on-dark-legible step; same as blue in light */

  /* accent — persimmon, the signature */
  --accent: #d8472a;
  --accent-deep: #b23a20;
  --accent-wash: #f3d9cf;
  --accent-ink: #ffffff;         /* text on an --accent fill */

  /* status */
  --forest: #1f4034;             /* verified / trust */
  --forest-soft: #cfdcd2;
  --gold: #b8842f;               /* warn */
  --danger: #b23a20;
  --ok: #1f4034;

  --shadow: 18px 22px 0 -8px rgba(34, 28, 22, 0.08);

  /* type */
  --serif: "Fraunces", Georgia, serif;
  --sans: "Hanken Grotesk", system-ui, sans-serif;
  --mono: "JetBrains Mono", monospace;

  --maxw: 1180px;
  --ease: cubic-bezier(0.2, 0.7, 0.2, 1);
}

:root[data-theme="dark"] {
  color-scheme: dark;

  --paper: #0d110e;
  --paper-2: #080b09;
  --paper-3: #1a201a;
  --panel: #121712;

  --ink: #e9e4d6;
  --ink-2: #cdc7b8;
  --ink-soft: #b7b2a3;
  --ink-faint: #6f7868;

  --line: #232b23;
  --line-strong: #34402f;
  --line-faint: rgba(233, 228, 214, 0.06);

  --brand-blue: #4f8cff;
  --brand-blue-deep: #2f6fe0;
  --brand-blue-tint: rgba(79, 140, 255, 0.16);
  --brand-blue-bright: #4f8cff;

  --accent: #ff6a48;
  --accent-deep: #d8472a;
  --accent-wash: rgba(255, 106, 72, 0.14);
  --accent-ink: #1a0f0a;

  --forest: #6fdc8c;
  --forest-soft: rgba(111, 220, 140, 0.16);
  --gold: #ffb000;
  --danger: #ff5d49;
  --ok: #6fdc8c;

  --shadow: 0 18px 40px -18px rgba(0, 0, 0, 0.6);
}
```

- [ ] **Step 2: Create `base.css`** — global reset + body defaults using the tokens.

```css
/* frontend/src/shared/styles/base.css
   Global reset + base typography. Body colour/background come from tokens so
   they flip with the theme. Surfaces may override font-size/line-height on
   their .surface-* wrapper (e.g. console runs denser). */

*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.6;
  font-weight: 400;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  min-height: 100dvh;
  transition: background-color 0.2s var(--ease), color 0.2s var(--ease);
}
```

- [ ] **Step 3: Create `components.css`** — shared primitives skeleton (filled out in Task 5; created now so the import in `main.tsx` resolves and surfaces can begin adopting).

```css
/* frontend/src/shared/styles/components.css
   Shared component primitives on semantic tokens — render correctly in both
   themes. Surfaces converge onto these in Task 5. */

.ds-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5em;
  font-family: var(--sans);
  font-weight: 600;
  border: 1px solid var(--line-strong);
  background: var(--panel);
  color: var(--ink);
  border-radius: 2px;
  padding: 0.6em 1.1em;
  cursor: pointer;
  transition: background-color 0.15s var(--ease), border-color 0.15s var(--ease);
}
.ds-btn:hover {
  background: var(--paper-3);
}
.ds-btn-primary {
  background: var(--accent);
  border-color: var(--accent-deep);
  color: var(--accent-ink);
}
.ds-btn-primary:hover {
  background: var(--accent-deep);
}

.ds-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 4px;
  box-shadow: var(--shadow);
}

.ds-input {
  font-family: var(--sans);
  font-size: 1rem;
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  padding: 0.55em 0.75em;
}
.ds-input::placeholder {
  color: var(--ink-faint);
}
.ds-input:focus-visible {
  outline: 2px solid var(--brand-blue);
  outline-offset: 1px;
}

.ds-badge {
  display: inline-flex;
  align-items: center;
  font-family: var(--mono);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 2px;
  padding: 0.15em 0.5em;
}
```

- [ ] **Step 4: Create `ThemeContext.ts`** — context + types, split out so consumers don't import the provider's effects (mirrors the repo's context/provider split convention).

```ts
// frontend/src/shared/theme/ThemeContext.ts
import { createContext } from "react";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export interface ThemeContextValue {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export const THEME_STORAGE_KEY = "jobify-theme";
```

- [ ] **Step 5: Create `ThemeProvider.tsx`**.

```tsx
// frontend/src/shared/theme/ThemeProvider.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  ThemeContext,
  THEME_STORAGE_KEY,
  type ResolvedTheme,
  type Theme,
} from "./ThemeContext";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function readStored(): Theme {
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* private mode / disabled storage — fall through */
  }
  return "system";
}

function systemResolved(): ResolvedTheme {
  return window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStored);
  const [systemPref, setSystemPref] = useState<ResolvedTheme>(systemResolved);

  // Track the OS preference while in "system" mode.
  useEffect(() => {
    const mql = window.matchMedia(DARK_QUERY);
    const onChange = () => setSystemPref(mql.matches ? "dark" : "light");
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  const resolvedTheme: ResolvedTheme = theme === "system" ? systemPref : theme;

  // Apply to <html> and persist.
  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
  }, [resolvedTheme]);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, t);
    } catch {
      /* ignore */
    }
  }, []);

  const toggle = useCallback(() => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  }, [resolvedTheme, setTheme]);

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme, toggle }),
    [theme, resolvedTheme, setTheme, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
```

- [ ] **Step 6: Create `useTheme.ts`**.

```ts
// frontend/src/shared/theme/useTheme.ts
import { useContext } from "react";
import { ThemeContext, type ThemeContextValue } from "./ThemeContext";

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within <ThemeProvider>");
  return ctx;
}
```

- [ ] **Step 7: Create `ThemeToggle.tsx`** — a dependency-free inline-SVG sun/moon button.

```tsx
// frontend/src/shared/theme/ThemeToggle.tsx
import { useTheme } from "./useTheme";

export function ThemeToggle() {
  const { resolvedTheme, toggle } = useTheme();
  const isDark = resolvedTheme === "dark";
  return (
    <button
      type="button"
      className="ds-theme-toggle"
      onClick={toggle}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Light" : "Dark"}
    >
      {isDark ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="5" />
          <path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  );
}
```

- [ ] **Step 8: Add a minimal toggle style to `components.css`** (append).

```css
.ds-theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.1em;
  height: 2.1em;
  color: var(--ink-soft);
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 2px;
  cursor: pointer;
  transition: color 0.15s var(--ease), border-color 0.15s var(--ease);
}
.ds-theme-toggle:hover {
  color: var(--accent);
  border-color: var(--line-strong);
}
```

- [ ] **Step 9: Wire `main.tsx`** — import shared CSS first, wrap App in ThemeProvider.

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./shared/styles/tokens.css";
import "./shared/styles/base.css";
import "./shared/styles/components.css";
import { ThemeProvider } from "./shared/theme/ThemeProvider";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
);
```

- [ ] **Step 10: Edit `index.html`** — (a) replace the three Google-Fonts `<link rel="stylesheet">` blocks (web/console/employers) with the single web bundle; (b) add the pre-paint script in `<head>` BEFORE the module script.

Replace the three font `<link>` tags with exactly one:

```html
<link
  href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,900;1,9..144,400;1,9..144,500&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap"
  rel="stylesheet"
/>
```

Add this inline script inside `<head>`, immediately after the font `<link>` (keep the `preconnect` links):

```html
<script>
  (function () {
    try {
      var s = localStorage.getItem("jobify-theme");
      var dark =
        s === "dark" ||
        ((!s || s === "system") &&
          window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
    } catch (e) {
      document.documentElement.dataset.theme = "light";
    }
  })();
</script>
```

- [ ] **Step 11: Build.**

Run: `cd frontend && npm run build`
Expected: `tsc -b` passes with no errors; `vite build` prints `✓ built in …`. No TypeScript errors about unused imports or missing modules.

- [ ] **Step 12: Smoke-test the toggle wiring** (foundation only — surfaces unchanged).

Run: `cd frontend && npm run dev` (or reuse the running server). In a browser/Playwright, evaluate:
```js
// before any toggle, with no stored pref on a light-OS machine:
document.documentElement.dataset.theme // => "light"
localStorage.setItem("jobify-theme","dark"); location.reload();
// after reload:
document.documentElement.dataset.theme // => "dark" (no flash: set pre-paint)
```
Expected: attribute flips; reload with stored `dark` shows `data-theme="dark"` from first paint. Clean up: `localStorage.removeItem("jobify-theme")`.

- [ ] **Step 13: Commit.**

```bash
git add frontend/src/shared/styles frontend/src/shared/theme frontend/src/main.tsx frontend/index.html
git commit -m "feat(frontend): shared design tokens + light/dark theme foundation"
```

---

### Task 2: Migrate the web surface onto shared tokens

Web is the canon — its token *names* are already the shared vocabulary, so this is mostly **deleting** web's local token definitions (now provided by `:root`) and mounting the toggle. Verify light is pixel-stable and dark renders.

**Files:**
- Modify: `frontend/src/sites/web/styles/site.css` (token block at top, ~lines 8–50)
- Modify: `frontend/src/sites/web/components/Chrome.tsx` (mount toggle in `Masthead`)

**Interfaces:**
- Consumes: all tokens from `:root` (Task 1); `ThemeToggle` from `../../../shared/theme/ThemeToggle`.

- [ ] **Step 1: Remove web's local token definitions.** In `frontend/src/sites/web/styles/site.css`, delete the custom-property lines inside `.surface-web { … }` (the `--paper` … `--maxw` declarations, currently lines 9–37). **Keep** the non-token rules in that block: `margin`, `background: var(--paper)`, `color: var(--ink)`, `font-family: var(--sans)`, `font-size`, `line-height`, `font-weight`, `-webkit-font-smoothing`, `text-rendering`, `min-height`, `position`. Result:

```css
.surface-web {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.6;
  font-weight: 400;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  min-height: 100dvh;
  position: relative;
}
```

- [ ] **Step 2: Sweep remaining hardcoded literals** in `web/styles/site.css`.

Run: `grep -nE '#[0-9a-fA-F]{3,8}|rgba?\(' frontend/src/sites/web/styles/site.css`
For each match that is a brand/ink/paper/accent colour, replace with the matching `var(--…)`. Decorative one-offs (paper-grain gradients, the `rgba(34,28,22,0.08)` already inside `--shadow`) may stay if they have no token equivalent — but anything equal to a token value MUST become the token. Expected after sweep: only decorative gradient/grain literals remain (≤ a handful).

- [ ] **Step 3: Mount the toggle** in `Masthead` (`web/components/Chrome.tsx`). Add the import and place `<ThemeToggle />` at the end of the `<nav className="nav">`, after the "Open my feed" CTA:

```tsx
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
// …inside <nav className="nav">, after the nav-cta <Link>:
          <ThemeToggle />
```

- [ ] **Step 4: Build.**

Run: `cd frontend && npm run build`
Expected: green.

- [ ] **Step 5: Visual verify (light + dark).** With the dev server up, load `#/` (web). In light:
```js
getComputedStyle(document.querySelector(".surface-web")).backgroundColor
// => rgb(244, 239, 227)  (== #f4efe3, unchanged from before)
```
Toggle to dark (click the toggle or `useTheme().toggle()`), then:
```js
document.documentElement.dataset.theme // "dark"
getComputedStyle(document.querySelector(".surface-web")).backgroundColor
// => rgb(13, 17, 14)  (== #0d110e)
getComputedStyle(document.querySelector(".surface-web")).color
// => rgb(233, 228, 214)  (== #e9e4d6)
```
Expected: light background byte-identical to pre-change; dark flips background + ink. Spot-check the masthead, a card, and a primary button are legible in dark.

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/sites/web/styles/site.css frontend/src/sites/web/components/Chrome.tsx
git commit -m "feat(web): consume shared tokens + theme toggle"
```

---

### Task 3: Migrate the employers surface onto shared tokens

Employers changes colour identity (cool navy/amber → warm-paper/persimmon) and gains dark mode. Remap its bespoke names, de-hardcode literals, swap fonts, mount toggle.

**Files:**
- Modify: `frontend/src/sites/employers/styles/site.css`
- Modify: `frontend/src/sites/employers/components/Chrome.tsx` (mount toggle in `Masthead`'s `.mast-cta`)

**Interfaces:**
- Consumes: `:root` tokens; `ThemeToggle` from `../../../shared/theme/ThemeToggle`.

- [ ] **Step 1: Remove employers' local token block.** In `employers/styles/site.css`, delete the custom-property declarations inside `.surface-employers { … }` (the `--paper` … `--ease` lines, ~lines 11–46). Keep the base rules (`margin`, `background: var(--paper)`, `color: var(--ink)`, `font-family: var(--sans)`, `font-size`, `line-height`, etc.). The shared `:root` now provides `--paper`, `--ink`, `--ink-2`, `--ink-soft`, `--ink-faint`, `--line`, `--line-strong`, `--line-faint`, `--panel`, `--ease`.

- [ ] **Step 2: Apply the name remapping** with ordered `sed` (compound substrings BEFORE bare — `--amber-deep`/`--amber-wash` before `--amber`; `--slate-soft` before `--slate`; `--good-soft` before `--good`). From repo root:

```bash
f=frontend/src/sites/employers/styles/site.css
sed -i '' \
  -e 's/var(--display)/var(--serif)/g' \
  -e 's/var(--amber-deep)/var(--accent-deep)/g' \
  -e 's/var(--amber-wash)/var(--accent-wash)/g' \
  -e 's/var(--amber)/var(--accent)/g' \
  -e 's/var(--slate-soft)/var(--brand-blue-tint)/g' \
  -e 's/var(--slate)/var(--brand-blue)/g' \
  -e 's/var(--good-soft)/var(--forest-soft)/g' \
  -e 's/var(--good)/var(--forest)/g' \
  "$f"
```
Mapping rationale: employers' amber signal-accent → persimmon `--accent`; slate data-blue → `--brand-blue`; good/pass green → `--forest`. `--ink-2`/`--line-faint`/`--ease` keep their names (now shared). Archivo `--display` → `--serif` (Fraunces).

- [ ] **Step 3: Verify no orphaned bespoke vars remain.**

Run: `grep -nE 'var\(--(amber|slate|good|display)\b' frontend/src/sites/employers/styles/site.css`
Expected: no output. If any remain (e.g. `--good` inside a longer name), fix by hand.

- [ ] **Step 4: De-hardcode remaining literals.**

Run: `grep -nE '#[0-9a-fA-F]{3,8}|rgba?\(' frontend/src/sites/employers/styles/site.css`
Replace navy/amber/slate-derived literals with their token. Common ones: `rgba(14, 27, 42, …)` (navy, was line/ink) → `var(--line)` / `var(--line-strong)` / `var(--line-faint)` per opacity, or `var(--ink)` where used as text; `#0e1b2a`/`#213347` → `var(--ink)`/`var(--ink-2)`; any `#f3a712`/`#e8930c` → `var(--accent)`/`var(--accent-deep)`. Leave purely decorative gradients with no token equivalent. Expected after: only decorative literals remain.

- [ ] **Step 5: Mount the toggle** in `employers/components/Chrome.tsx` `Masthead`. Add import and place `<ThemeToggle />` as the first child of `<div className="mast-cta">` (before the "Open the console" button):

```tsx
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
// …inside <div className="mast-cta">, first child:
          <ThemeToggle />
```

- [ ] **Step 6: Build.**

Run: `cd frontend && npm run build`
Expected: green.

- [ ] **Step 7: Visual verify (light + dark).** Load `#/employers`. In light:
```js
getComputedStyle(document.querySelector(".surface-employers")).backgroundColor
// => rgb(244, 239, 227)  (warm paper — NOT the old cool #f3f4f1)
```
Toggle dark:
```js
getComputedStyle(document.querySelector(".surface-employers")).backgroundColor // rgb(13, 17, 14)
```
Expected: warm-paper identity in light, legible dark. Check the hero, pricing cards, and the amber→persimmon accent on CTAs/badges. Confirm no navy text-on-dark contrast failures.

- [ ] **Step 8: Commit.**

```bash
git add frontend/src/sites/employers/styles/site.css frontend/src/sites/employers/components/Chrome.tsx
git commit -m "feat(employers): adopt shared tokens (warm/persimmon) + dark mode"
```

---

### Task 4: Migrate the console surface onto shared tokens (light default + dark)

The largest change. Console flips from dark-only to **light default**, with its old dark look restored via the shared dark theme. Critical: console uses `--paper` as **foreground text** (opposite of web) and layered `--bg0..3` backgrounds — these must remap correctly. Fonts collapse to the shared set (console stays mono-bodied on JetBrains — still within the canon). Area-keyed accents collapse to the single persimmon accent.

**Files:**
- Modify: `frontend/src/sites/console/styles/console.css`
- Modify: `frontend/src/sites/console/components/Shell.tsx` (mount toggle in the rail)

**Interfaces:**
- Consumes: `:root` tokens; `ThemeToggle` from `../../../shared/theme/ThemeToggle`.

- [ ] **Step 1: Remove console's local token block.** In `console/styles/console.css`, delete the custom-property declarations inside `.surface-console { … }` (the `--bg0` … `--font-flavor` lines, ~lines 11–39). Keep the base rules below them (`margin`, `min-height`, and — after Step 2 — the `background`/`color`/`font-family` lines, which get remapped).

- [ ] **Step 2: Do NOT hand-edit the body colour/background/font lines.** Leave `.surface-console`'s `background: var(--bg0);`, `color: var(--paper);`, and `font-family: var(--font-mono);` exactly as-is — the two-pass `sed` in Step 4 remaps them correctly (`--bg0`→`--paper-2` for the page background, `--paper`→`--ink` for the foreground, `--font-mono`→`--mono`). Hand-editing here would create a premature `var(--paper)` that Step 4 Pass 1 would wrongly convert to `var(--ink)`. The only thing to confirm: `font-size: 13px; line-height: 1.55;` stay (console runs denser than the shared 16px `body` default — allowed; the surface overrides).

- [ ] **Step 3: Remove the area-keyed accent overrides.** Delete the two blocks:

```css
.surface-console [data-area="admin"] { --acc: #ffb000; --acc-ink: #140d00; }
.surface-console [data-area="recruiter"] { --acc: #4fe3c1; --acc-ink: #00150f; }
```
(The `data-area` attribute stays on `.shell` for any non-colour use; the accent is now the single shared persimmon.)

- [ ] **Step 4: Apply the name remapping** as **two `sed` passes**. The two-pass split is load-bearing: console uses `--paper` as foreground text (must become `--ink`), but `--bg1` must become `--paper` (the page colour). If both ran in one pass, the new `--paper` created from `--bg1` would get swept into `--ink` too. So **Pass 1 converts the original `--paper` (foreground) → `--ink` while no `--paper` exists from backgrounds yet; Pass 2 then creates `--paper` from `--bg1`.** Within each pass, compounds come before bare names (`--paper-dim` before `--paper`, `--hairline-bright` before `--hairline`, `--acc-*` before `--acc`). From repo root:

```bash
f=frontend/src/sites/console/styles/console.css
# Pass 1: fonts, foreground text, accents, dim/muted/hairline — NO backgrounds yet.
sed -i '' \
  -e 's/var(--font-display)/var(--serif)/g' \
  -e 's/var(--font-mono)/var(--mono)/g' \
  -e 's/var(--font-flavor)/var(--serif)/g' \
  -e 's/var(--paper-dim)/var(--ink-soft)/g' \
  -e 's/var(--paper)/var(--ink)/g' \
  -e 's/var(--muted)/var(--ink-faint)/g' \
  -e 's/var(--hairline-bright)/var(--line-strong)/g' \
  -e 's/var(--hairline)/var(--line)/g' \
  -e 's/var(--acc-faint)/var(--accent-wash)/g' \
  -e 's/var(--acc-dim)/color-mix(in srgb, var(--accent) 38%, transparent)/g' \
  -e 's/var(--acc-ink)/var(--accent-ink)/g' \
  -e 's/var(--acc)/var(--accent)/g' \
  "$f"
# Pass 2: backgrounds (creates var(--paper)/var(--panel)/... that Pass 1 must NOT have seen).
sed -i '' \
  -e 's/var(--bg0)/var(--paper-2)/g' \
  -e 's/var(--bg1)/var(--paper)/g' \
  -e 's/var(--bg2)/var(--panel)/g' \
  -e 's/var(--bg3)/var(--paper-3)/g' \
  "$f"
```
Result for the body rules left untouched in Step 2: `background: var(--bg0)` → `var(--paper-2)` (page background — light `#ece4d3`, dark `#080b09`); `color: var(--paper)` → `var(--ink)`; `font-family: var(--font-mono)` → `var(--mono)`. Verify in Step 8.

- [ ] **Step 5: Map `--ok`/`--danger` and de-hardcode remaining literals.** `--ok` and `--danger` keep their names (now shared) — just ensure the local defs were removed in Step 1.

Run: `grep -nE 'var\(--(bg[0-9]|acc|paper-dim|muted|hairline|font-)\b' frontend/src/sites/console/styles/console.css`
Expected: no output (all bespoke names mapped).

Run: `grep -nE '#[0-9a-fA-F]{3,8}|rgba?\(' frontend/src/sites/console/styles/console.css`
Replace dark-palette literals with tokens: `#080b09/#0d110e/#121712/#1a201a` → `var(--paper-2)/var(--paper)/var(--panel)/var(--paper-3)`; `#e9e4d6/#b7b2a3/#6f7868` → `var(--ink)/var(--ink-soft)/var(--ink-faint)`; `#232b23/#34402f` → `var(--line)/var(--line-strong)`; `#ffb000/#4fe3c1/#ff5d49/#6fdc8c` → `var(--accent)`/`var(--accent)`/`var(--danger)`/`var(--ok)`; `#4f8cff` → `var(--brand-blue-bright)`. Leave decorative grid/vignette/grain gradients that have no token (the console "atmosphere" layer) — but note in Step 7 these were tuned for dark; if they read badly in light, soften their opacity (they use rgba already).

- [ ] **Step 6: Mount the toggle** in `Shell.tsx`. Add import and place `<ThemeToggle />` in the rail brand area, after the `rail-brand` block's "internal operations" `<div className="k">`:

```tsx
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
// …inside <div className="rail-brand">, after the "internal operations" div:
          <div style={{ marginTop: 8 }}>
            <ThemeToggle />
          </div>
```

- [ ] **Step 7: Build.**

Run: `cd frontend && npm run build`
Expected: green (watch for `color-mix` — it is valid CSS, Vite passes it through; no TS impact).

- [ ] **Step 8: Visual verify (light default + dark restore).** Load `#/console` (sign in if required; or load a console route). Default (light):
```js
document.documentElement.dataset.theme // "light" (unless OS=dark)
getComputedStyle(document.querySelector(".surface-console")).backgroundColor
// => rgb(236, 228, 211)  (== #ece4d3 = --paper-2; the console page maps to bg0→--paper-2)
getComputedStyle(document.querySelector(".surface-console")).color
// => rgb(34, 28, 22)  (== #221c16 dark ink)
```
Toggle dark — console should look like its **original** dark control-room:
```js
getComputedStyle(document.querySelector(".surface-console")).backgroundColor // rgb(8, 11, 9)  (== #080b09, the original bg0)
getComputedStyle(document.querySelector(".surface-console")).color           // rgb(233, 228, 214)  (== #e9e4d6)
```
Expected: light is the big new look (verify rail, nav, tables, badges are legible — this is where the atmosphere gradients may need softening); dark closely restores the prior console. Check both `data-area` admin and recruiter routes render (accent is now persimmon in both).

- [ ] **Step 9: Commit.**

```bash
git add frontend/src/sites/console/styles/console.css frontend/src/sites/console/components/Shell.tsx
git commit -m "feat(console): light default + shared dark theme via shared tokens"
```

---

### Task 5: Converge shared component primitives + cross-surface QA + docs

Adopt the `components.css` primitives where each surface has near-identical buttons/cards/inputs/badges, finish `components.css`, run a full light/dark QA across all three surfaces, and update `frontend/CLAUDE.md`.

**Files:**
- Modify: `frontend/src/shared/styles/components.css` (finalize)
- Modify: surface CSS files where a primitive replaces a bespoke duplicate (only where it reduces divergence without restructuring layout)
- Modify: `frontend/CLAUDE.md`

**Interfaces:**
- Consumes: everything from Tasks 1–4.

- [ ] **Step 1: Audit button/card/input/badge styles across surfaces.**

Run: `grep -nE '\.btn|\.card|\.input|\.field|\.badge|\.chip|\.pill' frontend/src/sites/web/styles/site.css frontend/src/sites/employers/styles/site.css frontend/src/sites/console/styles/console.css`
Identify primitives that are structurally the same across ≥2 surfaces and now differ only by tokens (which already unified in Tasks 2–4). List them.

- [ ] **Step 2: Finalize `components.css`** so the `.ds-btn`/`.ds-card`/`.ds-input`/`.ds-badge` primitives match the visual spec the surfaces share (sizes, radii, weights observed in Step 1). Keep them token-only (no hardcoded colour). Do NOT force surfaces that have genuinely bespoke component designs to adopt them.

- [ ] **Step 3: Adopt primitives where low-risk.** For each surface where a component is now token-identical to a `ds-*` primitive, either (a) add the `ds-*` class alongside the existing class in the JSX, or (b) make the surface's existing selector `@extend`-style reference by pointing its rule body at the same tokens. Prefer (a) for buttons in new/edited markup; do not mass-rewrite stable markup. The goal is convergence, not churn — if a surface's button already uses `var(--accent)` etc., it is already harmonized and needs no change.

- [ ] **Step 4: Build.**

Run: `cd frontend && npm run build`
Expected: green.

- [ ] **Step 5: Full cross-surface QA in both themes.** For each of `#/`, `#/employers`, `#/console`:
  1. Load light; screenshot; spot-check primary button, card, input, badge, links.
  2. Toggle dark; screenshot; re-check the same.
  3. Assert no flash on reload with `localStorage["jobify-theme"]="dark"` (the pre-paint script): `document.documentElement.dataset.theme === "dark"` synchronously after load.
  4. Contrast spot-check: ink-on-paper and accent-on-paper in dark should be comfortably readable (WCAG-AA ~4.5:1 for body text). If any dark token fails, tune it in `tokens.css` (`:root[data-theme="dark"]`) and rebuild.

Record the screenshots/observations. Expected: all three surfaces share type + accent + paper/ink; each works light and dark; no flash.

- [ ] **Step 6: Update `frontend/CLAUDE.md`.** Add a short "Design system" section documenting: tokens live in `src/shared/styles/tokens.css` on `:root` (+ `:root[data-theme="dark"]`), NOT on `.surface-*`; web's names are canonical; the single global `ThemeProvider` is the deliberate exception to the per-surface provider rule (localStorage key `jobify-theme`, `data-theme` on `<html>`, pre-paint script in `index.html`); shared primitives live in `components.css` (`.ds-*`); the styleguide is intentionally divergent documentation, not wired to these tokens.

- [ ] **Step 7: Build once more and commit.**

```bash
cd frontend && npm run build
cd ..
git add frontend/src/shared/styles/components.css frontend/src/sites frontend/CLAUDE.md
git commit -m "feat(frontend): converge shared component primitives + document design system"
```

---

## Self-Review

**Spec coverage:**
- Shared `tokens.css` layer (light+dark) → Task 1. ✓
- `base.css` + `components.css` → Task 1 (created), Task 5 (finalized). ✓
- `ThemeProvider`/`useTheme`/`ThemeToggle`, single global provider → Task 1. ✓
- Fonts trimmed to web's three families → Task 1 Step 10. ✓
- Pre-paint anti-flash script → Task 1 Step 10; verified Task 5 Step 5.3. ✓
- web migration (pixel-stable light + dark) → Task 2. ✓
- employers migration (warm identity + dark) → Task 3. ✓
- console migration (light default + dark restore) → Task 4. ✓
- Component-depth convergence → Task 5. ✓
- Styleguide left untouched + documented → Task 5 Step 6 (CLAUDE.md note); no styleguide file edited. ✓
- Token home `:root` not `.surface-*` → enforced in Tasks 2–4 Step 1. ✓
- `npm run build` after every task → present in every task. ✓
- Playwright light/dark verification → Tasks 2/3/4 Step "Visual verify", Task 5 Step 5. ✓
- Contrast tuning → Task 5 Step 5.4. ✓

**Type/name consistency:** Token names match the Global Constraints list across all tasks. `useTheme()` return shape (`theme`/`resolvedTheme`/`setTheme`/`toggle`) defined in Task 1 Step 4 and consumed by `ThemeToggle` (Step 7) and surface toggles. localStorage key `jobify-theme` identical in `index.html` script, `ThemeContext.ts`, and `ThemeProvider`. The console `--paper`→`--ink` ordering hazard is explicitly corrected to a two-pass sed in Task 4 Step 4.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; sed mappings are exact; verification steps give exact expected `getComputedStyle` values.
