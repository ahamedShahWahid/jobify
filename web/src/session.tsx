import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { JobifyClient } from "./api/client";
import { ApiError, HttpClient } from "./api/client";
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

  const connectLive = useCallback(
    (baseUrl: string, token: string) =>
      // Tokens are short-lived; a 401 mid-session clears state and routes back to
      // the gate with an "expired" notice rather than stranding the user.
      connect(
        new HttpClient(baseUrl.replace(/\/$/, ""), token, () => {
          setSession(null);
          setExpired(true);
        }),
      ),
    [connect],
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
      // TODO: refresh-token rotation (see app/ refresh interceptor). For now the
      // returned refresh_token is intentionally unused — a 401 returns to the gate
      // where the Google button is one click away.
      return connectLive(base, data.access_token);
    },
    [connectLive],
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
