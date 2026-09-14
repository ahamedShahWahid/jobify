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

/** Every JobRead field except description — GET /v1/jobs/me's row shape
 * (PERF-09; description is the largest field on a job and no list/card view
 * renders it). GET /v1/jobs/me/{id} (and create/patch responses) return the
 * full JobRead below instead. */
export interface JobSummaryRead {
  id: string;
  title: string;
  locations: string[];
  min_exp_years: number;
  max_exp_years: number;
  ctc_min: number | null;
  ctc_max: number | null;
  status: string; // "open" | "closed"
  posted_at: string;
  employer_verified: boolean;
}

export interface JobRead extends JobSummaryRead {
  description: string;
}

/** GET /v1/jobs/me row — no description. Opening the edit form or the job
 * detail view must fetch the full job via EmployerClient.getMyJob(id)
 * first; never prefill/render description from one of these. */
export interface RecruiterJobRow extends JobSummaryRead {
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

export type ApplicationStage =
  | "applied"
  | "shortlisted"
  | "interview"
  | "offer"
  | "hired"
  | "rejected";

export interface StageChangeRead {
  application_id: string;
  stage: ApplicationStage;
  updated_at: string;
}

export interface ApplicantOfJobRow {
  application_id: string;
  applicant_id: string;
  display_name: string | null;
  email: string | null;
  status: string;
  stage: ApplicationStage;
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
