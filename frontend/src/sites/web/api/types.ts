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
  notice_period_days: number | null;
  current_ctc: string | null; // Decimal → JSON string
  years_experience: string | null;
}

// locations/expected_ctc moved off ApplicantRead onto their own resource —
// GET/PATCH /v1/applicants/me/preferences (source: routes/applicants.py
// PreferencesRead). desired_role is new; nothing here writes it yet.
export interface PreferencesRead {
  desired_role: string | null;
  locations: string[];
  expected_ctc: string | null; // Decimal → JSON string
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

// ---- /v1/notifications (in-app inbox) --------------------------------------
// Source: api/src/jobify/routes/notifications.py (NotificationRead).
// `payload` is kind-specific: application_received → {job_title, employer_name,
// application_id, job_id}; employer_invite → {employer_name, role, invite_id,
// employer_id}. Inbox shows pending/dispatching/sent only (failed is admin-only).

export interface NotificationRead {
  id: string;
  kind: string; // "application_received" | "employer_invite" | …
  channel: string; // "email" | "in_app"
  status: string; // "pending" | "dispatching" | "sent"
  payload: Record<string, unknown>;
  send_after: string;
  sent_at: string | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListItem {
  notification: NotificationRead;
}

export interface NotificationListResponse {
  items: NotificationListItem[];
  next_cursor: string | null;
}

// ---- /v1/me/invites (invitee side of employer invites, R4) -----------------
// Source: api/src/jobify/routes/invites.py (MyInviteRead, AcceptResult).
// Authorization is by email match, not membership — a non-member accepts and is
// flipped to recruiter. Accepting/declining a non-pending invite uniform-404s.

export interface MyInviteRead {
  id: string;
  employer_id: string;
  employer_name: string;
  role: string; // "owner" | "member"
  expires_at: string;
  created_at: string;
}

export interface AcceptResult {
  employer_id: string;
  role: string;
  status: string; // "accepted" | "revoked"
}
