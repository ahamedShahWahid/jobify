# Unify `web` + `console` + `employers` into one app — design

**Date:** 2026-06-23
**Status:** Approved (design); implementation plan to follow.

## Goal

Collapse the three repo-root React/Vite/TS web properties — `web`, `console`,
`employers` — into a **single React app** with one build and one deploy, surfaces
reached by route prefix (`/`, `/employers`, `/console`). This is the "one single
app + deduplicate the shared layer" option (option **B**): merge the apps **and**
reconcile their divergent shared code into one shared module set.

The static-HTML properties `emails/` and `styleguide/` are **out of scope** — they
have no build step and stay at the repo root untouched.

## Why (context)

The three apps share an identical stack (React + `react-router-dom` + Vite + TS)
and were seeded from a common shape, but evolved apart:

- `api/client.ts` differs by ~267 lines (web vs console), `api/types.ts` ~212,
  `session.tsx` ~91, `env.ts`, `auth/*`, `components/bits.tsx` ~170.
- The divergence is **mostly the endpoint surface** (`JobifyClient` applicant
  methods vs `ConsoleClient` admin/recruiter methods) — legitimately different
  API, not duplication. The underlying **transport core** (token store, error
  shaping, `request()` + single-flight refresh) is ~90% identical.

So the dedup wins concentrate in the plumbing (transport, session provider, env,
auth/GSI); the genuine per-surface code (pages, layouts, endpoint methods, types)
stays separate.

### Audiences / surfaces (unchanged by this work)

- **web** — public applicant site: marketing landing + live applicant surfaces
  (Explore/Feed, Applications, Inbox, Invites, Profile, Trust, Welcome).
- **employers** — public recruiter **marketing** site (illustrative, no live
  backend; `/verify`).
- **console** — **internal** ops: admin moderation (audit log, suspend/unsuspend,
  employer verification) + recruiter job/team management. Live backend.

### Decisions taken during brainstorming

- **One single app, one build, one deploy** (not a workspace / multi-entry split).
- **Console fully merged, no special handling** — `/console` is just another route
  in the main bundle. The API enforces `_require_admin`/`_require_recruiter`, so
  data is safe; the admin UI being present in the bundle is accepted.
- **Sessions stay independent per surface** — share the provider *code*, not the
  live session state (web=applicant, console=admin/recruiter are mutually
  exclusive roles with different clients). Preserves today's behavior exactly.
- **New `frontend/` dir**, surface names kept 1:1 (`sites/web`, `sites/employers`,
  `sites/console`).
- **Selective `bits.tsx` dedup** — share only genuinely-identical primitives.

## Key mechanical fact: HashRouter

All three apps use **`HashRouter`** (static bundle, no server rewrites; routes live
after the `#`). Consequences:

- No server-side routing to reconcile, no Vite `base` / router `basename` juggling.
- The merged app is still **one static `dist/`** served from one location.
- Route "prefixes" are hash-route prefixes: `/#/`, `/#/employers`, `/#/console/...`.
- Surfaces are sibling `<Route>` subtrees under one `<HashRouter>`.

## Structure

New top-level dir `frontend/` replaces `web/`, `console/`, `employers/`:

```
frontend/
  index.html · package.json · vite.config.ts · tsconfig.json · .env(.example)
  src/
    main.tsx            # one React root
    App.tsx             # one <HashRouter> mounting the three surfaces
    shared/
      api/transport.ts        # TokenStore, ApiError, errorMessage, formatDetail,
                              #   readDetail, BaseHttpClient (request + refresh)
      api/types.ts            # MeResponse ONLY (the shared identity shape)
      session/createSession.tsx   # generic SessionProvider/useSession factory
      auth/gsi.ts             # GSI script loader
      auth/GoogleSignInButton.tsx # one button (props for label/theme)
      env.ts                  # GOOGLE_CLIENT_ID, API_BASE_URL
      components/             # genuinely-identical primitives only
    sites/
      web/        # "/"            applicant + public landing
        client.ts (JobifyClient impl) · pages/ · components/Chrome.tsx · styles/ · routes
      employers/  # "/employers"  recruiter marketing
        pages/ · components/Chrome.tsx · styles/ · routes
      console/    # "/console"    admin + recruiter ops
        client.ts (ConsoleClient impl) · pages/ · components/Shell.tsx · styles/
        area.ts (Area/areasForRole/landingFor) · routes
```

Top-level router:

```tsx
<HashRouter>
  <Routes>
    <Route path="/employers/*" element={<EmployersApp />} />   {/* no session */}
    <Route path="/console/*"   element={<ConsoleApp />} />     {/* console session */}
    <Route path="/*"           element={<WebApp />} />         {/* web session */}
  </Routes>
</HashRouter>
```

Each `*App` mounts its own `SessionProvider` (built from the shared factory) around
its own `<Routes>`. Employers needs none.

Route remap (the only collision is `/`, claimed by both web and employers):

| Was (web) | Now      | Was (employers) | Now              | Was (console)        | Now                    |
| --------- | -------- | --------------- | ---------------- | -------------------- | ---------------------- |
| `/`       | `/`      | `/`             | `/employers`     | `/signin`            | `/console/signin`      |
| `/explore`| `/explore`| `/verify`      | `/employers/verify`| `/admin/*`         | `/console/admin/*`     |
| `/applications` etc. | unchanged |       |                  | `/recruiter/*`       | `/console/recruiter/*` |

## The dedup

### Shared, clean extractions (high value, low risk)

