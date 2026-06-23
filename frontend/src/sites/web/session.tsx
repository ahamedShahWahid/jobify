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
