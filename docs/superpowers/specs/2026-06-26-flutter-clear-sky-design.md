# Clear Sky — Flutter app visual direction — Design

**Status:** approved (brainstorm) — 2026-06-26
**Surface:** `app/` Flutter client — applicant sign-in + post-login experience (feed, cards, job detail, shell, applications, profile). Recruiter screens inherit the new tokens.

## Goal

Give the Flutter app its **own** distinctive visual identity, deliberately
diverging from the warm-paper + Fraunces-serif + terracotta "Match Statement"
system the app currently shares with the web surface (PR #44/#45).

The new direction — **Clear Sky** — is anchored on the brand's own logo blue
(`#0048A8`) and on the product's actual truth: Jobify **hands you a sentence,
not a number**, and is honest about the **caveat**. The register is **calm,
trustworthy, human — relief, not hustle**, because the product's promise is
anxiety reduction (roles come to *you*; we tell you the truth, caveat included)
for early-career Indian applicants.

### What "done" looks like

- The app wears a cool **daylight-blue** identity in both light and dark, with
  color rationed to two meanings: **brand blue = "this matters / a strong
  match,"** **amber = "the honest caveat."** Everything else is ink on sky.
- The **feed card is inverted**: the *match sentence* is the visual hero, the
  *role title* is quiet above it, and the *score* is a small monospace stamp —
  not a loud traffic-light pill.
- One orchestrated motion moment — **"the role arrives"** — and no other
  animation in the app.
- Light **and** dark palettes are both defined (the theme switcher is live).

## Background — why this is a fresh direction, not a repaint

The current Flutter theme (`app/lib/presentation/theme/`) is:

- `jobify_colors.dart` — warm paper `#F4EFE3`, terracotta accent `#D8472A`,
  brand blue `#0048A8` (secondary), forest, gold; full light + dark sets.
- `jobify_typography.dart` — **Fraunces** serif (displayLarge/Medium) +
  **Hanken Grotesk** (everything else), via `google_fonts`.
- 3-color match-score bands (`scoreLow` gold / `scoreMid` blue / `scoreHigh`
  green) rendered as a colored pill on every feed card.

This is, almost exactly, the **#1 AI-generated-design default** (warm cream +
high-contrast serif + terracotta accent). The web surface already owns that
look. The Flutter app has room for a coherent voice of its own — and Flutter's
edge over the web surface is **motion**, which is where the one risk is spent.

The screenshot `flutter-app-state.png` shows plain white because it's a web
build where `google_fonts` didn't fetch (Fraunces → system-sans fallback) and
the theme wasn't fully applied on the auth screen — it is not the intended
current look.

## Scope decisions (confirmed in brainstorm)

1. **Replace the global tokens** (`jobify_colors.dart` / `jobify_typography.dart`)
   rather than fork an applicant-only theme. One coherent identity app-wide;
   recruiter screens get the calmer look "for free" + a sanity pass. Avoids a
   two-theme split-brain.
2. **Both palettes.** Dark mode is live (profile theme switcher + `darkTheme:`
   in `app.dart`), so Clear Sky defines **light and dark** values for every
   token. Note `app/CLAUDE.md` line 20 ("Light theme only in v0") is stale —
   the switcher shipped in PR #44; this design keeps it honest.
3. **Un-unify from web, accepted.** This intentionally reverses the cross-surface
   harmonization of PR #44/#45 for the Flutter client. The trade (Flutter and
   web no longer look identical) is a conscious choice in service of a
   distinctive native identity.

## Token system

Color is **rationed**. Only two hues carry meaning; the rest is ink on a cool
sky surface. This is the discipline that keeps the accent meaningful.

### Color — `jobify_colors.dart` (replace values, keep token names where they map)

| Token | Light | Dark | Role |
|---|---|---|---|
| `paper` | `#F4F6F9` | `#0B1620` | app surface — cool daylight / calm night (not warm, not terminal-black) |
| `paper2` | `#EAEEF4` | `#0F1C28` | nav bar, recessed sections |
| `paper3` | `#DFE5EE` | `#0A141D` | deepest recess / pressed |
| `panel` / `card` | `#FFFFFF` | `#13212E` | the "arrived" card |
| `ink` | `#0F2440` | `#E8EDF3` | primary text |
| `inkSoft` | `#5C6B7E` | `#9DB0C2` | secondary text / metadata |
| `inkFaint` | `#94A1B2` | `#5E7186` | disabled / faint |
| `line` | `#E3E8EF` | `#1E2D3B` | hairline borders / dividers |
| `lineStrong` | `#CED7E2` | `#2C3F50` | prominent dividers |
| **`brand`** | `#0048A8` | `#5B9BFF` | **the one meaning color** — the match + primary action |
| `brandDeep` | `#00367D` | `#3F86F5` | pressed / hover |
| `brandWash` | `#E7EEF8` | `#13294A` | tint behind a strong match / selected nav |
| `brandInk` | `#FFFFFF` | `#04101F` | text/icon on brand fill |
| **`caveat`** | `#C77A1E` | `#E0A24A` | **the honest weakness, only** |
| `caveatWash` | `#FBF0E0` | `#2A1F0E` | caveat rule / tint |
| `danger` | `#C0362B` | `#FF6A5A` | errors / destructive |

