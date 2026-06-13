import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ConsoleClient } from "./api/client";
import { ApiError, HttpClient, TokenStore } from "./api/client";
import { DemoClient } from "./api/demo";
import type { DemoRole } from "./api/demo";
import type { MeResponse } from "./api/types";

/** Wire shape of `POST /v1/auth/oauth/google` (mirrors `SignInResponse`). */
interface GoogleSignInResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: { id: string; email: string; role: string; applicant_id: string; is_new_user: boolean };
}

/** Flatten an RFC 7807 problem `detail` (string) to a display string, as HttpClient does. */
function detailString(detail: unknown, fallback: string): string {
  return typeof detail === "string" ? detail : fallback;
}

export interface Session {
  client: ConsoleClient;
  identity: MeResponse;
}

export type Area = "admin" | "recruiter";

/**
 * Role → reachable console areas. `users.role` is single-valued in the backend
 * (an admin is never a recruiter and `_require_recruiter`/`_require_admin` 403
 * the other role), so each role maps to exactly one area. This is the single
 * source of truth for both the nav rail (Shell) and the route guards (App).
 */
const AREAS_FOR_ROLE: Record<string, Area[]> = {
  admin: ["admin"],
  recruiter: ["recruiter"],
};

export function areasForRole(role: string): Area[] {
  return AREAS_FOR_ROLE[role] ?? [];
}

/** Where a freshly-signed-in user (or a wrong-area redirect) should land. */
export function landingFor(role: string): string {
  switch (areasForRole(role)[0]) {
    case "admin":
      return "/admin/audit";
    case "recruiter":
      return "/recruiter";
    default:
      return "/no-access";
  }
}

interface SessionStore {
  session: Session | null;
  /** True when the last session ended via an expired/invalid token, not a manual disconnect. */
  expired: boolean;
  connectLive: (baseUrl: string, token: string) => Promise<MeResponse>;
  /** Exchange a Google ID token for an access token, then `connectLive`. */
  connectGoogle: (idToken: string, baseUrl: string) => Promise<MeResponse>;
  connectDemo: (role: DemoRole) => Promise<MeResponse>;
  disconnect: () => void;
}

const SessionContext = createContext<SessionStore | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [expired, setExpired] = useState(false);

  const connect = useCallback(async (client: ConsoleClient) => {
    const identity = await client.me();
    setSession({ client, identity });
    setExpired(false);
    return identity;
  }, []);

  // A live client over a token store. On an unrecoverable 401 (refresh failed or a
  // non-refreshable slug) the session clears and routes back to sign-in with an
  // "expired" notice.
  const makeLiveClient = useCallback(
    (store: TokenStore) =>
      new HttpClient(store, () => {
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
    async (idToken: string, baseUrl: string): Promise<MeResponse> => {
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
        let detail = `HTTP ${res.status}`;
        try {
          const problem = (await res.json()) as { detail?: unknown; title?: unknown };
          detail = detailString(problem.detail, detailString(problem.title, detail));
        } catch {
          /* non-JSON error body — keep the status fallback */
        }
        throw new ApiError(res.status, detail, res.headers.get("X-Request-Id") ?? undefined);
      }
      const data = (await res.json()) as GoogleSignInResponse;
      // Google sessions carry the refresh token, so a mid-session access-token
      // expiry refreshes transparently (single-flight + rotation in HttpClient)
      // instead of bouncing the operator back to sign-in.
      return connect(
        makeLiveClient(new TokenStore(base, data.access_token, data.refresh_token)),
      );
    },
    [connect, makeLiveClient],
  );

  const store = useMemo<SessionStore>(
    () => ({
      session,
      expired,
      // Access tokens are short-lived (≤10 min TTL) and held in memory only — a
      // reload means re-authenticating, by design. The onUnauthorized hook
      // clears the session on ANY 401 so a mid-session expiry routes back to the
      // sign-in gate (with an "expired" notice) instead of stranding the user on
      // dead pages.
      connectLive,
      connectGoogle,
      connectDemo: (role) => connect(new DemoClient(role)),
      disconnect: () => {
        setSession(null);
        setExpired(false);
      },
    }),
    [session, expired, connect, connectLive, connectGoogle],
  );

  return <SessionContext.Provider value={store}>{children}</SessionContext.Provider>;
}

export function useSessionStore(): SessionStore {
  const store = useContext(SessionContext);
  if (!store) throw new Error("useSessionStore outside SessionProvider");
  return store;
}

/** For routes behind the auth gate, where a session is guaranteed. */
export function useSession(): Session {
  const { session } = useSessionStore();
  if (!session) throw new Error("useSession without an active session");
  return session;
}
