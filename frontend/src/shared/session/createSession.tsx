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
  makeDemo?: (role?: string) => TClient;
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
    /** Re-fetches identity on the CURRENT client (no new client, no new token) —
     *  for when a mutation flips the caller's role server-side mid-session. */
    refreshIdentity: () => Promise<TIdentity>;
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
