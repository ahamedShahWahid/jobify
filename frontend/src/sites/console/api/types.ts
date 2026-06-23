/**
 * Wire types mirroring the FastAPI Pydantic response models verbatim.
 * Source of truth: api/src/jobify/routes/{admin,jobs,employers,me}.py.
 * Decimal fields (ctc_*) serialize as JSON numbers (schemas declare float).
 */

// ---- /v1/me ----------------------------------------------------

export interface MeResponse {
  id: string;
  email: string | null;
  role: string; // "applicant" | "recruiter" | "admin"
  applicant: unknown | null;
}

// ---- /v1/admin -------------------------------------------------

export interface AdminUserRead {
  id: string;
  email: string | null;
  role: string;
  suspended_at: string | null;
  suspension_reason: string | null;
}

export interface AuditLogRead {
  id: string;
  actor_user_id: string | null;
  actor_role: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  context: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogRead[];
  next_cursor: string | null;
}

export interface AuditLogFilters {
  actor_user_id?: string;
  resource_type?: string;
  resource_id?: string;
  action?: string;
  from?: string; // ISO datetime
  to?: string;
  cursor?: string;
  limit?: number;
}

// ---- /v1/jobs (recruiter) --------------------------------------

export interface JobRead {
  id: string;
  title: string;
  description: string;
  locations: string[];
  min_exp_years: number;
  max_exp_years: number;
  ctc_min: number | null;
  ctc_max: number | null;
  status: string; // "open" | "closed"
  posted_at: string;
  employer_verified: boolean;
}

export interface RecruiterJobRow extends JobRead {
  applicant_count: number;
  surfaced_match_count: number;
}

export interface RecruiterJobsPage {
  items: RecruiterJobRow[];
  next_cursor: string | null;
}

export interface JobCreate {
  employer_id: string;
  title: string;
  description: string;
  locations: string[];
  min_exp_years: number;
  max_exp_years: number;
  ctc_min?: number | null;
  ctc_max?: number | null;
  status?: "open" | "closed";
}

export interface JobPatch {
  title?: string;
  description?: string;
  locations?: string[];
  min_exp_years?: number;
  max_exp_years?: number;
  ctc_min?: number | null;
  ctc_max?: number | null;
  status?: "open" | "closed";
}

export interface ApplicantOfJobRow {
  application_id: string;
  applicant_id: string;
  display_name: string | null;
  email: string | null;
  status: string;
  applied_at: string;
  match_score: number | null;
  match_explanation: Record<string, string> | null;
}

export interface ApplicantsOfJobPage {
  items: ApplicantOfJobRow[];
  next_cursor: string | null;
}

// ---- /v1/employers ---------------------------------------------

export interface EmployerRead {
  id: string;
  name: string;
  gst: string | null;
  verified_at: string | null;
  created_at: string;
}

// ---- /v1/admin/employers (PROPOSED — see client.ts) ------------
//
// No backend endpoint exists for an employer verification queue yet (admin has
// only audit-logs + suspend/unsuspend today). These types model the contract the
// console *would* consume once the backend exposes it; in live mode the calls
// 404. The DemoClient implements them fully against seeded data.

export type EmployerVerificationStatus = "pending" | "verified" | "rejected";

export interface EmployerVerificationRow {
  id: string;
  name: string;
  gst: string | null;
  status: EmployerVerificationStatus;
  created_at: string;
  reviewed_at: string | null; // derived: verified_at or rejected_at, whichever is set
  reason: string | null; // rejection_reason, only set while rejected
  // Demo-only enrichment. The real GET /v1/admin/employers response omits these —
  // employers don't collect domain/contact today, and reviewer history lives in
  // audit_logs (admin.employer.verified / .rejected), not a column.
  domain?: string | null;
  contact_email?: string | null;
  reviewer?: string | null;
}

export interface EmployerVerificationPage {
  items: EmployerVerificationRow[];
  next_cursor: string | null;
}

export interface MemberRead {
  user_id: string;
  email: string | null;
  display_name: string | null;
  role: string; // "owner" | "member"
  added_at: string;
}

export interface InviteRead {
  id: string;
  employer_id: string;
  email: string;
  role: string;
  status: string; // "pending" | "accepted" | "revoked" | "expired"
  expires_at: string;
  created_at: string;
  invited_by_user_id: string | null;
}