**Retired:** the 3-color score bands (`scoreLow`/`scoreMid`/`scoreHigh`). See
"The score, demoted" below.

Dark-mode discipline (per project memory, dark-mode traps): no hardcoded
near-white/near-dark foregrounds inside any brand- or caveat-filled panel — all
children resolve from tokens so auto-inverting surfaces stay legible in both
themes. Verify both themes before completion.

### Type — `jobify_typography.dart` (replace families)

- **Display — Schibsted Grotesk, w600** (calm, trustworthy; *not* w700+ — the
  heavy-black serif/sans is the cliché tell). Hero match sentence + screen
  titles.
- **Body — Inter**, w400 / w500.
- **Data — IBM Plex Mono** for the score stamp, ₹ figures, timestamps,
  generator attribution. The "shows its work" voice. *(Chosen over Space Mono:
  calmer, more on-register; the one deliberate risk is spent on motion, not the
  type face.)*

All via `google_fonts`, same as today. Widget tests continue to use
`ThemeData.light(useMaterial3: true)`, **not** `buildTheme()` (google_fonts
network fetch fails offline/CI — existing invariant, unchanged).

Type scale (Material 3 roles):

| Role | Font | Size | Weight | Use |
|---|---|---|---|---|
| displayLarge | Schibsted Grotesk | 34 | 600 | sign-in hero |
| displayMedium | Schibsted Grotesk | 28 | 600 | large moments |
| headlineLarge | Schibsted Grotesk | 24 | 600 | screen titles ("For you") |
| headlineMedium | Schibsted Grotesk | 20 | 600 | section titles |
| titleLarge | Inter | 18 | 600 | app-bar title |
| titleMedium | Inter | 16 | 600 | role title in card |
| bodyLarge | Inter | 16 | 400 | long-form (job description) |
| bodyMedium | Inter | 14 | 400 | card body |
| bodySmall | Inter | 12 | 400 | timestamps/secondary |
| labelLarge | Inter | 14 | 600 | buttons |
| labelMedium | Inter | 12 | 600 | small labels |
| labelSmall | Inter | 11 | 600 | micro labels |

The **match sentence** is its own treatment inside the card: **Inter 17 / w500
/ ink**, deliberately one notch *larger than the role title* (16/w600) — the
visual statement that the reason matters more than the label. The **score
stamp** and other data are **IBM Plex Mono 12 / w500**.

### Radii, spacing, motion tokens

- Radii: keep the scale; cards move to **`xl` (16)** for the softer "arrived
  object" feel; buttons `lg` (12); stamps/pills `pill`.
- Spacing: unchanged (4-base scale).
- Motion tokens (`jobify_motion.dart`): keep durations; add a spring/emphasized
  curve for the arrival stagger.

## The signature — "the role arrives"

The single orchestrated motion moment, and the **only** animation in the app
(scattered animation reads as AI-generated — restraint is the point).

- **Feed first-load and refresh only.** The first ~6 visible cards settle in
  with a staggered spring: `translateY(+16 → 0)` + `opacity(0 → 1)` +
  `scale(0.98 → 1)`, ~60 ms stagger per card, emphasized/spring curve — like
  briefs dropping onto a desk.
- **Not** during scroll or pagination (would scatter into noise). Subsequent
  pages append without entrance animation.
- **Sign-in** gets a quiet sibling: wordmark → tagline → button rise, once, on
  first build (~600 ms total).
- **Reduced motion respected:** when `MediaQuery.disableAnimations` is true (or
  the OS reduce-motion flag), cards/elements appear instantly with no transform.

Implementation note: a small reusable entrance widget (e.g.
`ArrivalStagger`/`Arrive`) wrapping the list children, driven by one
`AnimationController` with per-index `Interval`s, so the behavior is in one
place and trivially disabled for reduced motion and in tests.

## The card, inverted (the signature element)

The feed item card (`feed_item_card.dart`) is the most-seen surface and carries
the thesis. Today: a loud score pill leads, the sentence is buried last. Clear
Sky inverts the hierarchy.

