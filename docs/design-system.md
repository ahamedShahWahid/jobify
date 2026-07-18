# Jobify Design System — Claude Standard

> **Purpose.** The self-contained design standard Claude (and humans) apply when building or
> reviewing any Jobify UI. Read this before styling anything in `frontend/` or `app/`.
>
> **Source of truth is code, not this file.** Values below are a snapshot (**2026-07-16**) of:
> - `frontend/src/shared/styles/tokens.css` (web tokens, light + dark)
> - `frontend/src/shared/styles/base.css` / `components.css`
> - `app/lib/presentation/theme/jobify_colors.dart` / `jobify_typography.dart` / `jobify_radii.dart` / `build_theme.dart`
> - `frontend/src/shared/format.ts` (India-first formatting)
>
> If this file and the code disagree, the code wins — update this file.
>
> **This supersedes `frontend/styleguide/`'s three-design-languages model** (Console / Web /
> Employers as separate palettes). Tokens were unified in 2026-07: both web surfaces consume ONE
> shared token set; the applicant web surface was removed in favor of the Flutter app. The
> styleguide remains as a historical specimen page.

---

## 1. The system in one sentence

**Two palettes, one philosophy.** Web (warm editorial) and Flutter (cool "Clear Sky") have
*different* hex values and *different* font stacks — what is shared, and what this standard
actually enforces, is the color-rationing philosophy below. Never "sync" hex values across
platforms; sync **roles**.

### The shared philosophy (the spine — applies everywhere)

1. **Color is rationed.** Only two colors carry meaning; everything else is ink on paper.
2. **Brand blue = interactive + the match.** Primary CTAs, links, active nav/tabs, focus rings,
   unread indicators, toggles-on, selected states, data-viz (charts, score bars, funnels). One
   color for "you can act on this / this is the match."
3. **Exactly one accent = the honest caveat.** Web: persimmon. Flutter: amber. It marks the
   weakest match dimension, a genuine attention state (pending verification, pending invite), or
   at most one thesis emphasis per page. It is **not** decoration, not a data highlight, not the
   CTA color, not links.
4. **Three voices of type:**
   - **Mono** — the machine: scores, ₹ figures, timestamps, eyebrows/kickers, gauges, stats,
     chart/table figures. *Numbers always render in mono, never big display type.* Scores are
     small mono "receipt stamps," not billboard numerals.
   - **Display face** — the voice/explanation: headings and the match "fit" sentence (the
     *reason* leads; the score is demoted). Web uses serif italic for the reason line.
   - **Sans** — the interface: body, labels, controls.
5. **Restraint in weight.** Display type sits at ~460–600 weight, never 800/900 heavy-black.
6. **Light AND dark always.** Every surface must be verified in both themes. The recurring bug
   class: a hardcoded near-white/near-dark color inside a panel that auto-inverts via tokens.
7. **India-first at the render layer only.** Displayed times are IST, money is ₹/lakh with
   Indian 2,3 grouping; storage and transport stay UTC ISO / raw numbers (§6).

---

## 2. Web palette (frontend/) — "warm editorial"

Tokens live on `:root` (light) and `:root[data-theme="dark"]` in
`src/shared/styles/tokens.css`. **All web CSS uses `var(--token)` — never a raw hex.**
Surfaces (`.surface-employers`, `.surface-console`) must NOT redefine tokens.

### 2.1 Color tokens

