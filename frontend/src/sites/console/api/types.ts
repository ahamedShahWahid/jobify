/**
 * Wire types mirroring the FastAPI Pydantic response models verbatim.
 * Source of truth: api/src/jobify_api/routes/{admin,me}.py.
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

export interface CountBucket {
  key: string;
  count: number;
}

export interface DayBucket {
  day: string;
  count: number;
}

export interface AdminAnalyticsSummary {
  total_events: number;
  distinct_actors: number;
  last_24h: number;
  system_events: number;
  span_start: string | null;
  span_end: string | null;
  activity: DayBucket[];
  role_counts: CountBucket[];
  action_counts: CountBucket[];
}

// ---- /v1/admin/employers ----------------------------------------

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

export interface EmployerVerificationCounts {
  pending: number;
  verified: number;
  rejected: number;
}

// ---- /v1/admin/match-feedback — mirrors
// api/src/jobify_api/routes/admin/match_feedback.py ---------------

export type MatchFeedbackRating = "up" | "down";

export interface AdminMatchFeedbackRow {
  id: string;
  rating: MatchFeedbackRating;
  created_at: string;
  updated_at: string;
  job_id: string;
  job_title: string;
  employer_name: string;
  applicant_id: string;
  applicant_name: string | null;
  total_score: number | null;
  explanation: { fit?: string; caveat?: string } | null;
}

export interface AdminMatchFeedbackPage {
  items: AdminMatchFeedbackRow[];
  next_cursor: string | null;
}

export interface MatchFeedbackWindowStats {
  up: number;
  down: number;
  /** up / (up + down); null when nothing rated yet. */
  share: number | null;
}

export interface AdminMatchFeedbackSummary {
  all_time: MatchFeedbackWindowStats;
  last_30d: MatchFeedbackWindowStats;
}
