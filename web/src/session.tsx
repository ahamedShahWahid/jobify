import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { JobifyClient } from "./api/client";
import { ApiError, HttpClient, TokenStore } from "./api/client";
import { DemoClient } from "./api/demo";
import type { MeResponse } from "./api/types";

/** POST /v1/auth/oauth/google response (mirrors the FastAPI token envelope). */
interface GoogleOAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: { id: string; email: string; role: string; applicant_id: string | null; is_new_user: boolean };
}

function problemDetail(body: unknown, status: number): string {
  if (body && typeof body === "object") {
    const p = body as { detail?: unknown; title?: unknown };
    if (typeof p.detail === "string") return p.detail;
    if (typeof p.title === "string") return p.title;
  }
  return `HTTP ${status}`;
}

export interface Session {
  client: JobifyClient;
  identity: MeResponse;
}

interface SessionStore {
  session: Session | null;
  /** True when the last session ended via an expired/invalid token, not a sign-out. */
  expired: boolean;
  connectLive: (baseUrl: string, token: string) => Promise<MeResponse>;
  /** Exchange a Google ID token for an access token, then open a live session. */
  connectGoogle: (idToken: string, baseUrl: string) => Promise<MeResponse>;
  connectDemo: () => Promise<MeResponse>;
  signOut: () => void;
}

const SessionContext = createContext<SessionStore | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [expired, setExpired] = useState(false);

  const connect = useCallback(async (client: JobifyClient) => {
    const identity = await client.me();
    setSession({ client, identity });
    setExpired(false);
    return identity;
  }, []);

  // A live client over a token store. On an unrecoverable 401 (refresh failed or
  // a non-refreshable slug) the session clears and routes back to the gate with an
  // "expired" notice rather than stranding the user.
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
        throw new ApiError(res.status, problemDetail(body, res.status));
      }
      const data = (await res.json()) as GoogleOAuthResponse;
      // Google sessions carry the refresh token, so a mid-session access-token
      // expiry refreshes transparently (single-flight + rotation in HttpClient)
      // instead of bouncing the user back to the gate.
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
      connectLive,
      connectGoogle,
      connectDemo: () => connect(new DemoClient()),
      signOut: () => {
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

export function useSession(): Session {
  const { session } = useSessionStore();
  if (!session) throw new Error("useSession without an active session");
  return session;
}
