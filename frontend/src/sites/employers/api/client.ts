import { BaseHttpClient } from "../../../shared/api/transport";
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";

import type {
  ApplicantsOfJobPage,
  EmployerCreate,
  EmployerRead,
  InviteRead,
  JobCreate,
  JobPatch,
  JobRead,
  MeResponse,
  MemberRead,
  RecruiterJobsPage,
} from "./types";

/** One interface, two impls: HttpClient (live API) and DemoClient (fixtures). */
export interface EmployerClient {
  readonly mode: "live" | "demo";

  me(): Promise<MeResponse>;

  listMyJobs(status: "open" | "closed", cursor?: string): Promise<RecruiterJobsPage>;
  createJob(payload: JobCreate): Promise<JobRead>;
  patchJob(jobId: string, payload: JobPatch): Promise<JobRead>;
  deleteJob(jobId: string): Promise<void>;
  listJobApplicants(jobId: string, cursor?: string): Promise<ApplicantsOfJobPage>;

  myEmployers(): Promise<EmployerRead[]>;
  createEmployer(payload: EmployerCreate): Promise<EmployerRead>;
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

export class HttpClient extends BaseHttpClient implements EmployerClient {
  me(): Promise<MeResponse> {
    return this.request("GET", "/v1/me");
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

  createEmployer(payload: EmployerCreate): Promise<EmployerRead> {
    return this.request("POST", "/v1/employers", payload);
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
