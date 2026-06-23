# Unify web/console/employers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the three repo-root React/Vite/TS apps (`web`, `console`, `employers`) into one Vite app under `frontend/`, with three route-prefixed surfaces under one `HashRouter` and a deduplicated shared transport/session/auth/env core.

**Architecture:** One `HashRouter` mounts three surfaces via React Router v6 **layout routes** (`/` web, `/employers/*`, `/console/*`). Each surface keeps its own pages, layout chrome, endpoint client, types, and CSS; the transport (`BaseHttpClient` + token refresh), the session-provider factory, env, and Google auth are shared. Sessions stay **independent per surface** (we share code, not session state). Routing uses absolute paths; web stays at root unchanged, console/employers get their nav literals prefixed.

**Tech Stack:** React 18.3, react-router-dom 6.28, Vite 6, TypeScript 5.6 (strict). No backend or Flutter changes.

## Global Constraints

- **No automated test suite exists for these apps** (no lint/test CI; only `api.yml`/`app.yml`). The per-task verification cycle is **`npm run build`** (= `tsc -b && vite build`) run from `frontend/`, plus the manual smoke checks each task lists. Treat a failing build as a failing test (red) and a clean build as green.
- **`HashRouter` only** — static bundle, no server rewrites. Routes live after `#`. Do not introduce `BrowserRouter`, Vite `base`, or router `basename`.
- **TypeScript strict + `noUnusedLocals` + `noUnusedParameters`** are on (inherited tsconfig). Every import must be used; remove dead imports as you port.
- **Surface independence is a non-goal to break:** do NOT unify live session state across surfaces. Each surface mounts its own `SessionProvider` instance from the shared factory.
- **Canonical reconciliations** (apply verbatim where the two copies diverged):
  - `ApiError` carries a 3rd `requestId?: string` arg (console's richer version).
  - `formatDetail` is the `loc`-aware 422 flattener (console's version).
  - `GoogleOAuthResponse.user.applicant_id` is `string | null` (web's correct version).
  - Session sign-out method is named **`signOut`** (web's name) everywhere.
- **Preserve load-bearing auth behavior verbatim:** single 401-recoverable slug `invalid_access_token`; single-flight refresh; `refreshInFlight = null` cleared in `.finally()` BEFORE awaiters resume; `/v1/auth/refresh` rotates and is never routed through `request()`. These mirror `app/`'s `RefreshOn401Interceptor`.
- **Dev port 5173.** One `.env` with `VITE_GOOGLE_CLIENT_ID` + `VITE_API_BASE_URL`.
- **Out of scope:** `emails/`, `styleguide/` (static, untouched); CI/deploy config; per-route SEO meta.

---

## File Structure (target)

```
frontend/
  index.html              # union of all three apps' fonts + favicon; generic title
  package.json            # one set of deps; dev on 5173
  vite.config.ts          # port 5173
  tsconfig.json           # copied verbatim from any app (all three identical)
  .env.example            # VITE_GOOGLE_CLIENT_ID, VITE_API_BASE_URL
  public/                 # union of web/console/employers public assets
  src/
    main.tsx              # one React root → <App/>
    App.tsx               # one <HashRouter> mounting the three surfaces' route fragments
    vite-env.d.ts
    shared/
      api/transport.ts        # TokenStore, ApiError, errorMessage, formatDetail, BaseHttpClient
      api/types.ts            # GoogleOAuthResponse (the shared auth envelope)
      session/createSession.tsx  # generic SessionProvider/useSession factory
      env.ts                  # GOOGLE_CLIENT_ID, API_BASE_URL
      auth/gsi.ts             # GIS loader + renderGoogleButton(theme)
      auth/GoogleSignInButton.tsx  # one button, theme + classNames props
    sites/
      web/        # mounted at "/"           (from web/src/*)
      employers/  # mounted at "/employers/*"(from employers/src/*)
      console/    # mounted at "/console/*"  (from console/src/*)
```

Each surface keeps thin shim files (`api/client.ts`, `session.tsx`, `env.ts`, `auth/GoogleSignInButton.tsx`) that re-export from `shared/` so its **page files need no import edits** (relative imports survive a whole-subtree `git mv`).

---

### Task 1: Scaffold `frontend/` shell

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/.env.example`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/vite-env.d.ts`
- Create: `frontend/public/` (copied assets)

**Interfaces:**
- Produces: a buildable empty app rendering a placeholder, so later tasks have a working `npm run build`. `App` (default-exported route shell) is replaced in Task 6.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "jobify-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^6.0.3"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Single unified web app. Live surfaces (web applicant + console) need this
// origin in the API's JOBIFY_CORS_ALLOW_ORIGINS. See frontend/README.md.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
```

- [ ] **Step 3: Create `frontend/tsconfig.json`** — copy verbatim from `web/tsconfig.json` (all three apps' tsconfigs are byte-identical):

```bash
cp web/tsconfig.json frontend/tsconfig.json
```

- [ ] **Step 4: Create `frontend/src/vite-env.d.ts`**

```ts
/// <reference types="vite/client" />
```

- [ ] **Step 5: Create `frontend/index.html`** — union of all three apps' font links; one favicon; generic title. (Per-surface `document.title` is set in Task 4/5/6 layout components.)

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Jobify</title>
    <meta
      name="description"
      content="Jobify is a placement platform that surfaces roles matched to your résumé — and tells you why each one fits."
    />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <!-- web fonts -->
    <link
      href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,900;1,9..144,400;1,9..144,500&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap"
      rel="stylesheet"
    />
    <!-- console fonts -->
    <link
      href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,500;12..96,700;12..96,800&family=Newsreader:ital,opsz,wght@1,6..72,400;1,6..72,500&family=Spline+Sans+Mono:wght@300;400;500;600&display=swap"
      rel="stylesheet"
    />
    <!-- employers fonts -->
    <link
      href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap"
      rel="stylesheet"
    />
    <link rel="icon" type="image/svg+xml" href="/jobify-logo.svg" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Consolidate `public/` assets** (union of all three; web/employers `jobify-logo.svg`, console `jobify-mark.svg`, plus any others):

```bash
mkdir -p frontend/public
cp -n web/public/* frontend/public/ 2>/dev/null || true
cp -n console/public/* frontend/public/ 2>/dev/null || true
cp -n employers/public/* frontend/public/ 2>/dev/null || true
ls frontend/public
```

Expected: `jobify-logo.svg` and `jobify-mark.svg` (at minimum) present.

- [ ] **Step 7: Create `frontend/.env.example`**

```bash
# Google Web OAuth client id (enables the Sign in with Google button).
VITE_GOOGLE_CLIENT_ID=
# API base for live token exchange + applicant/console calls.
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 8: Create `frontend/src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 9: Create a placeholder `frontend/src/App.tsx`** (replaced in Task 6):

```tsx
import { HashRouter, Routes, Route } from "react-router-dom";

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="*" element={<p style={{ padding: 24 }}>frontend scaffold OK</p>} />
      </Routes>
    </HashRouter>
  );
}
```

- [ ] **Step 10: Install and build**

Run:
```bash
cd frontend && npm install && npm run build
```
Expected: install succeeds; `tsc -b` no errors; `vite build` writes `frontend/dist/`. (`cd ..` when done.)

- [ ] **Step 11: Commit**

```bash
git add frontend/ && git commit -m "feat(frontend): scaffold unified web app shell"
```

---

### Task 2: Shared transport core

**Files:**
- Create: `frontend/src/shared/api/transport.ts`
- Create: `frontend/src/shared/api/types.ts`

**Interfaces:**
- Produces:
  - `class TokenStore(baseUrl: string, access: string, refresh: string | null)`
  - `class ApiError(status: number, detail: string, requestId?: string)`
  - `function errorMessage(e: unknown): string`
  - `function formatDetail(detail: unknown): string | null`
  - `class BaseHttpClient` with `readonly mode: "live"`, `constructor(store: TokenStore, onSignOut?: () => void)`, and `protected request<T>(method: string, path: string, body?: unknown, isRetry?: boolean): Promise<T>`
  - `interface GoogleOAuthResponse` (in `types.ts`)
- Consumes: nothing (leaf module).

- [ ] **Step 1: Create `frontend/src/shared/api/transport.ts`**

```ts
/** RFC 7807 problem+json error; `detail` is the API's user-visible slug/message.
 *  `requestId` is the X-Request-Id correlation handle when the response carried one. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly requestId?: string,
  ) {
    super(detail);
  }
}

/** Turn any caught value into a display string — used in every page's catch. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return String(e);
}

/**
 * Render an RFC 7807 problem `detail` as one human string. Two shapes arrive:
 *  - HTTPException → `detail` is already a string.
 *  - 422 validation → FastAPI default `{detail: [{loc, msg, type}, ...]}`, flattened
 *    `loc.msg`-style so the UI never shows raw JSON.
 */
export function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === "object" && "msg" in d) {
          const item = d as { loc?: unknown; msg?: unknown };
          const loc = Array.isArray(item.loc) ? item.loc.filter((s) => s !== "body").join(".") : "";
          const msg = String(item.msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return JSON.stringify(d);
      })
      .join("; ");
  }
  return null;
}

/** The single 401 slug a token refresh can recover from. Every other 401
 * (`missing_bearer_token`, `user_not_found`, `user_suspended`, an unknown future
 * slug) is structurally unrecoverable → sign out. Mirrors app/'s
 * RefreshOn401Interceptor, which only refreshes on `invalid_access_token`. */
const INVALID_ACCESS_TOKEN = "invalid_access_token";

/** Mutable holder for the live session's tokens. The refresh-on-401 path mutates
 * `access` (and rotates `refresh`) in place, so every method picks up the new
 * access token without the client being rebuilt. `refresh` is null on the
 * paste-token path. Mirrors app/'s AccessTokenHolder. */
export class TokenStore {
  constructor(
    readonly baseUrl: string,
    public access: string,
    public refresh: string | null,
  ) {}
}

/** Shared bearer transport with the 401 single-flight refresh ladder. Surface
 * clients EXTEND this and implement their typed endpoint methods by calling
 * `this.request(...)`. */
export class BaseHttpClient {
  readonly mode = "live" as const;

  /** In-flight single-flight refresh — concurrent 401s collapse onto one
   * /v1/auth/refresh call rather than each rotating the token separately. */
  private refreshInFlight: Promise<string> | null = null;

  constructor(
    protected readonly store: TokenStore,
    /** Invoked when the session is unrecoverable (refresh failed, or a
     * non-refreshable 401) so the session layer can sign the user out. */
    private readonly onSignOut?: () => void,
  ) {}

  protected async request<T>(method: string, path: string, body?: unknown, isRetry = false): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.store.baseUrl}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${this.store.access}`,
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new ApiError(0, `network error — is the API reachable at ${this.store.baseUrl}?`);
    }

    // 401 ladder: only `invalid_access_token`, with a refresh token, on the FIRST
    // attempt is recoverable — refresh once then replay the original request once.
    if (res.status === 401) {
      const requestId = res.headers.get("X-Request-Id") ?? undefined;
      const detail = await this.readDetail(res);
      const recoverable = detail === INVALID_ACCESS_TOKEN && this.store.refresh !== null && !isRetry;
      if (recoverable) {
        try {
          await this.refreshSingleFlight();
        } catch {
          this.onSignOut?.();
          throw new ApiError(401, detail, requestId);
        }
        return this.request<T>(method, path, body, true);
      }
      this.onSignOut?.();
      throw new ApiError(401, detail, requestId);
    }

    if (!res.ok) {
      throw new ApiError(res.status, await this.readDetail(res), res.headers.get("X-Request-Id") ?? undefined);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  /** RFC 7807 problem+json `detail` (or `title`) as a display string. */
  private async readDetail(res: Response): Promise<string> {
    try {
      const problem = (await res.json()) as { detail?: unknown; title?: unknown };
      return formatDetail(problem.detail) ?? formatDetail(problem.title) ?? `HTTP ${res.status}`;
    } catch {
      return `HTTP ${res.status}`;
    }
  }

  /** Single-flight refresh. Concurrent 401s share one in-flight promise; the slot
   * is cleared BEFORE the promise settles (awaiters already hold it). Mirrors
   * app/'s `_inFlight = null` BEFORE `complete()` ordering. */
  private refreshSingleFlight(): Promise<string> {
    if (this.refreshInFlight) return this.refreshInFlight;
    const inFlight = this.doRefresh().finally(() => {
      this.refreshInFlight = null;
    });
    this.refreshInFlight = inFlight;
    return inFlight;
  }

  /** POST /v1/auth/refresh — rotates the refresh token on every call. A plain
   * fetch (never routed through request()) so a 401 here can't recurse. */
  private async doRefresh(): Promise<string> {
    if (this.store.refresh === null) throw new ApiError(401, "no_refresh_token");
    let res: Response;
    try {
      res = await fetch(`${this.store.baseUrl}/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.store.refresh }),
      });
    } catch {
      throw new ApiError(0, "network error during token refresh");
    }
    if (!res.ok) throw new ApiError(res.status, "token refresh failed");
    const data = (await res.json()) as { access_token: string; refresh_token: string };
    this.store.access = data.access_token;
    this.store.refresh = data.refresh_token; // rotation — persist the new refresh token
    return data.access_token;
  }
}
```

- [ ] **Step 2: Create `frontend/src/shared/api/types.ts`**

```ts
/** Wire shape of `POST /v1/auth/oauth/google` (the FastAPI token envelope). Shared
 *  by the session factory across surfaces. `applicant_id` is null for recruiter/admin. */
