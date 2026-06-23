/** Role → reachable console areas. `users.role` is single-valued server-side. */
export type Area = "admin" | "recruiter";

const AREAS_FOR_ROLE: Record<string, Area[]> = {
  admin: ["admin"],
  recruiter: ["recruiter"],
};

export function areasForRole(role: string): Area[] {
  return AREAS_FOR_ROLE[role] ?? [];
}

/** Where a freshly-signed-in operator (or a wrong-area redirect) should land. */
export function landingFor(role: string): string {
  switch (areasForRole(role)[0]) {
    case "admin":
      return "/console/admin/audit";
    case "recruiter":
      return "/console/recruiter";
    default:
      return "/console/no-access";
  }
}