| Token | Role | Light | Dark |
|---|---|---|---|
| `--paper` | page background | `#f4efe3` | `#0d110e` |
| `--paper-2` | recessed surface | `#ece4d3` | `#080b09` |
| `--paper-3` | deeper / hover | `#e4dac4` | `#1a201a` |
| `--panel` | raised card | `#faf7ef` | `#121712` |
| `--ink` | primary text | `#221c16` | `#e9e4d6` |
| `--ink-2` | secondary text | `#3b362c` | `#cdc7b8` |
| `--ink-soft` | muted text | `#6c6354` | `#b7b2a3` |
| `--ink-faint` | faintest text | `#9b917e` | `#6f7868` |
| `--line` | default border | `#d9cfb9` | `#232b23` |
| `--line-strong` | emphasized border | `#c4b89c` | `#34402f` |
| `--line-faint` | hairline | `rgba(34,28,22,.06)` | `rgba(233,228,214,.06)` |
| `--brand-blue` | interactive / the match | `#0048a8` | `#4f8cff` |
| `--brand-blue-deep` | pressed / deep | `#003c8f` | `#2f6fe0` |
| `--brand-blue-tint` | wash behind a match | `#e1ecf8` | `rgba(79,140,255,.16)` |
| `--brand-blue-bright` | on-dark-legible step | `#0048a8` | `#4f8cff` |
| `--accent` | **the caveat** (persimmon) | `#d8472a` | `#ff6a48` |
| `--accent-deep` | caveat, pressed | `#b23a20` | `#d8472a` |
| `--accent-wash` | caveat tint | `#f3d9cf` | `rgba(255,106,72,.14)` |
| `--accent-ink` | text on accent fill | `#ffffff` | `#1a0f0a` |
| `--forest` / `--ok` | verified / trust / success | `#1f4034` | `#6fdc8c` |
| `--forest-soft` | success wash | `#cfdcd2` | `rgba(111,220,140,.16)` |
| `--gold` | warn | `#b8842f` | `#ffb000` |
| `--gold-soft` | near-match / caution wash | `#efe2c4` | `rgba(255,176,0,.16)` |
| `--danger` | destructive / error | `#b23a20` | `#ff5d49` |
| `--danger-wash` | destructive tint | `#f3dcd4` | `rgba(255,93,73,.14)` |
| `--shadow` | card shadow | `18px 22px 0 -8px rgba(34,28,22,.08)` | `0 18px 40px -18px rgba(0,0,0,.6)` |

### 2.2 Type + layout tokens

| Token | Value |
|---|---|
| `--serif` | `"Fraunces", Georgia, serif` — display/voice; headings at weight ~460–560 with `font-optical-sizing: auto`, never 900 |
| `--sans` | `"Hanken Grotesk", system-ui, sans-serif` — interface; body 16px / 1.6 |
| `--mono` | `"JetBrains Mono", monospace` — the machine voice |
| `--maxw` | `1180px` content max-width |
| `--ease` | `cubic-bezier(0.2, 0.7, 0.2, 1)` — the app-wide easing |

### 2.3 Web application rules

- **Filled brand-blue buttons pair with `color: var(--paper)`** so the label flips correctly in
  both themes.
- **Accent usage, precisely:** weakest score bar (`.bar-row:has(.bar-fill.acc)`), the why-match
  `⌁` caveat marker, console `.chip.acc` pending/attention states. The reason blockquote border
  is **neutral** — the reason is the voice, not the caveat.
- **Deliberate exceptions (do not "fix"):** console `.jc-card` is always-light (hardcoded warm
  palette for candidate preview cards) — intentionally not tokenized.
- **Leverage classes:** when restyling, edit `.kicker`, `.explain`, base `h1,h2,h3`,
  `.btn.primary` / `.btn` / `a` / `.rail-link.active` — one edit restyles every page.
- **Theming mechanics:** one global `ThemeProvider` (`src/shared/theme/`) sets `data-theme` on
  `<html>`, persists `localStorage["jobify-theme"]` (`light`/`dark`/`system`). `index.html`
  carries an inline pre-paint script stamping `data-theme` before CSS parses — never defer or
  bundle it. The 3-way switch (`.ds-theme-switch`) reads stored `theme`, not `resolvedTheme`.

---

## 3. Flutter palette (app/) — "Clear Sky"

Tokens live in `JobifyColors` / `JobifyTypography` / `JobifyRadii`; `buildTheme(brightness)`
maps them into a Material 3 `ColorScheme`. **Widgets consume `Theme.of(context)` /
`JobifyColors.*` — never inline `Color(0x…)` literals in screens.**

### 3.1 Color tokens