export interface GoogleOAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    email: string;
    role: string;
    applicant_id: string | null;
    is_new_user: boolean;
  };
}
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: no errors (modules typecheck even though nothing imports them yet). `cd ..`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/shared && git commit -m "feat(frontend): shared transport core (BaseHttpClient, ApiError)"
```

---

### Task 3: Shared session factory, env, and auth

**Files:**
- Create: `frontend/src/shared/session/createSession.tsx`
- Create: `frontend/src/shared/env.ts`
- Create: `frontend/src/shared/auth/gsi.ts`
- Create: `frontend/src/shared/auth/GoogleSignInButton.tsx`

**Interfaces:**
- Consumes: `TokenStore`, `ApiError` from `../api/transport`; `GoogleOAuthResponse` from `../api/types`.
- Produces:
  - `createSession<TClient extends { me: () => Promise<TIdentity> }, TIdentity>(config: { makeLive: (store: TokenStore, onSignOut: () => void) => TClient; makeDemo: (role?: string) => TClient }) => { SessionProvider, useSessionStore, useSession }`
    - `useSessionStore()` returns `{ session: { client: TClient; identity: TIdentity } | null; expired: boolean; connectLive(baseUrl, token); connectGoogle(idToken, baseUrl); connectDemo(role?); signOut() }`
    - `useSession()` returns `{ client: TClient; identity: TIdentity }`
  - `GOOGLE_CLIENT_ID: string | undefined`, `API_BASE_URL: string` (env.ts)
  - `renderGoogleButton(container, clientId, onCredential, theme?)` (gsi.ts)
  - `GoogleSignInButton` component (props: `clientId`, `onCredential`, `theme?`, `onLoadError?`)

- [ ] **Step 1: Create `frontend/src/shared/env.ts`**

```ts
/**
 * Build-time config from Vite env (`VITE_*`, baked at `vite build`).
 * `GOOGLE_CLIENT_ID` is optional — when unset the sign-in gate hides the Google
 * button (demo + paste-token still work).
 */

