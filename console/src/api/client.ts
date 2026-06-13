import type {
  AdminUserRead,
  ApplicantsOfJobPage,
  AuditLogFilters,
  AuditLogListResponse,
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
export interface ConsoleClient {
  readonly mode: "live" | "demo";

  me(): Promise<MeResponse>;

  // admin
  listAuditLogs(filters: AuditLogFilters): Promise<AuditLogListResponse>;
  suspendUser(userId: string, reason: string): Promise<AdminUserRead>;
  unsuspendUser(userId: string): Promise<AdminUserRead>;

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

/** RFC 7807 problem+json error; `detail` is the API's user-visible slug/message. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly requestId?: string,
  ) {
    super(detail);
  }
}

/** Uniform "turn any caught value into a display string" — used in every page's catch. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return String(e);
}

/**
 * Render an error body's `detail` as one human string. Two shapes arrive:
 *  - HTTPException → problem+json, `detail` is already a string.
 *  - 422 validation → FastAPI default `{detail: [{loc, msg, type}, ...]}` (no
 *    custom handler in this API), which must be flattened or the UI shows raw JSON.
 */
function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      if (d && typeof d === "object" && "msg" in d) {
        const item = d as { loc?: unknown; msg?: unknown };
        const loc = Array.isArray(item.loc)
          ? item.loc.filter((s) => s !== "body").join(".")
          : "";
        const msg = String(item.msg);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return JSON.stringify(d);
    });
    return parts.join("; ");
  }
  return null;
}

export class HttpClient implements ConsoleClient {
  readonly mode = "live" as const;

  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
    /** Invoked on any 401 so the session layer can sign the operator out globally. */
    private readonly onUnauthorized?: () => void,
  ) {}

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${this.token}`,
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new ApiError(0, `network error — is the API reachable at ${this.baseUrl}?`);
    }
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const problem = (await res.json()) as { detail?: unknown; title?: unknown };
        detail = formatDetail(problem.detail) ?? formatDetail(problem.title) ?? detail;
      } catch {
        /* non-JSON error body — keep the status fallback */
      }
      // A token that expired mid-session (≤10 min TTL) lands here on every call;
      // tell the session layer once so it can clear state and route to sign-in.
      if (res.status === 401) this.onUnauthorized?.();
      throw new ApiError(res.status, detail, res.headers.get("X-Request-Id") ?? undefined);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

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

  suspendUser(userId: string, reason: string): Promise<AdminUserRead> {
    return this.request("POST", `/v1/admin/users/${userId}/suspend`, { reason });
  }

  unsuspendUser(userId: string): Promise<AdminUserRead> {
    return this.request("DELETE", `/v1/admin/users/${userId}/suspend`);
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
