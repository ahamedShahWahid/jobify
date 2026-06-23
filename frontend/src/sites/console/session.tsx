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