/** Google **Web** OAuth client id; `undefined` ⇒ Google sign-in disabled. */
export const GOOGLE_CLIENT_ID: string | undefined =
  import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim() || undefined;

/** API base for the Google exchange + live calls; defaults to the local dev API. */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000";
```

- [ ] **Step 2: Create `frontend/src/shared/auth/gsi.ts`** (reconciled loader + themed render):

```ts
/**
 * Google Identity Services (GIS) web helper. The imperative `signIn()` can't
 * return an ID token on web, so we `initialize({ callback })` + `renderButton`;
 * the callback yields `response.credential` (the Google ID token), exchanged
 * server-side for an access token. Minimal ambient types only — no `@types/...`.
 */

interface CredentialResponse {
  /** The Google ID token (JWT) — POST to /v1/auth/oauth/google. */
  credential: string;
}

interface GsiButtonConfiguration {
  theme?: "outline" | "filled_blue" | "filled_black";
  size?: "small" | "medium" | "large";
  text?: "signin_with" | "signup_with" | "continue_with" | "signin";
  shape?: "rectangular" | "pill" | "circle" | "square";
  logo_alignment?: "left" | "center";
  width?: number;
}

interface GsiIdConfiguration {
  client_id: string;
  callback: (response: CredentialResponse) => void;
  auto_select?: boolean;
  use_fedcm_for_prompt?: boolean;
}

interface GoogleAccountsId {
  initialize(config: GsiIdConfiguration): void;
  renderButton(parent: HTMLElement, options: GsiButtonConfiguration): void;
  cancel(): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } };
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";
let loadPromise: Promise<GoogleAccountsId> | null = null;

/** Inject the GIS SDK once (idempotent) and resolve with `google.accounts.id`. */
export function loadGsi(): Promise<GoogleAccountsId> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<GoogleAccountsId>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    const onReady = () => {
      const id = window.google?.accounts?.id;
      if (id) resolve(id);
      else reject(new Error("Google Identity Services loaded but window.google.accounts.id is missing"));
    };
    const onFail = () => {
      loadPromise = null; // allow a retry after a transient network failure
      reject(new Error("failed to load Google Identity Services"));
    };
    if (existing) {
      existing.addEventListener("load", onReady, { once: true });
      existing.addEventListener("error", onFail, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", onReady, { once: true });
    script.addEventListener("error", onFail, { once: true });
    document.head.appendChild(script);
  });
  return loadPromise;
}

/** Initialize GIS for `clientId` and render the official button into `container`.
 *  `onCredential` fires with the Google ID token on a successful sign-in. */
export async function renderGoogleButton(
  container: HTMLElement,
  clientId: string,
  onCredential: (idToken: string) => void,
  theme: GsiButtonConfiguration["theme"] = "outline",
): Promise<void> {
  const id = await loadGsi();
  id.initialize({
    client_id: clientId,
    callback: (response) => onCredential(response.credential),
    use_fedcm_for_prompt: true,
  });
  id.renderButton(container, {
    theme,
    size: "large",
    text: "continue_with",
    shape: "rectangular",
    logo_alignment: "left",
    width: 320,
  });
}
```

- [ ] **Step 3: Create `frontend/src/shared/auth/GoogleSignInButton.tsx`** (one button; `theme` + optional `onLoadError`; unified class names `gsi`/`gsi-btn`/`gsi-hint`):

```tsx
import { useEffect, useRef, useState } from "react";
import { renderGoogleButton } from "./gsi";

/**
 * Renders the official GIS button and hands the Google ID token to `onCredential`.
 * While the SDK loads (or if it fails) a muted status line stands in. `theme`
 * selects the Google button style per surface ("outline" web, "filled_black" console).
 */
