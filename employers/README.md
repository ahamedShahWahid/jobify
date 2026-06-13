# Jobify · for employers

The recruiter/employer **marketing & acquisition site** for Jobify — a top-of-funnel
surface for hiring teams and engineering leaders. Mostly illustrative content; no live
backend calls.

**Aesthetic:** an *engineering prospectus / technical blueprint* — cool structured paper,
deep navy ink, one signal-amber accent, hairline drafting rules, and a fanned
"ranked applicant stack" as the signature hero visual.

## Run

```bash
npm install && npm run dev   # → http://localhost:5373
```

Build / preview:

```bash
npm run build     # tsc -b && vite build → dist/
npm run preview
```

## Stack

Vite 6 + React 18 + react-router-dom 6 (**HashRouter**, static bundle — no server
rewrites). TypeScript strict. No UI framework: the design system is a single CSS file
(`src/styles/site.css`) of CSS variables. Fonts (Archivo / IBM Plex Sans / IBM Plex Mono)
are loaded in `index.html`.

## Routes

- `/` — landing (hero, stats, how-it-works, match-reason showcase, verified trust,
  pricing, FAQ, CTA).
- `/#/verify` — focused "get verified" explainer (what's checked, the steps, the payoff).
- `*` — redirects to `/`.

## CTAs

Every primary CTA deep-links to the **recruiter console** (the real product) at its dev
URL `http://localhost:5173` with a generic "Open the console →" label. The footer also
links the applicant web property (`http://localhost:5273`) and `hello@jobify.in`.

Ports: console `5173`, applicant web `5273`, this site `5373`.
