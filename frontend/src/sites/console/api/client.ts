import { BaseHttpClient } from "../../../shared/api/transport";
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";

import type {
  AdminUserRead,
  AdminAnalyticsSummary,
  ApplicantsOfJobPage,
  AuditLogFilters,
  AuditLogListResponse,
  EmployerRead,
  EmployerVerificationPage,
  EmployerVerificationCounts,
  EmployerVerificationRow,
  EmployerVerificationStatus,
  InviteRead,
  JobCreate,
  JobPatch,
  JobRead,
  MeResponse,
  MemberRead,
  RecruiterJobsPage,
} from "./types";

/** One interface, two impls: HttpClient (live API) and DemoClient (fixtures). */
export interface ConsoleClient {
  readonly mode: "live" | "demo";

  me(): Promise<MeResponse>;

  // admin
  listAuditLogs(filters: AuditLogFilters): Promise<AuditLogListResponse>;
  analyticsSummary(): Promise<AdminAnalyticsSummary>;
  suspendUser(userId: string, reason: string): Promise<AdminUserRead>;
  unsuspendUser(userId: string): Promise<AdminUserRead>;

  // admin · employer verification queue (GET/POST /v1/admin/employers, migration 0020)
  listEmployersForVerification(
    status: EmployerVerificationStatus,
    cursor?: string,
  ): Promise<EmployerVerificationPage>;
  employerVerificationCounts(): Promise<EmployerVerificationCounts>;
  verifyEmployer(employerId: string): Promise<EmployerVerificationRow>;
  rejectEmployer(employerId: string, reason: string): Promise<EmployerVerificationRow>;

  // recruiter
  listMyJobs(status: "open" | "closed", cursor?: string): Promise<RecruiterJobsPage>;
  createJob(payload: JobCreate): Promise<JobRead>;
  patchJob(jobId: string, payload: JobPatch): Promise<JobRead>;
  deleteJob(jobId: string): Promise<void>;
  listJobApplicants(jobId: string, cursor?: string): Promise<ApplicantsOfJobPage>;

  myEmployers(): Promise<EmployerRead[]>;
  listMembers(employerId: string): Promise<MemberRead[]>;
  addMember(employerId: string, email: string, role: "owner" | "member"): Promise<MemberRead>;
  changeMemberRole(
    employerId: string,
    memberUserId: string,
    role: "owner" | "member",
  ): Promise<MemberRead>;
  removeMember(employerId: string, memberUserId: string): Promise<void>;
  listInvites(employerId: string): Promise<InviteRead[]>;
  createInvite(employerId: string, email: string, role: "owner" | "member"): Promise<InviteRead>;
  revokeInvite(employerId: string, inviteId: string): Promise<void>;
}

export class HttpClient extends BaseHttpClient implements ConsoleClient {
  me(): Promise<MeResponse> {
    return this.request("GET", "/v1/me");
  }

  listAuditLogs(filters: AuditLogFilters): Promise<AuditLogListResponse> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    return this.request("GET", `/v1/admin/audit-logs${qs ? `?${qs}` : ""}`);
  }

  analyticsSummary(): Promise<AdminAnalyticsSummary> {
    return this.request("GET", "/v1/admin/analytics/summary");
  }

  suspendUser(userId: string, reason: string): Promise<AdminUserRead> {
    return this.request("POST", `/v1/admin/users/${userId}/suspend`, { reason });
  }

  unsuspendUser(userId: string): Promise<AdminUserRead> {
    return this.request("DELETE", `/v1/admin/users/${userId}/suspend`);
  }

  // Employer verification review (admin) — GET /v1/admin/employers (status filter
  // + cursor), POST .../{id}/verify, POST .../{id}/reject {reason}. The live
  // response is AdminEmployerRead {id,name,gst,status,created_at,reviewed_at,reason};
  // the demo-only domain/contact_email/reviewer fields are absent here.
  listEmployersForVerification(
    status: EmployerVerificationStatus,
    cursor?: string,
  ): Promise<EmployerVerificationPage> {
    const params = new URLSearchParams({ status });
    if (cursor) params.set("cursor", cursor);
    return this.request("GET", `/v1/admin/employers?${params}`);
  }

  employerVerificationCounts(): Promise<EmployerVerificationCounts> {
    return this.request("GET", "/v1/admin/employers/counts");
  }

  verifyEmployer(employerId: string): Promise<EmployerVerificationRow> {
    return this.request("POST", `/v1/admin/employers/${employerId}/verify`);
  }

  rejectEmployer(employerId: string, reason: string): Promise<EmployerVerificationRow> {
    return this.request("POST", `/v1/admin/employers/${employerId}/reject`, { reason });
  }

  listMyJobs(status: "open" | "closed", cursor?: string): Promise<RecruiterJobsPage> {
    const params = new URLSearchParams({ status });
    if (cursor) params.set("cursor", cursor);
    return this.request("GET", `/v1/jobs/me?${params}`);
  }

  createJob(payload: JobCreate): Promise<JobRead> {
    return this.request("POST", "/v1/jobs", payload);
  }

  patchJob(jobId: string, payload: JobPatch): Promise<JobRead> {
    return this.request("PATCH", `/v1/jobs/${jobId}`, payload);
  }

  deleteJob(jobId: string): Promise<void> {
    return this.request("DELETE", `/v1/jobs/${jobId}`);
  }

  listJobApplicants(jobId: string, cursor?: string): Promise<ApplicantsOfJobPage> {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request("GET", `/v1/jobs/${jobId}/applicants${qs}`);
  }

  myEmployers(): Promise<EmployerRead[]> {
    return this.request("GET", "/v1/employers/me");
  }

  listMembers(employerId: string): Promise<MemberRead[]> {
    return this.request("GET", `/v1/employers/${employerId}/members`);
  }

  addMember(employerId: string, email: string, role: "owner" | "member"): Promise<MemberRead> {
    return this.request("POST", `/v1/employers/${employerId}/members`, { email, role });
  }

  changeMemberRole(
    employerId: string,
    memberUserId: string,
    role: "owner" | "member",
  ): Promise<MemberRead> {
    return this.request("PATCH", `/v1/employers/${employerId}/members/${memberUserId}`, { role });
  }

  removeMember(employerId: string, memberUserId: string): Promise<void> {
    return this.request("DELETE", `/v1/employers/${employerId}/members/${memberUserId}`);
  }

  listInvites(employerId: string): Promise<InviteRead[]> {
    return this.request("GET", `/v1/employers/${employerId}/invites`);
  }

  createInvite(employerId: string, email: string, role: "owner" | "member"): Promise<InviteRead> {
    return this.request("POST", `/v1/employers/${employerId}/invites`, { email, role });
  }

  revokeInvite(employerId: string, inviteId: string): Promise<void> {
    return this.request("DELETE", `/v1/employers/${employerId}/invites/${inviteId}`);
  }
}