export function GoogleSignInButton({
  clientId,
  onCredential,
  theme = "outline",
  onLoadError,
}: {
  clientId: string;
  onCredential: (idToken: string) => void;
  theme?: "outline" | "filled_blue" | "filled_black";
  onLoadError?: (message: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  // Keep the latest callback without re-running the effect (which would re-init GIS).
  const cbRef = useRef(onCredential);
  cbRef.current = onCredential;
  const errRef = useRef(onLoadError);
  errRef.current = onLoadError;

  useEffect(() => {
    let cancelled = false;
    const el = containerRef.current;
    if (!el) return;
    renderGoogleButton(el, clientId, (idToken) => cbRef.current(idToken), theme)
      .then(() => {
        if (!cancelled) setStatus("ready");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setStatus("error");
        errRef.current?.(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [clientId, theme]);

  return (
    <div className="gsi">
      <div ref={containerRef} className="gsi-btn" aria-busy={status === "loading"} />
      {status === "loading" && <span className="gsi-hint dim">Loading Google sign-in…</span>}
      {status === "error" && (
        <span className="gsi-hint err">Couldn’t load Google sign-in — check your connection.</span>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/shared/session/createSession.tsx`**

```tsx
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, TokenStore } from "../api/transport";
import type { GoogleOAuthResponse } from "../api/types";

function problemDetail(body: unknown, status: number): string {
  if (body && typeof body === "object") {
    const p = body as { detail?: unknown; title?: unknown };
    if (typeof p.detail === "string") return p.detail;
    if (typeof p.title === "string") return p.title;
  }
  return `HTTP ${status}`;
}

/**
 * Build a per-surface session context. `TClient` is the surface's API client
 * (must expose `me(): Promise<TIdentity>`); `TIdentity` is its `/v1/me` shape.
 * Sessions are independent per surface — each surface calls this once and mounts
 * its own <SessionProvider>.
 */
export function createSession<TClient extends { me: () => Promise<TIdentity> }, TIdentity>(config: {
  makeLive: (store: TokenStore, onSignOut: () => void) => TClient;
  makeDemo: (role?: string) => TClient;
}) {
  interface Session {
    client: TClient;
    identity: TIdentity;
  }
  interface SessionStore {
    session: Session | null;
    /** True when the last session ended via an expired/invalid token, not a sign-out. */
    expired: boolean;
    connectLive: (baseUrl: string, token: string) => Promise<TIdentity>;
    connectGoogle: (idToken: string, baseUrl: string) => Promise<TIdentity>;
    connectDemo: (role?: string) => Promise<TIdentity>;
    signOut: () => void;
  }

  const SessionContext = createContext<SessionStore | null>(null);

  function SessionProvider({ children }: { children: ReactNode }) {
    const [session, setSession] = useState<Session | null>(null);
    const [expired, setExpired] = useState(false);

    const connect = useCallback(async (client: TClient) => {
      const identity = await client.me();
      setSession({ client, identity });
      setExpired(false);
      return identity;
    }, []);

    // A live client over a token store. On an unrecoverable 401 the session clears
    // and routes back to the gate with an "expired" notice.
    const makeLiveClient = useCallback(
      (store: TokenStore) =>
        config.makeLive(store, () => {
          setSession(null);
          setExpired(true);
        }),
      [],
    );

    const connectLive = useCallback(
      // Paste-token path has no refresh token → a 401 just signs out (no rotation).
      (baseUrl: string, token: string) =>
        connect(makeLiveClient(new TokenStore(baseUrl.replace(/\/$/, ""), token, null))),
      [connect, makeLiveClient],
    );

    const connectGoogle = useCallback(
      async (idToken: string, baseUrl: string) => {
        const base = baseUrl.replace(/\/$/, "");
        let res: Response;
        try {
          res = await fetch(`${base}/v1/auth/oauth/google`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: idToken }),
          });
        } catch {
          throw new ApiError(0, `network error — is the API reachable at ${base}?`);
        }
        if (!res.ok) {
          let body: unknown = null;
          try {
            body = await res.json();
          } catch {
            /* non-JSON problem body — fall back to the status */
          }
          throw new ApiError(res.status, problemDetail(body, res.status), res.headers.get("X-Request-Id") ?? undefined);
        }
        const data = (await res.json()) as GoogleOAuthResponse;
        // Google sessions carry the refresh token, so a mid-session access-token
        // expiry refreshes transparently instead of bouncing to the gate.
        return connect(makeLiveClient(new TokenStore(base, data.access_token, data.refresh_token)));
      },
      [connect, makeLiveClient],
    );

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

    return <SessionContext.Provider value={store}>{children}</SessionContext.Provider>;
  }

  function useSessionStore(): SessionStore {
    const store = useContext(SessionContext);
    if (!store) throw new Error("useSessionStore outside SessionProvider");
    return store;
  }

  function useSession(): Session {
    const { session } = useSessionStore();
    if (!session) throw new Error("useSession without an active session");
    return session;
  }

  return { SessionProvider, useSessionStore, useSession };
}
```

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: no errors. `cd ..`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/shared && git commit -m "feat(frontend): shared session factory, env, and Google auth"
```

---

### Task 4: Port the web surface (mounted at `/`)

The whole `web/src` subtree moves under `frontend/src/sites/web/`; intra-subtree relative imports survive the move. Only the four shim files (`api/client.ts`, `session.tsx`, `env.ts`, `auth/GoogleSignInButton.tsx`) are rewritten to use `shared/`. **Web stays at root — no route/nav literal changes.**

**Files:**
- Move: `web/src/*` → `frontend/src/sites/web/*`
- Rewrite: `frontend/src/sites/web/api/client.ts`, `.../session.tsx`, `.../env.ts`, `.../auth/GoogleSignInButton.tsx`
- Create: `frontend/src/sites/web/WebRoutes.tsx`
- Delete (after move): `frontend/src/sites/web/App.tsx`, `frontend/src/sites/web/main.tsx`

**Interfaces:**
- Consumes: `BaseHttpClient`, `ApiError`, `errorMessage`, `TokenStore` from `shared/api/transport`; `createSession` from `shared/session/createSession`; `GoogleSignInButton` from `shared/auth/GoogleSignInButton`; `GOOGLE_CLIENT_ID`/`API_BASE_URL` from `shared/env`.
- Produces: `WebRoutes(): JSX` — a `<Route>` fragment (web's routes wrapped in a session+CSS layout) for the top `App.tsx`.

- [ ] **Step 1: Move the subtree**

```bash
mkdir -p frontend/src/sites
git mv web/src frontend/src/sites/web
```

- [ ] **Step 2: Delete the now-redundant per-app entry files**

```bash
git rm frontend/src/sites/web/main.tsx
```
(Keep `App.tsx` for now; it becomes `WebRoutes.tsx` in Step 7. `vite-env.d.ts` is redundant with the root one — remove it: `git rm frontend/src/sites/web/vite-env.d.ts`.)

- [ ] **Step 3: Rewrite `frontend/src/sites/web/env.ts`** to a shim:

```ts
export { API_BASE_URL, GOOGLE_CLIENT_ID } from "../../shared/env";
```

- [ ] **Step 4: Rewrite `frontend/src/sites/web/auth/GoogleSignInButton.tsx`** to a shim:

```ts
export { GoogleSignInButton } from "../../../shared/auth/GoogleSignInButton";
```
Then delete the now-unused `frontend/src/sites/web/auth/gsi.ts`:
```bash
git rm frontend/src/sites/web/auth/gsi.ts
```

- [ ] **Step 5: Rewrite `frontend/src/sites/web/api/client.ts`** — re-export transport pieces from shared, keep the `JobifyClient` interface, and make `HttpClient` extend `BaseHttpClient`. Replace the entire file with:

```ts
import { BaseHttpClient } from "../../../shared/api/transport";
import type {
  AcceptResult,
  ApplicationListResponse,
  ApplicationRead,
  ConsentRead,
  FeedResponse,
  JobDetailResponse,
  MeResponse,
  MyInviteRead,
  NotificationListResponse,
  NotificationRead,
  SavedJobListResponse,
  SavedJobRead,
} from "./types";

// Re-export the shared transport surface so existing page imports
// (`import { errorMessage, ApiError, TokenStore } from "../api/client"`) keep working.
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";

/** One interface, two impls: HttpClient (live /v1) and DemoClient (fixtures). */
export interface JobifyClient {
  readonly mode: "live" | "demo";
  me(): Promise<MeResponse>;
  feed(cursor?: string): Promise<FeedResponse>;
  job(jobId: string): Promise<JobDetailResponse>;
  apply(jobId: string): Promise<ApplicationRead>;
  withdraw(applicationId: string): Promise<ApplicationRead>;
  save(jobId: string): Promise<SavedJobRead>;
  unsave(jobId: string): Promise<void>;
  applications(cursor?: string): Promise<ApplicationListResponse>;
  saved(cursor?: string): Promise<SavedJobListResponse>;
  getConsents(): Promise<ConsentRead[]>;
  setConsent(scope: string, granted: boolean): Promise<ConsentRead>;
  dsrExport(): Promise<unknown>;
  dsrDelete(): Promise<unknown>;
  notifications(cursor?: string): Promise<NotificationListResponse>;
  markNotificationRead(notificationId: string): Promise<NotificationRead>;
  myInvites(): Promise<MyInviteRead[]>;
  acceptInvite(inviteId: string): Promise<AcceptResult>;
  declineInvite(inviteId: string): Promise<AcceptResult>;
}

export class HttpClient extends BaseHttpClient implements JobifyClient {
  me() {
    return this.request<MeResponse>("GET", "/v1/me");
  }
  feed(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<FeedResponse>("GET", `/v1/feed${qs}`);
  }
  job(jobId: string) {
    return this.request<JobDetailResponse>("GET", `/v1/jobs/${jobId}`);
  }
  apply(jobId: string) {
    return this.request<ApplicationRead>("POST", `/v1/jobs/${jobId}/apply`, { source: "web" });
  }
  withdraw(applicationId: string) {
    return this.request<ApplicationRead>("PATCH", `/v1/applications/${applicationId}`, { status: "withdrawn" });
  }
  save(jobId: string) {
    return this.request<SavedJobRead>("POST", `/v1/jobs/${jobId}/save`);
  }
  unsave(jobId: string) {
    return this.request<void>("DELETE", `/v1/jobs/${jobId}/save`);
  }
  applications(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<ApplicationListResponse>("GET", `/v1/applications${qs}`);
  }
  saved(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<SavedJobListResponse>("GET", `/v1/saved${qs}`);
  }
  async getConsents() {
    const res = await this.request<{ items: ConsentRead[] }>("GET", "/v1/me/consents");
    return res.items;
  }
  setConsent(scope: string, granted: boolean) {
    return this.request<ConsentRead>("PATCH", `/v1/me/consents/${encodeURIComponent(scope)}`, { granted });
  }
  dsrExport() {
    return this.request<unknown>("POST", "/v1/me/dsr/export");
  }
  dsrDelete() {
    return this.request<unknown>("DELETE", "/v1/me/dsr", { confirmation: "DELETE_MY_ACCOUNT" });
  }
  notifications(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<NotificationListResponse>("GET", `/v1/notifications${qs}`);
  }
  markNotificationRead(notificationId: string) {
    return this.request<NotificationRead>("POST", `/v1/notifications/${encodeURIComponent(notificationId)}/read`);
  }
  myInvites() {
    return this.request<MyInviteRead[]>("GET", "/v1/me/invites");
  }
  acceptInvite(inviteId: string) {
    return this.request<AcceptResult>("POST", `/v1/me/invites/${encodeURIComponent(inviteId)}/accept`);
  }
  declineInvite(inviteId: string) {
    return this.request<AcceptResult>("POST", `/v1/me/invites/${encodeURIComponent(inviteId)}/decline`);
  }
}
```

- [ ] **Step 6: Rewrite `frontend/src/sites/web/session.tsx`** to build its context from the shared factory (preserves the `useSessionStore`/`useSession`/`SessionProvider` names that pages import):

```tsx
import { createSession } from "../../shared/session/createSession";
import { DemoClient } from "./api/demo";
import { HttpClient } from "./api/client";
import type { JobifyClient } from "./api/client";
import type { MeResponse } from "./api/types";

export const { SessionProvider, useSessionStore, useSession } = createSession<JobifyClient, MeResponse>({
  makeLive: (store, onSignOut) => new HttpClient(store, onSignOut),
  makeDemo: () => new DemoClient(),
});

export type { MeResponse };
```
> Note: if any web page imports the `Session` type from `./session`, add `export type Session = { client: JobifyClient; identity: MeResponse };`. Check with `grep -rn "from \"../session\"\|from \"./session\"" frontend/src/sites/web` and add only what's imported.

- [ ] **Step 7: Convert `App.tsx` → `WebRoutes.tsx`** — rename, strip the inner `<SessionProvider>` and `<HashRouter>`, and export a route fragment under a session+CSS layout. Run:

```bash
git mv frontend/src/sites/web/App.tsx frontend/src/sites/web/WebRoutes.tsx
```
Then edit `WebRoutes.tsx`: remove the `<HashRouter>` wrapper and the `SessionProvider` import/wrapper from the old `App()`. Replace the top of the file's imports — change `import { SessionProvider, useSessionStore } from "./session";` to `import { SessionProvider, useSessionStore } from "./session";` (unchanged) — and restructure the export as:

```tsx
import { Outlet, Route, Navigate } from "react-router-dom";
import "./styles/site.css";
// ...keep the existing page imports (Landing, Trust, Welcome, Feed, Gate, JobDetail,
//    WhyMatch, Profile, Applications, Inbox, Invites) and RequireApplicant...

/** Session + CSS-scope wrapper for the applicant surface (mounted at "/"). */
function WebLayout() {
  return (
    <SessionProvider>
      <div className="surface-web">
        <Outlet />
      </div>
    </SessionProvider>
  );
}

/** Web (applicant + public) routes, at the root. Returned into the top <Routes>. */
export function WebRoutes() {
  return (
    <Route element={<WebLayout />}>
      <Route path="/" element={<Landing />} />
      <Route path="/trust" element={<Trust />} />
      <Route path="/welcome" element={<Welcome />} />
      <Route path="/explore" element={<RequireApplicant><Feed /></RequireApplicant>} />
      {/* ...keep every existing web <Route> verbatim, paths UNCHANGED... */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Route>
  );
}
```
Preserve the existing `RequireApplicant` helper and the full set of web routes exactly as they were in the old `App.tsx` (paths unchanged). The only structural changes: (a) no `HashRouter`, (b) routes wrapped in `<Route element={<WebLayout/>}>`, (c) `import "./styles/site.css"` moves here (it was in the deleted `main.tsx`), (d) `WebLayout` adds the `surface-web` wrapper div.

- [ ] **Step 8: Wire web into the top `frontend/src/App.tsx`**

```tsx
import { HashRouter, Routes } from "react-router-dom";
import { WebRoutes } from "./sites/web/WebRoutes";

export function App() {
  return (
    <HashRouter>
      {/* HashRouter: static bundle, no server rewrites, tokens stay out of paths. */}
      <Routes>{WebRoutes()}</Routes>
    </HashRouter>
  );
}
```

- [ ] **Step 9: Build**

Run: `cd frontend && npm run build`
Expected: no errors. Fix any leftover import path (e.g. a page importing a deleted `gsi.ts`) by repointing to the shim. `cd ..`

- [ ] **Step 10: Smoke test**

Run: `cd frontend && npm run dev` (port 5173). In a browser, load `http://localhost:5173/#/` (Landing), `/#/welcome`, `/#/explore` (shows the sign-in Gate). Confirm the Google button renders when `VITE_GOOGLE_CLIENT_ID` is set in `frontend/.env`, and demo mode works. Stop dev (`Ctrl-C`). `cd ..`

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "feat(frontend): port web (applicant) surface onto shared core at /"
```

---

### Task 5: Port the console surface (mounted at `/console/*`)

Same move + shim pattern as web, **plus** prefix every console route/nav literal with `/console`, and move `landingFor`/`Area` into `sites/console/area.ts`.

**Files:**
- Move: `console/src/*` → `frontend/src/sites/console/*`
- Rewrite: `.../api/client.ts` (extend `BaseHttpClient`), `.../session.tsx` (factory), `.../env.ts` (shim), `.../auth/GoogleButton.tsx` (shim → shared button)
- Create: `frontend/src/sites/console/area.ts`, `frontend/src/sites/console/ConsoleRoutes.tsx`
- Modify: every file in the prefix list below

**Interfaces:**
- Consumes: same shared modules as web.
- Produces: `ConsoleRoutes(): JSX` route fragment for the top `App.tsx`; `ConsoleClient` interface + `HttpClient`; `areasForRole`, `landingFor` (from `area.ts`).

- [ ] **Step 1: Move the subtree + drop redundant entry files**

```bash
git mv console/src frontend/src/sites/console
git rm frontend/src/sites/console/main.tsx frontend/src/sites/console/vite-env.d.ts
```

- [ ] **Step 2: `env.ts` shim**

```ts
export { API_BASE_URL, GOOGLE_CLIENT_ID } from "../../shared/env";
```

- [ ] **Step 3: Auth shim** — replace `frontend/src/sites/console/auth/GoogleButton.tsx` with a wrapper that defaults the dark theme and adapts the prop name (`onLoadError` is optional in the shared button):

```tsx
import { GoogleSignInButton } from "../../../shared/auth/GoogleSignInButton";

/** Console keeps the dark ("filled_black") Google button. */
export function GoogleButton(props: {
  clientId: string;
  onCredential: (idToken: string) => void;
  onLoadError: (message: string) => void;
}) {
  return <GoogleSignInButton {...props} theme="filled_black" />;
}
```
Then remove the old loader: `git rm frontend/src/sites/console/auth/google-gsi.ts`.
> Console's `GoogleButton` previously used class names `google-signin`/`google-btn-host`. The shared button uses `gsi`/`gsi-btn`/`gsi-hint`. Console CSS is updated for these in Task 7.

- [ ] **Step 4: Rewrite `frontend/src/sites/console/api/client.ts`** — re-export transport from shared; keep the `ConsoleClient` interface; make `HttpClient extends BaseHttpClient`. Replace the file's transport section: delete the local `ApiError`/`errorMessage`/`formatDetail`/`TokenStore`/`INVALID_ACCESS_TOKEN` definitions and the `HttpClient`'s `request`/`readDetail`/`refreshSingleFlight`/`doRefresh` methods; add at top:

```ts
import { BaseHttpClient } from "../../../shared/api/transport";
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";
```
and change the class declaration to:
```ts
export class HttpClient extends BaseHttpClient implements ConsoleClient {
```
Keep every endpoint method body verbatim (they already call `this.request(...)`). Keep the `ConsoleClient` interface and all `import type {...} from "./types"` lines unchanged.

- [ ] **Step 5: Extract `frontend/src/sites/console/area.ts`** from the old `session.tsx` (the `Area`/`areasForRole`/`landingFor` block), prefixing the landing paths with `/console`:

```ts
/** Role → reachable console areas. `users.role` is single-valued server-side. */
export type Area = "admin" | "recruiter";

const AREAS_FOR_ROLE: Record<string, Area[]> = {
  admin: ["admin"],
  recruiter: ["recruiter"],
};

export function areasForRole(role: string): Area[] {
  return AREAS_FOR_ROLE[role] ?? [];
}

/** Where a freshly-signed-in operator (or a wrong-area redirect) should land. */
export function landingFor(role: string): string {
  switch (areasForRole(role)[0]) {
    case "admin":
      return "/console/admin/audit";
    case "recruiter":
      return "/console/recruiter";
    default:
      return "/console/no-access";
  }
}
```

- [ ] **Step 6: Rewrite `frontend/src/sites/console/session.tsx`** to the factory (note: console used `DemoRole`; default to `"admin"`):

```tsx
import { createSession } from "../../shared/session/createSession";
import { DemoClient } from "./api/demo";
import type { DemoRole } from "./api/demo";
import { HttpClient } from "./api/client";
import type { ConsoleClient } from "./api/client";
import type { MeResponse } from "./api/types";

export const { SessionProvider, useSessionStore, useSession } = createSession<ConsoleClient, MeResponse>({
  makeLive: (store, onSignOut) => new HttpClient(store, onSignOut),
  makeDemo: (role) => new DemoClient((role ?? "admin") as DemoRole),
});

// Re-export the area helpers from their new home so existing imports survive.
export { areasForRole, landingFor } from "./area";
export type { Area } from "./area";
```
> The old console session exposed `disconnect()`. The shared factory exposes `signOut()`. Update call sites in Step 8's grep (search `disconnect(`).

- [ ] **Step 7: Convert `App.tsx` → `ConsoleRoutes.tsx`**

```bash
git mv frontend/src/sites/console/App.tsx frontend/src/sites/console/ConsoleRoutes.tsx
```
Edit it: remove `<HashRouter>` and the top-level `<SessionProvider>` wrapper; wrap routes in a layout route that provides the session + `surface-console` div + sets the document title; **prefix every `path=` with `/console`**; add `import "./styles/console.css";`. Skeleton:

```tsx
import { Outlet, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import "./styles/console.css";
import { SessionProvider } from "./session";
// ...keep page imports (SignIn, Analytics, AuditExplorer, UserActions, Verification,
//    Dashboard, Jobs, JobComposer, Applicants, Team) + the existing guard helpers...

function ConsoleLayout() {
  useEffect(() => {
    document.title = "JOBIFY // CONSOLE";
  }, []);
  return (
    <SessionProvider>
      <div className="surface-console">
        <Outlet />
      </div>
    </SessionProvider>
  );
}

export function ConsoleRoutes() {
  return (
    <Route element={<ConsoleLayout />}>
      <Route path="/console/signin" element={<SignIn />} />
      <Route path="/console/admin/analytics" element={/* guard */ <Analytics />} />
      <Route path="/console/admin/audit" element={/* guard */ <AuditExplorer />} />
      <Route path="/console/admin/users" element={/* guard */ <UserActions />} />
      <Route path="/console/admin/verification" element={/* guard */ <Verification />} />
      <Route path="/console/recruiter" element={/* guard */ <Dashboard />} />
      <Route path="/console/recruiter/jobs" element={/* guard */ <Jobs />} />
      <Route path="/console/recruiter/jobs/new" element={/* guard */ <JobComposer />} />
      <Route path="/console/recruiter/jobs/:jobId/edit" element={/* guard */ <JobComposer />} />
      <Route path="/console/recruiter/jobs/:jobId/applicants" element={/* guard */ <Applicants />} />
      <Route path="/console/recruiter/team" element={/* guard */ <Team />} />
      <Route path="/console/no-access" element={/* ... */ <Navigate to="/console/signin" replace />} />
      <Route path="/console/*" element={<Navigate to="/console/signin" replace />} />
    </Route>
  );
}
```
Keep the original guard wrappers (the `RequireSession`/area-check components and their `<Navigate to="/signin">` redirects) — but change those redirect targets to `/console/signin` (see prefix list). Preserve the original route element structure; only paths and the wrapper change.

- [ ] **Step 8: Prefix all remaining console nav literals.** Apply these exact replacements (left → right) across `frontend/src/sites/console/`:

| File | Old | New |
| --- | --- | --- |
| `ConsoleRoutes.tsx` (guards) | `Navigate to="/signin"` (×3) | `Navigate to="/console/signin"` |
| `pages/admin/UserActions.tsx:54` | `to="/admin/audit"` | `to="/console/admin/audit"` |
| `pages/recruiter/Applicants.tsx:29` | `to="/recruiter/jobs"` | `to="/console/recruiter/jobs"` |
| `pages/recruiter/Dashboard.tsx` (×3) | `to="/recruiter/jobs"`, `to="/recruiter/team"` | prefix each with `/console` |
| `pages/recruiter/JobComposer.tsx` (×4) | `navigate("/recruiter/jobs"`, `to="/recruiter/jobs"` | prefix each with `/console` |
| `pages/recruiter/Jobs.tsx:88` | `navigate("/recruiter/jobs/new"` | `navigate("/console/recruiter/jobs/new"` |

Verify none missed:
```bash
grep -rnE '(to|navigate\()="?/(admin|recruiter|signin|no-access)' frontend/src/sites/console || echo "clean"
```
Expected: `clean`. Also update any `disconnect(` → `signOut(`:
```bash
grep -rn "disconnect(" frontend/src/sites/console
```
Rename each to `signOut(`.

- [ ] **Step 9: Wire console into the top `App.tsx`** (more specific than web; React Router ranks by specificity):

```tsx
import { ConsoleRoutes } from "./sites/console/ConsoleRoutes";
// inside <Routes>:
//   {ConsoleRoutes()}
//   {WebRoutes()}
```

- [ ] **Step 10: Build + smoke**

Run: `cd frontend && npm run build` (expect clean), then `npm run dev`. Load `/#/console/signin`, sign in via demo (admin) → lands `/#/console/admin/audit`; check recruiter demo lands `/#/console/recruiter`; click through nav links and confirm they stay under `/console`. `cd ..`

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "feat(frontend): port console surface onto shared core at /console"
```

---

### Task 6: Port the employers surface (mounted at `/employers/*`)

Marketing only — no api/session/auth. Move the subtree, prefix its nav literals, wrap in a CSS-scope layout.

**Files:**
- Move: `employers/src/*` → `frontend/src/sites/employers/*`
- Create: `frontend/src/sites/employers/EmployersRoutes.tsx`
- Modify: `Chrome.tsx`, `Landing.tsx`, `Verify.tsx` (nav literals)

**Interfaces:**
- Produces: `EmployersRoutes(): JSX` route fragment for the top `App.tsx`.

- [ ] **Step 1: Move + drop entry files**

```bash
git mv employers/src frontend/src/sites/employers
git rm frontend/src/sites/employers/main.tsx
# employers has no vite-env.d.ts; skip if absent.
```

- [ ] **Step 2: Convert `App.tsx` → `EmployersRoutes.tsx`**

```bash
git mv frontend/src/sites/employers/App.tsx frontend/src/sites/employers/EmployersRoutes.tsx
```
Edit: remove `<HashRouter>`; wrap in a CSS-scope layout; prefix paths with `/employers`; move CSS import here:

```tsx
import { Outlet, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import "./styles/site.css";
import { Landing } from "./pages/Landing";
import { Verify } from "./pages/Verify";

function EmployersLayout() {
  useEffect(() => {
    document.title = "Jobify for employers — ranked applicants, not a résumé pile";
  }, []);
  return (
    <div className="surface-employers">
      <Outlet />
    </div>
  );
}

export function EmployersRoutes() {
  return (
    <Route element={<EmployersLayout />}>
      <Route path="/employers" element={<Landing />} />
      <Route path="/employers/verify" element={<Verify />} />
      <Route path="/employers/*" element={<Navigate to="/employers" replace />} />
    </Route>
  );
}
```

- [ ] **Step 3: Prefix employers nav literals** (path part only; preserve trailing `#anchor`):

| File:line | Old | New |
| --- | --- | --- |
| `components/Chrome.tsx:14,59` | `to="/"` | `to="/employers"` |
| `components/Chrome.tsx:31` | `to="/#how"` | `to="/employers#how"` |
| `components/Chrome.tsx:32,75` | `to="/verify"` | `to="/employers/verify"` |
| `components/Chrome.tsx:33` | `to="/#pricing"` | `to="/employers#pricing"` |
| `components/Chrome.tsx:34` | `to="/#faq"` | `to="/employers#faq"` |
| `pages/Landing.tsx:227,359,424` | `to="/verify"` | `to="/employers/verify"` |
| `pages/Verify.tsx:18,193` | `to="/"` | `to="/employers"` |

Verify:
```bash
grep -rnE 'to="/(verify|#|")' frontend/src/sites/employers || echo "clean"
```
Expected: `clean` (only `/employers...` targets remain).

- [ ] **Step 4: Wire employers into the top `App.tsx`** (final form):

```tsx
import { HashRouter, Routes } from "react-router-dom";
import { EmployersRoutes } from "./sites/employers/EmployersRoutes";
import { ConsoleRoutes } from "./sites/console/ConsoleRoutes";
import { WebRoutes } from "./sites/web/WebRoutes";

export function App() {
  return (
    <HashRouter>
      <Routes>
        {EmployersRoutes()}
        {ConsoleRoutes()}
        {WebRoutes()}
      </Routes>
    </HashRouter>
  );
}
```

- [ ] **Step 5: Build + smoke**

Run: `cd frontend && npm run build` (clean), then `npm run dev`. Load `/#/employers` (Landing), `/#/employers/verify`. Confirm links stay under `/employers`. Re-check `/#/` (web) and `/#/console/signin` still work. `cd ..`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(frontend): port employers surface onto shared shell at /employers"
```

---

### Task 7: CSS scoping + bits.tsx reconciliation

All three stylesheets now load in one bundle. Scope each under its surface class (the `surface-web`/`surface-console`/`surface-employers` wrappers added in Tasks 4–6), update console's CSS for the unified GSI button class names, and extract genuinely-identical `bits.tsx` primitives to `shared/components/`.

**Files:**
- Modify: `frontend/src/sites/web/styles/site.css`, `.../console/styles/console.css`, `.../employers/styles/site.css`
- Create: `frontend/src/shared/components/bits.tsx` (only if shared primitives exist)
- Modify: `frontend/src/sites/{web,console}/components/bits.tsx`

- [ ] **Step 1: Audit global-selector collisions**

```bash
cd frontend
grep -nE '^\s*(:root|html|body|\*)\b' src/sites/web/styles/site.css src/sites/console/styles/console.css src/sites/employers/styles/site.css
cd ..
```
This lists the global rules that will bleed across surfaces.

- [ ] **Step 2: Scope each stylesheet under its surface class.** For each file, prefix top-level non-`:root`/non-`@` selectors with the surface class:
  - `web/styles/site.css` → prefix selectors with `.surface-web ` (e.g. `body` rules become `.surface-web` rules; generic classes `.card` → `.surface-web .card`).
  - `console/styles/console.css` → `.surface-console `.
  - `employers/styles/site.css` → `.surface-employers `.
  `:root { --tokens }` may stay global **only if** the custom-property names don't conflict across files with different values; if they do (e.g. two different `--bg`), move them under the surface class too. After editing, confirm fonts still resolve (the families are all loaded in `index.html`).

> This is manual surgery with no automated test. Work one file at a time and visually smoke each surface after.

- [ ] **Step 3: Update console CSS for the unified GSI button classes.** Console's old button used `google-signin`/`google-btn-host`/`k dim`; the shared button emits `gsi`/`gsi-btn`/`gsi-hint`. Port the old rules to the new class names (scoped under `.surface-console`):

```bash
grep -n "google-signin\|google-btn-host" frontend/src/sites/console/styles/console.css
```
Rename those selectors to `.surface-console .gsi` / `.surface-console .gsi-btn` and add a `.surface-console .gsi-hint` rule mirroring the old hint styling.

- [ ] **Step 4: Reconcile `bits.tsx`.** Diff the two files; extract only primitives that are **byte-identical in behavior and markup** into `shared/components/bits.tsx`, and re-export them from each surface's `bits.tsx` so page imports survive:

```bash
diff frontend/src/sites/web/components/bits.tsx frontend/src/sites/console/components/bits.tsx
```
For each identical primitive: move it to `frontend/src/shared/components/bits.tsx`, then in both surface `bits.tsx` files add `export { Thing } from "../../../shared/components/bits";` and delete the local copy. Leave divergent primitives in place. If nothing is byte-identical, skip creating the shared file and note it in the commit message.

- [ ] **Step 5: Build + full visual smoke**

Run: `cd frontend && npm run build` (clean), then `npm run dev`. Load all three surfaces (`/#/`, `/#/employers`, `/#/console/signin`) and confirm: each renders with its own look, **no cross-surface CSS bleed** (e.g. console's dark theme doesn't leak into web), the Google button is styled on both web and console. `cd ..`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(frontend): scope per-surface CSS + share identical bits primitives"
```

---

### Task 8: Delete old apps + docs + final build

**Files:**
- Delete: `web/`, `console/`, `employers/` (top-level)
- Create: `frontend/README.md`
- Modify: root `CLAUDE.md` (frontend pointer), `~/.claude/projects/.../memory/jobify-web-frontends.md`, `.gitignore`

- [ ] **Step 1: Remove the old app directories**

```bash
git rm -r web console employers
```

- [ ] **Step 2: Verify nothing references the old paths**

```bash
grep -rnE '\b(web|console|employers)/(src|package\.json|dist)' --include="*.md" --include="*.json" --include="*.yml" . | grep -v "frontend/" | grep -v node_modules || echo "clean"
```
Expected: `clean` (or only historical mentions in `docs/superpowers/specs/`). Fix any live references.

- [ ] **Step 3: Ensure `.gitignore` covers the merged app**

```bash
grep -qE 'frontend/.*node_modules|^node_modules|/dist' .gitignore || printf '\nfrontend/node_modules/\nfrontend/dist/\n' >> .gitignore
```
(Adjust to match the existing ignore style; the three old apps' `dist/`/`node_modules/` were ignored — mirror that for `frontend/`.)

- [ ] **Step 4: Write `frontend/README.md`** — run/build/env + the surface→route map. Minimum content:

```markdown
# Jobify Frontend

One Vite + React + TS app; three surfaces under one HashRouter:

- `/` — applicant + public marketing (`src/sites/web`)
- `/employers` — recruiter marketing (`src/sites/employers`)
- `/console` — internal admin + recruiter ops (`src/sites/console`)

Shared transport/session/auth/env live in `src/shared`.

## Run

    cd frontend
    npm install
    cp .env.example .env   # set VITE_GOOGLE_CLIENT_ID, VITE_API_BASE_URL
    npm run dev            # http://localhost:5173

Live surfaces (web, console) need 5173 in the API's `JOBIFY_CORS_ALLOW_ORIGINS`
and the dev origin in the Google Web OAuth client's Authorized JavaScript origins.

## Build / typecheck

    npm run build          # tsc -b && vite build → dist/
```

- [ ] **Step 5: Update the root `CLAUDE.md`** — replace any "five web properties" / `web`,`console`,`employers` references with the unified `frontend/` (three surfaces) + `emails/`,`styleguide/` (static). Keep it terse.

- [ ] **Step 6: Update the memory note** `~/.claude/projects/-Users-ahamadshah-ahamed-personal-jobify/memory/jobify-web-frontends.md` to describe the merged `frontend/` (one app, three route-prefixed surfaces, shared core) and adjust the `MEMORY.md` one-liner.

- [ ] **Step 7: Final clean build from scratch**

```bash
cd frontend && rm -rf node_modules dist && npm install && npm run build && cd ..
```
Expected: clean install + build.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "chore(frontend): remove old web/console/employers apps; add docs"
```

---

## Self-Review

**1. Spec coverage:**
- One app / one build / one deploy → Tasks 1–8 (single `frontend/`, one `npm run build`). ✅
- Route prefixes `/`, `/employers`, `/console` under HashRouter → Tasks 4–6. ✅
- Console fully merged, no special handling → Task 5 (plain routes, no lazy/gate). ✅
- Sessions independent per surface → Task 3 factory + per-surface `SessionProvider` in Tasks 4/5. ✅
- New `frontend/` dir, surface names 1:1 → Task 1 + `sites/{web,employers,console}`. ✅
- Shared transport/session/env/auth; per-surface pages/layouts/clients/types → Tasks 2–3 (shared) + 4–6 (per-surface shims). ✅
- Canonical reconciliations (ApiError requestId, loc-aware formatDetail, applicant_id nullable, signOut name) → Task 2 + Task 5 Step 8. ✅
- Selective bits.tsx dedup → Task 7 Step 4. ✅
- CSS scoping via surface classes → Tasks 4–6 (wrappers) + Task 7 (scoping). ✅
- Union of fonts/favicon, public asset consolidation → Task 1 Steps 5–6. ✅
- Verification = tsc + build + manual smoke → every task's build/smoke steps. ✅
- Delete old dirs + docs + memory update → Task 8. ✅

**2. Placeholder scan:** No TBD/TODO. Where full page bodies aren't reproduced (they move verbatim via `git mv`), the exact mechanical transformation + enumerated literal lists are given. The only judgment steps (CSS scoping, bits identity) are bounded with grep commands and "leave divergent in place" rules.

**3. Type consistency:** `createSession<TClient, TIdentity>` signature matches its call sites (web `<JobifyClient, MeResponse>`, console `<ConsoleClient, MeResponse>`). `HttpClient extends BaseHttpClient` and `request` is `protected` (callable from subclass methods). Shim re-exports preserve `ApiError`/`errorMessage`/`TokenStore`/`GoogleSignInButton`/`API_BASE_URL`/`GOOGLE_CLIENT_ID` names that pages import. `signOut` replaces console's `disconnect` (Task 5 Step 8 fixes call sites).
