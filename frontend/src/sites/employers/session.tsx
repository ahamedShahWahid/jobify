import { createSession } from "../../shared/session/createSession";
import { HttpClient } from "./api/client";
import type { EmployerClient } from "./api/client";
import type { MeResponse } from "./api/types";

export const { SessionProvider, useSessionStore, useSession } = createSession<EmployerClient, MeResponse>({
  makeLive: (store, onSignOut) => new HttpClient(store, onSignOut),
});
