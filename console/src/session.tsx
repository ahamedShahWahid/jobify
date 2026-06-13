import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ConsoleClient } from "./api/client";
import { HttpClient } from "./api/client";
import { DemoClient } from "./api/demo";
import type { DemoRole } from "./api/demo";
import type { MeResponse } from "./api/types";

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

  const store = useMemo<SessionStore>(
    () => ({
      session,
      expired,
      // Access tokens are short-lived (≤10 min TTL) and held in memory only — a
      // reload means re-pasting the token, by design. The onUnauthorized hook
      // clears the session on ANY 401 so a mid-session expiry routes back to the
      // sign-in gate (with an "expired" notice) instead of stranding the user on
      // dead pages.
      connectLive: (baseUrl, token) =>
        connect(
          new HttpClient(baseUrl.replace(/\/$/, ""), token, () => {
            setSession(null);
            setExpired(true);
          }),
        ),
      connectDemo: (role) => connect(new DemoClient(role)),
      disconnect: () => {
        setSession(null);
        setExpired(false);
      },
    }),
    [session, expired, connect],
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
