# Employers self-serve sign-up flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the employers surface's fake "Demo Data" sign-in mode with a real self-serve path: sign in with Google, and if you're brand-new (no employer yet), create your company and land straight on the job composer to post your first role free.

**Architecture:** The backend already supports this fully (`POST /v1/employers` auto-flips `APPLICANT → RECRUITER`); only the frontend needs new plumbing. Adds one new page (`Onboarding.tsx`), one new client method (`createEmployer`), one new shared session-store method (`refreshIdentity`, so the just-flipped role is visible without a fresh sign-in), and a tiny shared `landingFor(role)` helper so the sign-in redirect and the route guard's redirect can't drift apart. Demo mode is deleted outright from `employers/` only — console's own demo mode is untouched.

**Tech Stack:** React 18, react-router-dom v6, TypeScript, Vite. No new dependencies.

## Global Constraints

- `npm run build` (`tsc -b && vite build`, from `frontend/`) must stay clean after every task.
- No backend changes — `POST /v1/employers` (`api/src/jobify_api/routes/employers/core.py`) already does everything needed: creates the employer, links the caller as owner, flips role, no admin/invite step.
- No changes to console (`sites/console/**`) — its own demo mode, session, and sign-in are untouched.
- No changes to the Flutter app (`app/`).
- Follow the existing repo convention of NOT writing multi-line doc comments — one-line comments only where the *why* isn't obvious from the code.
- This flow cannot be exercised against demo fixtures (demo mode is what's being removed) — the final task's manual verification requires the real backend (`uv run --env-file=.env uvicorn jobify_api.main:app --reload` or equivalent, per `api/README.md`) running and reachable at the configured API base URL.

---

## Task 1: Add `EmployerCreate` type to `employers/api/types.ts`

**Files:**
- Modify: `frontend/src/sites/employers/api/types.ts`

**Interfaces:**
- Produces: `EmployerCreate` — Task 2's `EmployerClient.createEmployer()` and Task 6's `Onboarding.tsx` both use this exact type.

- [ ] **Step 1: Add the type**

In `frontend/src/sites/employers/api/types.ts`, insert this immediately before the existing `export interface EmployerRead {` block:

```ts
export interface EmployerCreate {
  name: string;
  gst?: string | null;
}

```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors (nothing imports the new type yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/api/types.ts
git commit -m "feat(frontend): add EmployerCreate type for the self-serve sign-up flow"
```

---

## Task 2: Add `createEmployer()` to `EmployerClient`

**Files:**
- Modify: `frontend/src/sites/employers/api/client.ts`

**Interfaces:**
- Consumes: `EmployerCreate` (Task 1).
- Produces: `EmployerClient.createEmployer(payload: EmployerCreate): Promise<EmployerRead>` — Task 6's `Onboarding.tsx` calls this exact method.

- [ ] **Step 1: Add the import**

In `frontend/src/sites/employers/api/client.ts`, change:

```ts
import type {
  ApplicantsOfJobPage,
  EmployerRead,
  InviteRead,
  JobCreate,
  JobPatch,
  JobRead,
  MeResponse,
  MemberRead,
  RecruiterJobsPage,
} from "./types";
```

to:

```ts
import type {
  ApplicantsOfJobPage,
  EmployerCreate,
  EmployerRead,
  InviteRead,
  JobCreate,
  JobPatch,
  JobRead,
  MeResponse,
  MemberRead,
  RecruiterJobsPage,
} from "./types";
```

- [ ] **Step 2: Add the interface method**

Change:

```ts
  myEmployers(): Promise<EmployerRead[]>;
  listMembers(employerId: string): Promise<MemberRead[]>;
```

to:

```ts
  myEmployers(): Promise<EmployerRead[]>;
  createEmployer(payload: EmployerCreate): Promise<EmployerRead>;
  listMembers(employerId: string): Promise<MemberRead[]>;
```

- [ ] **Step 3: Add the implementation**

Change:

```ts
  myEmployers(): Promise<EmployerRead[]> {
    return this.request("GET", "/v1/employers/me");
  }

  listMembers(employerId: string): Promise<MemberRead[]> {
```

to:

```ts
  myEmployers(): Promise<EmployerRead[]> {
    return this.request("GET", "/v1/employers/me");
  }

  createEmployer(payload: EmployerCreate): Promise<EmployerRead> {
    return this.request("POST", "/v1/employers", payload);
  }

  listMembers(employerId: string): Promise<MemberRead[]> {
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sites/employers/api/client.ts
git commit -m "feat(frontend): add EmployerClient.createEmployer (POST /v1/employers)"
```

---

## Task 3: Make `makeDemo` optional and add `refreshIdentity` to the shared session factory

**Files:**
- Modify: `frontend/src/shared/session/createSession.tsx`

**Interfaces:**
- Produces: `SessionStore.refreshIdentity(): Promise<TIdentity>` — Task 6's `Onboarding.tsx` calls this after creating the employer, so the session's cached role reflects `recruiter` without a fresh sign-in. `config.makeDemo` becomes optional — Task 4's `employers/session.tsx` stops supplying it; console's `session.tsx` (unchanged) keeps supplying it, so console's behavior is identical to before.

This file is shared by both `console/session.tsx` and `employers/session.tsx` — console's usage must keep working unchanged.

- [ ] **Step 1: Make `makeDemo` optional in the config type**

Change:

```ts
export function createSession<TClient extends { me: () => Promise<TIdentity> }, TIdentity>(config: {
  makeLive: (store: TokenStore, onSignOut: () => void) => TClient;
  makeDemo: (role?: string) => TClient;
}) {
```

to:

```ts
export function createSession<TClient extends { me: () => Promise<TIdentity> }, TIdentity>(config: {
  makeLive: (store: TokenStore, onSignOut: () => void) => TClient;
  makeDemo?: (role?: string) => TClient;
}) {
```

- [ ] **Step 2: Add `refreshIdentity` to the `SessionStore` interface**

Change:

```ts
  interface SessionStore {
    session: Session | null;
    /** True when the last session ended via an expired/invalid token, not a sign-out. */
    expired: boolean;
    connectLive: (baseUrl: string, token: string) => Promise<TIdentity>;
    connectGoogle: (idToken: string, baseUrl: string) => Promise<TIdentity>;
    connectDemo: (role?: string) => Promise<TIdentity>;
    signOut: () => void;
  }
```

to:

```ts
  interface SessionStore {
    session: Session | null;
    /** True when the last session ended via an expired/invalid token, not a sign-out. */
    expired: boolean;
    connectLive: (baseUrl: string, token: string) => Promise<TIdentity>;
    connectGoogle: (idToken: string, baseUrl: string) => Promise<TIdentity>;
    connectDemo: (role?: string) => Promise<TIdentity>;
    /** Re-fetches identity on the CURRENT client (no new client, no new token) —
     *  for when a mutation flips the caller's role server-side mid-session. */
    refreshIdentity: () => Promise<TIdentity>;
    signOut: () => void;
  }
```

- [ ] **Step 3: Add the `refreshIdentity` callback in `SessionProvider`**

Change:

```ts
    const store = useMemo<SessionStore>(
      () => ({
        session,
        expired,
        connectLive,
        connectGoogle,
        connectDemo: (role?: string) => connect(config.makeDemo(role)),
        signOut: () => {
          setSession(null);
          setExpired(false);
        },
      }),
      [session, expired, connect, connectLive, connectGoogle],
    );
```

to:

```ts
    const refreshIdentity = useCallback(async () => {
      if (!session) throw new Error("refreshIdentity called without an active session");
      const identity = await session.client.me();
      setSession((s) => (s ? { ...s, identity } : s));
      return identity;
    }, [session]);

    const store = useMemo<SessionStore>(
      () => ({
        session,
        expired,
        connectLive,
        connectGoogle,
        connectDemo: (role?: string) => {
          if (!config.makeDemo) throw new Error("Demo mode is not available on this surface");
          return connect(config.makeDemo(role));
        },
        refreshIdentity,
        signOut: () => {
          setSession(null);
          setExpired(false);
        },
      }),
      [session, expired, connect, connectLive, connectGoogle, refreshIdentity],
    );
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors — `console/session.tsx` still supplies `makeDemo`, so console is unaffected; `employers/session.tsx` (not yet updated — that's Task 4) still supplies `makeDemo` too at this point, so this task alone introduces no errors anywhere.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/session/createSession.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): make createSession's makeDemo optional, add refreshIdentity

Demo mode becomes opt-in per surface (console keeps it, employers will
drop it in the next commit). refreshIdentity re-fetches /v1/me on the
existing client so a mid-session role flip (e.g. creating an employer)
is visible without a fresh sign-in.
EOF
)"
```

---

## Task 4: Retire demo mode from the employers surface

**Files:**
- Modify: `frontend/src/sites/employers/session.tsx`
- Delete: `frontend/src/sites/employers/api/demo.ts`

**Interfaces:**
- Consumes: the now-optional `makeDemo` config (Task 3).
- Produces: `employers/session.tsx` no longer imports or references `DemoClient`. Nothing in `employers/` references `employers/api/demo.ts` after this task — verified by Step 3's grep.

- [ ] **Step 1: Replace `employers/session.tsx`**

Replace the entire file with:

```tsx
import { createSession } from "../../shared/session/createSession";
import { HttpClient } from "./api/client";
import type { EmployerClient } from "./api/client";
import type { MeResponse } from "./api/types";

export const { SessionProvider, useSessionStore, useSession } = createSession<EmployerClient, MeResponse>({
  makeLive: (store, onSignOut) => new HttpClient(store, onSignOut),
});
```

- [ ] **Step 2: Delete `employers/api/demo.ts`**

```bash
git rm frontend/src/sites/employers/api/demo.ts
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors. `connectDemo` stays in the `SessionStore` interface with its existing signature (Task 3 only changed its runtime behavior when `config.makeDemo` is absent), so `SignIn.tsx`'s still-present demo toggle continues to type-check — it would throw at runtime if actually clicked in this transient state between commits, but that UI is removed in Task 7 before anyone would reach it live. No errors should reference the deleted `demo.ts` file (confirms nothing else in `employers/` imports it).

Run: `grep -rn "api/demo\|DemoClient" frontend/src/sites/employers`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src/sites/employers/session.tsx frontend/src/sites/employers/api/demo.ts
git commit -m "$(cat <<'EOF'
refactor(frontend): retire demo mode from the employers surface

Demo Data was a stand-in for trying the product before signing up;
that's now the real self-serve sign-up flow (this branch). Console's
own demo mode is untouched — createSession's makeDemo is per-surface
opt-in as of the previous commit.
EOF
)"
```

---

## Task 5: Create the shared `landingFor` helper

**Files:**
- Create: `frontend/src/sites/employers/landing.ts`

**Interfaces:**
- Produces: `landingFor(role: string): string` — Task 7's `SignIn.tsx` (post-sign-in redirect) and Task 8's `EmployersRoutes.tsx` (`RequireRecruiter`'s redirect target for an already-signed-in non-recruiter) both import this exact function, so the two call sites can't drift on what a non-recruiter role should see.

- [ ] **Step 1: Create the file**

```ts
/** Where a signed-in employers-surface user should land, based on role. Used
 *  both right after sign-in and as RequireRecruiter's redirect target — kept
 *  as one function so the two call sites can't drift on what a non-recruiter
 *  role should see. */
export function landingFor(role: string): string {
  if (role === "recruiter") return "/employers/dashboard";
  if (role === "applicant") return "/employers/onboarding";
  return "/employers/no-access";
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors (this new file compiles standalone; nothing imports it yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/landing.ts
git commit -m "feat(frontend): add employers/landing.ts — shared post-auth redirect logic"
```

---

## Task 6: Create `employers/pages/Onboarding.tsx`

**Files:**
- Create: `frontend/src/sites/employers/pages/Onboarding.tsx`

**Interfaces:**
- Consumes: `EmployerClient.createEmployer` (Task 2), `SessionStore.refreshIdentity` (Task 3), `ErrorNotice`/`Field` (`employers/components/bits.tsx`, unchanged), `ApiError`/`errorMessage` (`employers/api/client.ts`, unchanged).
- Produces: `Onboarding` component — Task 8's `EmployersRoutes.tsx` imports this exact name from `"./pages/Onboarding"`.

Renders inside the existing `Shell`-wrapped `.content` area (same as `Settings.tsx`/`NoAccess`) — no new CSS needed; `.headline`/`.panel`/`.panel-head`/`.panel-body`/`.field` already exist in `employers/styles/dashboard.css`.

- [ ] **Step 1: Create the file**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import { ErrorNotice, Field } from "../components/bits";
import { useSession, useSessionStore } from "../session";

/** First-run setup for a signed-in user whose role is still "applicant" (see
 *  landingFor.ts, which routes them here instead of /no-access). Creating an
 *  employer flips APPLICANT -> RECRUITER server-side; refreshIdentity() then
 *  re-fetches /v1/me so the very next navigation is admitted as a recruiter. */
export function Onboarding() {
  const { identity, client } = useSession();
  const { refreshIdentity } = useSessionStore();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [gst, setGst] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function asMessage(e: unknown): string {
    if (e instanceof ApiError && e.status === 409) {
      return "That company name is already registered — try a slightly different name.";
    }
    return errorMessage(e);
  }

  const nameValid = name.trim().length >= 2 && name.trim().length <= 200;
  const gstValid = gst.trim().length === 0 || gst.trim().length === 15;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await client.createEmployer({ name: name.trim(), gst: gst.trim() || undefined });
      await refreshIdentity();
      navigate("/employers/jobs/new");
    } catch (e) {
      setError(asMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="headline">
        <h1>
          SET UP <span className="ghost">YOUR COMPANY</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            One step between {identity.email ?? "you"} and your first posting — it&apos;s free.
          </span>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 560 }}>
        <div className="panel-head">
          <span className="k">Company details</span>
        </div>
        <div className="panel-body">
          <Field label="Company name" hint="2–200 characters.">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Robotics" />
          </Field>
          <Field label="GST (optional)" hint="15 characters, if you have one — you can add this later too.">
            <input value={gst} onChange={(e) => setGst(e.target.value)} placeholder="29ABCDE1234F1Z5" />
          </Field>

          <ErrorNotice error={error} />

          <button
            className="btn primary"
            onClick={submit}
            disabled={busy || !nameValid || !gstValid}
            style={{ marginTop: 12 }}
          >
            {busy ? "Setting up…" : "Create workspace & post your first role"}
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors (this new file compiles standalone; nothing imports it yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/pages/Onboarding.tsx
git commit -m "feat(frontend): add employers/pages/Onboarding — self-serve create-company form"
```

---

## Task 7: Update `employers/pages/SignIn.tsx` — remove demo mode, wire the new copy and redirect

**Files:**
- Modify: `frontend/src/sites/employers/pages/SignIn.tsx`

**Interfaces:**
- Consumes: `landingFor` (Task 5).
- Produces: `SignIn` component with the same export shape as before — no consumers need to change.

- [ ] **Step 1: Replace the entire file**

```tsx
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import { GoogleButton } from "../auth/GoogleButton";
import { ErrorNotice, Field, IstClock } from "../components/bits";
import { API_BASE_URL, GOOGLE_CLIENT_ID } from "../env";
import { landingFor } from "../landing";
import { useSessionStore } from "../session";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";

export function SignIn() {
  const { connectLive, connectGoogle, expired } = useSessionStore();
  const navigate = useNavigate();
  const [showManual, setShowManual] = useState(false);
  const [baseUrl, setBaseUrl] = useState(API_BASE_URL);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function asMessage(e: unknown): string {
    return e instanceof ApiError ? `${e.status || "network"}: ${e.detail}` : errorMessage(e);
  }

  async function connectManual() {
    setBusy(true);
    setError(null);
    try {
      const identity = await connectLive(baseUrl, token.trim());
      navigate(landingFor(identity.role));
    } catch (e) {
      setError(asMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const onGoogleCredential = useCallback(
    async (idToken: string) => {
      setBusy(true);
      setError(null);
      try {
        const identity = await connectGoogle(idToken, API_BASE_URL);
        navigate(landingFor(identity.role));
      } catch (e) {
        setError(asMessage(e));
      } finally {
        setBusy(false);
      }
    },
    [connectGoogle, navigate],
  );

  const onGoogleLoadError = useCallback((message: string) => setError(message), []);

  return (
    <div className="dash gate">
      <div className="gate-left">
        <div className="spread">
          <span className="k">jobify for employers</span>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <ThemeToggle />
            <IstClock />
          </div>
        </div>

        <img src="/jobify-mark.svg" alt="Jobify" className="gate-mark rise" />
        <h1 className="gate-title rise">
          EMPLOYER
          <span className="line2">WORKSPACE</span>
        </h1>

        <div className="stack">
          <p className="flavor rise" style={{ maxWidth: 520 }}>
            Post roles, review your ranked applicant stack, and manage your team — the job desk
            for hiring on Jobify.
          </p>
          <div className="gate-meta rise">
            <div className="cell">
              <span className="k">api</span>
              <span className="num">/v1 · problem+json</span>
            </div>
            <div className="cell">
              <span className="k">build</span>
              <span className="num">employers v0.1</span>
            </div>
          </div>
        </div>
      </div>

      <div className="gate-right">
        <div className="google-block rise">
          <span className="k">sign in</span>
          {GOOGLE_CLIENT_ID ? (
            <GoogleButton
              clientId={GOOGLE_CLIENT_ID}
              onCredential={onGoogleCredential}
              onLoadError={onGoogleLoadError}
            />
          ) : (
            <p className="dim google-hint">
              Set <code>VITE_GOOGLE_CLIENT_ID</code> to enable Google sign-in.
            </p>
          )}
          <p className="k google-note">
            New here? Sign in with Google and we&apos;ll walk you through setting up your company
            — your first posting is free. Already set up? Sign in the same way.
          </p>
        </div>

        {expired && !error && (
          <div className="notice rise">
            Your session ended — the access token expired or was rejected. Sign in with Google or
            paste a fresh token to continue.
          </div>
        )}

        <ErrorNotice error={error} />

        <button
          type="button"
          className="btn ghost sm rise"
          onClick={() => setShowManual((v) => !v)}
          style={{ marginTop: 18 }}
        >
          {showManual ? "Hide manual token entry" : "Paste an access token instead"}
        </button>

        {showManual && (
          <div className="rise" style={{ marginTop: 14 }}>
            <Field label="API base URL">
              <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </Field>
            <Field
              label="Access token (Bearer)"
              hint="Short-lived JWT from Google sign-in. Held in memory only — reload requires a fresh paste. The API must allow this origin in JOBIFY_CORS_ALLOW_ORIGINS."
            >
              <textarea
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="eyJhbGciOiJIUzI1NiIs…"
                spellCheck={false}
              />
            </Field>
            <button
              className="btn primary rise"
              onClick={connectManual}
              disabled={busy || !token.trim()}
            >
              {busy ? "Connecting…" : "Connect"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors. This was the last file in `employers/` still calling `connectDemo` (which type-checked fine throughout, since `connectDemo`'s signature never changed — only its runtime behavior when `makeDemo` is absent) — after this task nothing in `employers/` calls it at all.

Run: `grep -rn "connectDemo\|mode-tabs\|Demo data\|Enter demo workspace" frontend/src/sites/employers`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/pages/SignIn.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): remove demo mode from employers SignIn, wire landingFor

Google is the only primary path now; the manual paste-token option
stays as a de-emphasized secondary link (useful for testing against a
real backend without Google each time). Post-sign-in redirect now
goes through the shared landingFor(role) so a brand-new applicant
lands on /employers/onboarding instead of a no-access dead end.
EOF
)"
```

---

## Task 8: Wire `/employers/onboarding` into `EmployersRoutes.tsx`

**Files:**
- Modify: `frontend/src/sites/employers/EmployersRoutes.tsx`

**Interfaces:**
- Consumes: `Onboarding` (Task 6), `landingFor` (Task 5).
- Produces: `EmployersRoutes()` — same export shape as before.

- [ ] **Step 1: Add the imports**

Change:

```tsx
import { Dashboard } from "./pages/dashboard/Dashboard";
import { Jobs } from "./pages/dashboard/Jobs";
import { JobComposer } from "./pages/dashboard/JobComposer";
import { Applicants } from "./pages/dashboard/Applicants";
import { Team } from "./pages/dashboard/Team";
import { SessionProvider, useSessionStore } from "./session";
```

to:

```tsx
import { Dashboard } from "./pages/dashboard/Dashboard";
import { Jobs } from "./pages/dashboard/Jobs";
import { JobComposer } from "./pages/dashboard/JobComposer";
import { Applicants } from "./pages/dashboard/Applicants";
import { Team } from "./pages/dashboard/Team";
import { Onboarding } from "./pages/Onboarding";
import { landingFor } from "./landing";
import { SessionProvider, useSessionStore } from "./session";
```

- [ ] **Step 2: Update `RequireRecruiter` to redirect through `landingFor`**

Change:

```tsx
function RequireRecruiter() {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/employers/signin" replace />;
  if (session.identity.role !== "recruiter") {
    return <Navigate to="/employers/no-access" replace />;
  }
  return <Outlet />;
}
```

to:

```tsx
function RequireRecruiter() {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/employers/signin" replace />;
  if (session.identity.role !== "recruiter") {
    return <Navigate to={landingFor(session.identity.role)} replace />;
  }
  return <Outlet />;
}
```

- [ ] **Step 3: Add the onboarding route**

Change:

```tsx
          {/* Account & settings — any signed-in recruiter, not role-gated further. */}
          <Route path="/employers/settings" element={<Settings />} />
          <Route path="/employers/no-access" element={<NoAccess />} />
          <Route element={<RequireRecruiter />}>
```

to:

```tsx
          {/* Account & settings — any signed-in recruiter, not role-gated further. */}
          <Route path="/employers/settings" element={<Settings />} />
          <Route path="/employers/no-access" element={<NoAccess />} />
          <Route path="/employers/onboarding" element={<Onboarding />} />
          <Route element={<RequireRecruiter />}>
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors, project-wide.

Run: `npm run build 2>&1 | tail -20` (from `frontend/`)
Expected: `✓ built in ...` with no errors or warnings about unresolved imports.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sites/employers/EmployersRoutes.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): wire /employers/onboarding, route non-recruiters through landingFor

RequireRecruiter now sends an applicant (no employer yet) to
/employers/onboarding instead of /employers/no-access; any other
non-recruiter role (e.g. admin) still sees the no-access page.
EOF
)"
```

---

## Task 9: Final build + manual smoke test (requires a live backend)

**Files:** none (verification only)

This flow has no demo-mode fallback (that's what's being removed), so the only way to verify it end-to-end is against a real running API. If you don't have one available, do Steps 1–2 (static checks) and report the rest as not-yet-verified rather than guessing.

- [ ] **Step 1: Full typecheck + build**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...`, zero errors.

- [ ] **Step 2: Sweep for stray references**

```bash
grep -rn "connectDemo\|DemoClient\|api/demo\|Demo data\|Enter demo workspace" frontend/src/sites/employers
```
Expected: no output.

- [ ] **Step 3: Start the backend and frontend dev server**

Follow `api/README.md` to start the API against your local Postgres (needs `JOBIFY_GOOGLE_OAUTH_CLIENT_IDS` set to accept your Google client id, and `JOBIFY_JWT_SECRET` etc. per that README). Then:

```bash
cd frontend && npm run dev -- --port 5173
```

- [ ] **Step 4: New-user flow**

Open `http://localhost:5173/#/employers/signin`. Confirm:
- No "Demo Data" toggle or "Enter demo workspace" button anywhere on the page.
- Sign in with a Google account that has never signed into Jobify before (or, if you'd rather not use a real fresh Google account, use the "Paste an access token instead" link with a manually-minted JWT for a test user whose DB role is `applicant` and who owns no employer — see `api/README.md`'s seeding docs for how to mint one).
- Confirm you land on `/employers/onboarding`, not `/employers/no-access`.
- Submit the form with a valid company name (2–200 chars). Confirm you land on `/employers/jobs/new` with the new employer already selected in the composer's employer dropdown (no manual selection needed).
- Post a role. Confirm it appears in `/employers/jobs` and the `/employers/dashboard` tiles reflect it.

- [ ] **Step 5: Duplicate-name error**

On `/employers/onboarding` (a second applicant-role test account, or manually via the API), attempt to create an employer with a name that already exists. Confirm the page shows "That company name is already registered — try a slightly different name." rather than a raw `employer_name_taken` string.

- [ ] **Step 6: Admin edge case**

Sign in on `/employers/signin` with an admin-role account (paste-token, since Google sign-in always provisions as applicant for a new account). Confirm you land on `/employers/no-access` with its existing "This workspace is for recruiters" message — NOT the onboarding form.

- [ ] **Step 7: Existing recruiter still works**

Sign in with an account that's already a recruiter with an existing employer. Confirm you land directly on `/employers/dashboard`, exactly as before this change — the onboarding path is only for applicants with no employer yet.

- [ ] **Step 8: Stop the dev server, report results**

If every check in Steps 4–7 passes, the flow is functionally complete. If anything fails, treat it as a bug in the relevant task above (not a new task) — fix inline and re-run the affected smoke-test steps before committing.

- [ ] **Step 9: No commit for this task** (verification-only; nothing to stage).
