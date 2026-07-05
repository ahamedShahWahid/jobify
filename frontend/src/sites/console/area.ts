import { CONSOLE_BASE } from "./base";

/** Role → reachable console areas. `users.role` is single-valued server-side.
 *  Console is jobify-internal now — only "admin" ever reaches it; a recruiter
 *  or applicant signing in here lands on /no-access (recruiters have their
 *  own workspace at /employers). */
export type Area = "admin";

const AREAS_FOR_ROLE: Record<string, Area[]> = {
  admin: ["admin"],
};

export function areasForRole(role: string): Area[] {
  return AREAS_FOR_ROLE[role] ?? [];
}

/** Where a freshly-signed-in operator (or a wrong-role redirect) should land. */
export function landingFor(role: string): string {
  return areasForRole(role).length > 0 ? `${CONSOLE_BASE}/admin/audit` : `${CONSOLE_BASE}/no-access`;
}