| Token | Role | Light | Dark |
|---|---|---|---|
| `paper` | page background | `#F4F6F9` | `#0B1620` |
| `paper2` | recessed surface | `#EAEEF4` | `#0F1C28` |
| `paper3` | deeper / hover | `#DFE5EE` | `#0A141D` |
| `panel` | raised card | `#FFFFFF` | `#13212E` |
| `ink` | primary text | `#0F2440` | `#E8EDF3` |
| `inkSoft` | muted text | `#5C6B7E` | `#9DB0C2` |
| `inkFaint` | faintest text | `#94A1B2` | `#5E7186` |
| `line` | default border | `#E3E8EF` | `#1E2D3B` |
| `lineStrong` | emphasized border | `#CED7E2` | `#2C3F50` |
| `brandBlue` | interactive / the match | `#0048A8` | `#5B9BFF` |
| `brandBlueDeep` | pressed / deep | `#00367D` | `#3F86F5` |
| `brandBlueTint` | wash behind a match | `#E7EEF8` | `#13294A` |
| `brandInk` | text/icon on brand fill | `#FFFFFF` | `#04101F` |
| `caveat` | **the caveat** (amber) | `#C77A1E` | `#E0A24A` |
| `caveatWash` | caveat tint | `#FBF0E0` | `#2A1F0E` |
| `caveatInk` | text on caveat fill | `#FFFFFF` | `#1F1404` |
| `danger` | destructive / error | `#C0362B` | `#FF6A5A` |

**Brand canvas — theme-independent BY DESIGN** (the bold-blue hero identity on sign-in and bold
headers does **not** invert with light/dark; do not "theme" it):

| Token | Value |
|---|---|
| `brandCanvasTop` | `#0B53B8` |
| `brandCanvasMid` | `#013A86` — doubles as the on-white-button foreground (deliberately coupled) |
| `brandCanvasBottom` | `#001229` |
| `brandGlow` | `#7FB0FF` — glow/dot against the canvas |

### 3.2 Typography (all via `google_fonts`)

Display = **Schibsted Grotesk** w600 (calm, not heavy-black). Body/labels = **Inter**.
Data voice = **IBM Plex Mono** via `JobifyTypography.mono()`.

| Style | Font | Size / weight / height |
|---|---|---|
| displayLarge | Schibsted Grotesk | 34 / w600 / 1.15 |
| displayMedium | Schibsted Grotesk | 28 / w600 / 1.18 |
| headlineLarge | Schibsted Grotesk | 24 / w600 / 1.22 |
| headlineMedium | Schibsted Grotesk | 20 / w600 / 1.28 |
| titleLarge / titleMedium | Inter | 18 / 16, w600 |
| bodyLarge / bodyMedium / bodySmall | Inter | 16 / 14 / 12, w400 |
| labelLarge / labelMedium / labelSmall | Inter | 14 / 12 / 11, w600 |
| `mono(fontSize: …)` | IBM Plex Mono | w500 default — score stamps, ₹, dates |

### 3.3 Radii

`JobifyRadii`: sm 4 · md 8 (buttons, snackbars) · lg 12 · xl 16 (cards) · pill 999.

### 3.4 Flutter application rules

