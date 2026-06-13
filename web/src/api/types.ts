/**
 * Wire types mirroring the FastAPI applicant-facing response models verbatim.
 * Source of truth: api/src/jobify/routes/{schemas,feed,jobs,applications,saved_jobs,me}.py.
 * Note: the feed/jobs EmployerRead carries `verified: bool` (NOT verified_at/gst —
 * that's the recruiter shape). ctc_* serialize as JSON numbers.
 */

export interface MeResponse {
  id: string;
  email: string | null;
  role: string; // "applicant" | "recruiter" | "admin"
  applicant: ApplicantRead | null;
}

export interface ApplicantRead {
  id: string;
  full_name: string | null;
  locations: string[] | null;
  notice_period_days: number | null;
  current_ctc: string | null; // Decimal → JSON string
  expected_ctc: string | null;
  years_experience: string | null;
}

export interface ConsentRead {
  scope: string; // ConsentScope value, e.g. "email_transactional"
  granted: boolean;
  updated_at: string;
}

export interface MatchRead {
  id: string;
  total_score: number;
  vector_score: number;
  structured_score: number;
  components: Record<string, number>;
  surfaced_at: string | null;
  explanation: { fit?: string; caveat?: string } | null;
}

export interface EmployerRead {
  id: string;
  name: string;
  verified: boolean;
}

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

export interface FeedItem {
  match: MatchRead;
  job: JobRead;
  employer: EmployerRead;
}

export interface FeedResponse {
  items: FeedItem[];
  next_cursor: string | null;
}

export interface ApplicationRead {
  id: string;
  job_id: string;
  status: string; // "applied" | "withdrawn"
  source: string;
  created_at: string;
  updated_at: string;
}

export interface SavedJobRead {
  id: string;
  job_id: string;
  created_at: string;
  updated_at: string;
}

export interface JobDetailResponse {
  job: JobRead;
  employer: EmployerRead;
  match: MatchRead | null;
  application: ApplicationRead | null;
  saved_job: SavedJobRead | null;
}

export interface ApplicationListItem {
  application: ApplicationRead;
  job: JobRead;
  employer: EmployerRead;
}

export interface ApplicationListResponse {
  items: ApplicationListItem[];
  next_cursor: string | null;
}

export interface SavedJobListItem {
  saved_job: SavedJobRead;
  job: JobRead;
  employer: EmployerRead;
}

export interface SavedJobListResponse {
  items: SavedJobListItem[];
  next_cursor: string | null;
}
