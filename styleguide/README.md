# Jobify Design System — Specimen Catalogue

A single, self-contained static page that documents the design languages of all
**three Jobify frontend properties** side by side:

- **Console** — control-room editorial, dark phosphor-ink (admins & recruiters)
- **Web** — warm editorial broadsheet, bone paper (applicants)
- **Employers** — engineering prospectus, cool navy (recruiter acquisition)

The page is framed as a type-foundry specimen book in its own neutral, fourth
palette (warm off-white paper, near-black ink, an oxblood chrome accent), set in
**Spectral** with **Martian Mono** labels — deliberately distinct from all nine
app fonts so it reads as the catalogue that *frames* the three properties.

Each app section loads and uses that app's **real Google Fonts** and its **real
`:root` color tokens**, and statically recreates two to three of its signature
components so they look right in context.

## What it contains

1. **Cover / masthead** with a one-line thesis and a contents list
2. **Overview** — shared principles + a 3-up app summary card grid
3. **One full section per app** — identity, type specimen (display / body / mono),
   color-token swatches with names + hex, a type-size ramp, and component
   specimens
4. **Cross-app comparison** table
5. **Colophon** describing how the system is structured

## How to view

It is pure static HTML + CSS — no build step, no framework, no dependencies.

```bash
# open directly
open styleguide/index.html

# or serve it (any static server works)
npx serve styleguide
# then visit the printed http://localhost:… URL
```

The page fetches the app fonts from Google Fonts, so an internet connection gives
the most faithful rendering (it degrades to system fonts offline).

## Maintenance

This is a **hand-maintained snapshot**. The design tokens are authoritative
**in each app's CSS**, not here:

- `console/src/styles/console.css`
- `web/src/styles/site.css`
- `employers/src/styles/site.css`

When a token value or font changes in one of those files, update the matching
swatch / specimen on this page to keep the catalogue accurate. It is
documentation, not a build artifact.

## Files

- `index.html` — the whole specimen page
- `styleguide.css` — the styleguide's chrome + per-app theme scopes + component specimens
- `.gitignore`
- `README.md`