- `ColorScheme.primary` = brand blue → CTAs, the "Applied" pill, selected nav. `secondary` /
  `tertiary` stay in the brand family (unconsumed; kept on-palette so accidental use isn't off-brand).
- Cards: `surfaceContainerHighest` (panel), radius XL, elevation 0. Buttons: radius MD,
  20/14 padding, `labelLarge`. AppBar: flat, left-aligned title, paper background.
- "Spec sheet" screens (Profile/Edit/Preferences): label left (Inter, quiet), value right
  (`JobifyTypography.mono`, right-aligned); incomplete fields get caveat-amber tappable "Add"
  prompts, not a dead dash.
- **Widget tests use `ThemeData.light(useMaterial3: true)`, never `buildTheme()`** —
  `google_fonts` fetches over the network and fails in offline CI.

---

## 4. Convergence / divergence map

Consult this before any "make the platforms match" change.

| Aspect | Web | Flutter | Shared? |
|---|---|---|---|
| Philosophy (§1) | ✔ | ✔ | **Yes — the only thing to sync** |
| Brand blue (light) | `#0048a8` | `#0048A8` | Yes (the logo blue, identity constant) |
| Brand blue (dark) | `#4f8cff` | `#5B9BFF` | **No** — tuned per palette |
| Paper family | warm cream | cool sky | **No** |
| Caveat accent | persimmon `#d8472a` | amber `#C77A1E` | **Same role, different hue** |
| Display face | Fraunces (serif) | Schibsted Grotesk | **No** |
| Interface face | Hanken Grotesk | Inter | **No** |
| Mono face | JetBrains Mono | IBM Plex Mono | **Same role, different face** |
| Theme-independent hero | — | `brandCanvas*` | Flutter-only |
| Success/warn tokens | forest / gold | — (no equivalents yet) | Web-only |

A brand-identity change (e.g. the logo blue) touches **both** `tokens.css` and
`jobify_colors.dart` — as two deliberate edits, not a copy-paste of values.

---

## 5. Brand

- Logo: blue `#0048A8` J-person mark + wordmark, tagline **"Job will find you."**
- Per-surface asset copies exist (web + Flutter assets); on dark surfaces use the mark-only
  crop (the letter counters are near-white overpaints — the full wordmark only works on light).
- Emails use PNG, never SVG (`core/emails/templates/`).

---

## 6. India-first formatting (all surfaces)

Storage + transport are **UTC ISO / raw numbers**; only the render layer localizes.

- Web: `src/shared/format.ts` is the single source — `istClock` / `istDateTime` / `istDate`
  (Asia/Kolkata, h23), `inr` ("₹25,00,000", Indian 2,3 grouping), `inrLakh` ("₹12.5L").
  Console stamps keep the precise UTC ISO in a `title` tooltip. Surface-local helpers must
  **delegate** to it (thin re-exports), never re-implement. `Intl.*Format` instances stay
  hoisted to module constants — never constructed per call/render.
- Flutter: same conventions; ₹/lakh and IST at render time, `DateFormat` instances module-static.
- Never use `toISOString()` / `getUTC*` / `toLocaleDateString(undefined, …)` for **display**.

---

## 7. Hard rules (the review gate)

**MUST**
1. Colors via tokens only — `var(--token)` on web, `JobifyColors.*` / `Theme.of(context)` in
   Flutter. No raw hex in surface/screen code (exceptions: §2.3 `.jc-card`, §3.1 brand canvas).
2. Numbers (scores, ₹, counts, dates) render in the mono voice.
3. Brand blue for everything interactive; `var(--danger)` / `danger` for destructive.
4. Accent/caveat appears only for: weakest dimension, genuine attention state, ≤1 thesis
   emphasis per page.
5. Verify **both themes** on any styled change; on web also both surfaces if shared CSS moved.
6. Displayed time/money goes through the shared formatters (§6).
7. New web CSS scoped under `.surface-*` unless deliberately shared.

**MUST NOT**
1. Redefine tokens on `.surface-*`, or fork per-surface palettes (that model is retired).
2. Use accent for CTAs, links, active nav, focus, decoration, or data highlights.
3. Ship display type at weight 800/900, or numbers in big serif/display type.
4. Hardcode a near-white/near-dark color inside a token-inverting panel (the #1 dark-mode bug).
5. Invert Flutter's `brandCanvas*` with the theme.
6. Defer/bundle the web pre-paint theme script, or read `resolvedTheme` for switch active-state.
7. Call `GoogleFonts.*` in widget tests, or construct `Intl.*Format` per render.

---

## 8. Verify checklist (after any UI change)

- [ ] Light theme and dark theme both checked (web: toggle via the theme switch; Flutter: both
      brightnesses).
- [ ] No new raw hex/color literals outside token files (`grep -rnE "#[0-9a-fA-F]{3,8}" <changed files>`,
      then justify every hit).
- [ ] Numbers in mono; accent count on the page ≤ 1 meaning + attention states.
- [ ] Times display as IST, money as ₹/lakh, via the shared formatters.
- [ ] Web: nav literals carry the surface prefix; no raw `<a href="/#…">`.
- [ ] Flutter: `flutter analyze` + widget tests green (with `ThemeData.light()`).
