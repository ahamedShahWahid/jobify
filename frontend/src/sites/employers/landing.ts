/** Where a signed-in employers-surface user should land, based on role. Used
 *  both right after sign-in and as RequireRecruiter's redirect target — kept
 *  as one function so the two call sites can't drift on what a non-recruiter
 *  role should see. */
export function landingFor(role: string): string {
  if (role === "recruiter") return "/employers/dashboard";
  if (role === "applicant") return "/employers/onboarding";
  return "/employers/no-access";
}
