import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { JobifyClient } from "./api/client";
import { HttpClient } from "./api/client";
import { DemoClient } from "./api/demo";
import type { MeResponse } from "./api/types";

export interface Session {
  client: JobifyClient;
  identity: MeResponse;
}

interface SessionStore {
  session: Session | null;
  /** True when the last session ended via an expired/invalid token, not a sign-out. */
  expired: boolean;
  connectLive: (baseUrl: string, token: string) => Promise<MeResponse>;
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

  const store = useMemo<SessionStore>(
    () => ({
      session,
      expired,
      // Tokens are short-lived; a 401 mid-session clears state and routes back to
      // the gate with an "expired" notice rather than stranding the user.
      connectLive: (baseUrl, token) =>
        connect(
          new HttpClient(baseUrl.replace(/\/$/, ""), token, () => {
            setSession(null);
            setExpired(true);
          }),
        ),
      connectDemo: () => connect(new DemoClient()),
      signOut: () => {
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

export function useSession(): Session {
  const { session } = useSessionStore();
  if (!session) throw new Error("useSession without an active session");
  return session;
}
