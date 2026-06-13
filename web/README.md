# Jobify Web

The public-facing web property for Jobify — three surfaces in one Vite + React + TS app:

- **Landing** (`/`) — the marketing page: hero, how-matching-works, the explanation
  differentiator, applicant + recruiter value props, CTA.
- **Explore** (`/explore`) — the applicant product: the matched feed, job detail with
  score breakdown + the "why this fits" explanation, and working apply / save / withdraw.
  Tabs for Your matches / Applied / Saved.
- **Trust** (`/trust`) — DPDP transparency: a system-status panel, the three rights
  (consent / export / delete), and a plain-language FAQ.

No UI framework — the design system lives in `src/styles/site.css` ("warm editorial
broadsheet": bone paper, persimmon accent, forest-green "verified", **Fraunces** display /
**Hanken Grotesk** body / **JetBrains Mono** for scores). Deliberately distinct from the
internal `console/` app's dark control-room look.

## Run

```bash
cd web
npm install
npm run dev        # http://localhost:5273
```

Landing and Trust are fully public (no auth). **Explore** needs an applicant session:

- **Demo feed** (default on the gate) — six seeded matches, full apply/save flow, no backend
  (`src/api/demo.ts`).
- **Live token** — paste an applicant access token + API base URL. The API must list this
  origin in `JOBIFY_CORS_ALLOW_ORIGINS` (e.g. `http://localhost:5273`). A `401` mid-session
  clears the session and returns to the gate with an "expired" notice.

`npm run build` runs `tsc -b` then `vite build` → static bundle in `dist/` (HashRouter, so
it serves from any static host with no rewrite rules).

## Structure

- `src/api/types.ts` — wire types mirroring the FastAPI applicant models **verbatim**
  (`schemas.py`, `feed.py`, `applications.py`, `saved_jobs.py`, `me.py`). Note the feed/jobs
  `EmployerRead` carries `verified: bool`, not the recruiter `verified_at`/`gst`.
- `src/api/client.ts` — `JobifyClient` interface + `HttpClient` (live, problem+json-aware).
- `src/api/demo.ts` — `DemoClient`, seeded in-memory matches with mutable apply/save state.
- `src/pages/Landing.tsx`, `src/pages/Trust.tsx`, `src/pages/explore/*`.