```
┌─────────────────────────────────────┐
│ ACME PAYMENTS              87 ·mono· │  employer (Inter 13/600 slate) + score stamp
│ Senior Backend Engineer             │  role title (Inter 16/600 ink) — quiet
│ Your Django + REST work lines up    │  THE SENTENCE (Inter 17/500 ink) — hero
│ with what this team is missing.     │
│ ▎ Counts against: 3 yrs vs 5 req'd  │  caveat — amber rule, only if present
│ Bengaluru · 3d ago                  │  meta (IBM Plex Mono 12 slate)
└─────────────────────────────────────┘
```

- Card: `card` fill, radius `xl` (16), 1px `line` border, very soft shadow
  (the "arrived object").
- **Match sentence is the largest text** in the card. Role title quieter above
  it. This is the reversal made visual.
- **Caveat** is the only amber on the screen: a thin amber left-rule on the
  "counts against …" line. Rare, honest. Rendered only when
  `explanation.caveat != null`.
- Closed jobs keep a muted "Closed" pill (slate, not amber/blue — neither
  meaning applies).

### The score, demoted

The score becomes a small **monospace stamp** (e.g. `87` in IBM Plex Mono with
a quiet "MATCH" micro-label), replacing the colored pill:

- **Ordinary matches** (`total_score < 0.80`): quiet **ink/slate** — no color.
- **Strong matches** (`total_score ≥ 0.80`): **brand blue** — the one meaning
  color, "this one's worth your attention."

This retires the 3-way low/mid/high traffic light in favor of **one meaningful
blue state**, consistent with rationed color and with the thesis ("a sentence,
not a number"). `JobifyScoreBadge` is reworked from a 3-band colored pill into
this two-state mono stamp. The numeric score remains visible; only its visual
weight and color semantics change.

## Per-screen application

- **Sign-in (`sign_in_screen.dart`):** sky-paper surface; left-aligned
  composition sitting at ~40% height (more confident than dead-center);
  **"Jobify" wordmark in brand blue** (brand identity use of the logo color, not
  a "meaning" use); tagline kept ("Roles that match you, not the other way
  around."); clean **bordered** Google button (white fill, `line` border, ink
  label, radius `lg`) on mobile, GIS rendered button on web (the existing
  `kIsWeb` branch is preserved); the quiet entrance sequence.
- **Nav shell (`jobify_shell_scaffold.dart`, recruiter shell):** `paper2` bar;
  selected destination = **brand-blue** icon + label on a soft `brandWash`
  indicator; unselected = `inkSoft`.
- **Feed / Saved (`feed_screen.dart`, `saved_screen.dart`):** "For you" /
  "Saved" titles in Schibsted; the new card; arrival stagger on the feed only.
- **Job detail (`job_detail_screen.dart`):** the "Why this match" card adopts
  the same sentence-led hierarchy (sentence hero, mono stamp, amber caveat,
  mono generator attribution); description in `bodyLarge`.
- **Applications (`applications_screen.dart`):** Applied pill = `brandWash` +
  `brandInk`-on-blue text (active/positive → the meaning color); Withdrawn =
  muted `paper2` + `inkSoft`. Dates in IBM Plex Mono.
- **Profile (`profile_screen.dart`):** section headers in Schibsted; detail
  rows in Inter; ₹/CTC and dates in mono; theme switcher (System/Light/Dark)
  retained.
- **Shared widgets:** `jobify_empty_state.dart`, `jobify_loading_view.dart`,
  `jobify_error_view.dart`, status pills, detail rows — restyled from the new
  tokens; structure unchanged.
- **Recruiter screens:** inherit tokens; a visual sanity pass (no bespoke
  redesign in this slice).

## Out of scope

- No behavioral/routing/data changes — this is a visual-layer reskin
  (tokens, typography, the card widget, one motion widget, per-screen styling).
- No recruiter-specific redesign beyond inheriting tokens + sanity pass.
- No logo/brand asset changes (wordmark uses the existing brand blue).
- No new dependencies beyond the two added Google Fonts families (Schibsted
  Grotesk, Inter, IBM Plex Mono are all in the `google_fonts` set).

## Quality floor

- Responsive down to mobile widths; visible keyboard focus; reduced motion
  respected (the arrival stagger is the one place it matters).
- Both light and dark verified — especially no hardcoded near-white/near-dark
  foregrounds inside brand/caveat panels (dark-mode auto-invert trap).
- CI green before done (repo-root verbatim): `dart format --set-exit-if-changed
  lib test` · `flutter analyze` · `flutter test`. Widget tests keep using
  `ThemeData.light(useMaterial3: true)`.

## Risks / watch-list

- **Score-band retirement is a product-feel change**, not just chrome — agreed
  in brainstorm, but flagged here so it's a conscious record.
- **google_fonts adds two new families** → first-paint fetch on a cold cache;
  acceptable (same mechanism as today's Fraunces/Hanken).
- **Recruiter screens** may surface a hardcoded color or a layout that assumed
  the warm palette — the sanity pass must actually open them in both themes.
