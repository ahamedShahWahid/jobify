/**
 * Wire types mirroring the FastAPI Pydantic response models verbatim.
 * Source of truth: api/src/jobify_api/routes/{jobs,employers,me}.py.
 * Decimal fields (ctc_*) serialize as JSON numbers (schemas declare float).
 */

// ---- /v1/me ----------------------------------------------------

export interface MeResponse {
  id: string;
  email: string | null;
  role: string; // "applicant" | "recruiter" | "admin"
  applicant: unknown | null;
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

export interface EmployerCreate {
  name: string;
  gst?: string | null;
}

export interface EmployerRead {
  id: string;
  name: string;
  gst: string | null;
  verified_at: string | null;
  created_at: string;
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