1. **`shared/api/transport.ts`** — `TokenStore`, `ApiError`, `errorMessage`,
   `formatDetail`, `readDetail`, and a `BaseHttpClient` class holding the
   `request()` + single-flight refresh (`refreshSingleFlight`/`doRefresh`)
   machinery. Each surface's typed client *extends* `BaseHttpClient` and declares
   only its own endpoint methods. Canonical reconciliations:
   - `ApiError` keeps the **3rd `requestId?` arg** (console's richer version).
   - `formatDetail` keeps the **`loc`-aware 422 flattening** (console's version).
   - The single 401-recoverable slug (`invalid_access_token`), single-flight
     refresh, and `_inFlight = null` BEFORE settle ordering are preserved verbatim
     (they mirror `app/`'s `RefreshOn401Interceptor` — load-bearing).

2. **`shared/session/createSession.tsx`** — a generic factory returning
   `SessionProvider`/`useSessionStore`/`useSession` parameterized by the client
   type and a `connectDemo` factory. `connectGoogle`/`connectLive`/`makeLiveClient`
   live here once. Canonical reconciliations:
   - `GoogleOAuthResponse.user.applicant_id` typed `string | null` (web's version
     is correct; recruiter/admin have null applicant_id).
   - Console's `Area`/`areasForRole`/`landingFor` role logic is **not** in the
     shared core — it lives in `sites/console/area.ts` and composes on top.
   - Method naming unified: `signOut` (web) vs `disconnect` (console) → pick
     `signOut` as canonical; update console call sites.

3. **`shared/env.ts`** — adopt console's defensive `.trim() || undefined` /
   `.trim() || <default>` form.

4. **`shared/auth/`** — one GSI loader (`gsi.ts`) + one `GoogleSignInButton`
   (props for label/theme) reconciling the 106/58-line divergence. Behavior
   (rendered-button ID-token flow) is identical in intent across both.

### Selective (medium value, medium risk)

5. **`components/bits.tsx`** (web 69 / console 159 lines, ~170 diff) — extract only
   the genuinely-identical primitives into `shared/components/`; leave
   surface-specific variants in `sites/*/components`. Requires a careful diff and a
   **manual visual check** (no test net). Document which primitives moved and which
   stayed.

### Deliberately NOT shared (legitimately per-surface)

- **`Chrome.tsx` / `Shell.tsx`** layouts — different per audience (web vs employers
  diverge ~136 lines; console has its own `Shell`). Keep per-site.
- **`pages/`** — entirely surface-specific.
- **`types.ts`** — only `MeResponse` is shared (used by the session core). The
  overlapping `JobRead`/`EmployerRead` names have **different shapes** per surface
  (e.g. console carries demo-only verification fields). Keeping them per-site
  avoids DTO contract drift — a known hazard in this codebase.

### Non-goal (YAGNI)

Unifying live session *state* across surfaces (one sign-in spanning applicant +
console). Roles are mutually exclusive and the clients differ; a unified-auth
redesign is out of scope and would add behavioral risk with no asked-for benefit.

## CSS — the highest-risk part

The three stylesheets (`web/site.css`, `employers/site.css`, `console/console.css`)
define **global** selectors (`body`, `:root` custom properties, generic class
names). In one bundle the last import wins → cross-surface bleed.

Mitigation: wrap each surface's root element in a surface class
(`surface-web` / `surface-employers` / `surface-console`) and **scope each
stylesheet's selectors under that class**. Shared `:root` design tokens (the brand
palette) may stay global if identical across surfaces; conflicting tokens get
scoped. This is manual surgery with no automated test, so verification is a
per-surface visual smoke check (see Verification).

## Build / dev / env

- One `package.json` (deps near-identical: react, react-dom, react-router-dom +
  vite/tsc/@vitejs/plugin-react), one lockfile.
- One `vite build` → one `dist/`; one `npm run dev` on port **5173**;
  `tsc -b` for typecheck.
- One `.env` / `.env.example` with `VITE_GOOGLE_CLIENT_ID` + `VITE_API_BASE_URL`
  (both apps already use these exact names; employers needs neither but inherits
  them harmlessly).

## Phased cutover

Each phase is independently verifiable (`tsc -b` clean + `vite build` succeeds +
manual smoke):

1. **Scaffold** `frontend/` (package.json, vite/ts config, index.html, main.tsx,
   top-level `App.tsx` router) + `shared/` core (transport, session factory, env,
   auth, shared types).
2. **Port web** → `sites/web` on the shared core; verify `/#/` behaves identically.
3. **Port console** → `sites/console` at `/#/console/*`; verify (incl. role
   gating + audit/recruiter areas).
4. **Port employers** → `sites/employers` at `/#/employers/*`; verify.
5. **CSS scoping pass + `bits.tsx` reconciliation**; delete old `web/`, `console/`,
   `employers/` dirs; update `README`s and the `jobify-web-frontends.md` memory
   note.

## Verification (no automated test suite exists for these apps)

Per-phase gate:

- `tsc -b` reports no errors.
- `vite build` succeeds.
- Manual smoke of each affected surface: route loads, the auth gate renders
  (Google button when `VITE_GOOGLE_CLIENT_ID` set; demo + paste-token paths work),
  no cross-surface CSS bleed, and a representative live/demo call returns.

There is no lint/test CI for these three apps today (only `api.yml` / `app.yml`),
and no deploy config — so the merge is self-contained; nothing external breaks. A
follow-up could add a `frontend.yml` build-check workflow, but that is out of scope
here.

## Out of scope

- `emails/` and `styleguide/` (static HTML, no build).
- A unified cross-surface sign-in (see Non-goal).
- Adding CI / deploy configuration for the merged app.
- Any change to the FastAPI backend or the Flutter `app/`.
