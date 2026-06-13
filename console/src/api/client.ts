import type {
  AdminUserRead,
  ApplicantsOfJobPage,
  AuditLogFilters,
  AuditLogListResponse,
  EmployerRead,
  EmployerVerificationPage,
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
  suspendUser(userId: string, reason: string): Promise<AdminUserRead>;
  unsuspendUser(userId: string): Promise<AdminUserRead>;

  // admin · employer verification queue (GET/POST /v1/admin/employers, migration 0020)
  listEmployersForVerification(
    status: EmployerVerificationStatus,
    cursor?: string,
  ): Promise<EmployerVerificationPage>;
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

/** The single 401 slug a token refresh can recover from. Every other 401
 * (`missing_bearer_token`, `user_not_found`, `user_suspended`, an unknown future
 * slug) is structurally unrecoverable → sign out. Mirrors app/'s
 * RefreshOn401Interceptor, which only refreshes on `invalid_access_token`. */
const INVALID_ACCESS_TOKEN = "invalid_access_token";

/** Mutable holder for the live session's tokens. The refresh-on-401 path mutates
 * `access` (and rotates `refresh`) in place, so every HttpClient method picks up
 * the new access token without the client being rebuilt. `refresh` is null on the
 * paste-token path (no refresh possible → a 401 just signs out). Mirrors app/'s
 * AccessTokenHolder. */
export class TokenStore {
  constructor(
    readonly baseUrl: string,
    public access: string,
    public refresh: string | null,
  ) {}
}

export class HttpClient implements ConsoleClient {
  readonly mode = "live" as const;

  /** In-flight single-flight refresh — concurrent 401s collapse onto one
   * /v1/auth/refresh call rather than each rotating the token separately. */
  private refreshInFlight: Promise<string> | null = null;

  constructor(
    private readonly store: TokenStore,
    /** Invoked when the session is unrecoverable (refresh failed, or a
     * non-refreshable 401) so the session layer can sign the operator out. */
    private readonly onSignOut?: () => void,
  ) {}

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    isRetry = false,
  ): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.store.baseUrl}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${this.store.access}`,
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new ApiError(0, `network error — is the API reachable at ${this.store.baseUrl}?`);
    }

    // 401 ladder (mirrors app/ RefreshOn401Interceptor): only `invalid_access_token`,
    // with a refresh token, on the FIRST attempt is recoverable — refresh once then
    // replay the original request once. A replay that 401s again, a non-refreshable
    // slug, or the absence of a refresh token all sign out.
    if (res.status === 401) {
      const requestId = res.headers.get("X-Request-Id") ?? undefined;
      const detail = await this.readDetail(res);
      const recoverable =
        detail === INVALID_ACCESS_TOKEN && this.store.refresh !== null && !isRetry;
      if (recoverable) {
        try {
          await this.refreshSingleFlight();
        } catch {
          this.onSignOut?.();
          throw new ApiError(401, detail, requestId);
        }
        return this.request<T>(method, path, body, true);
      }
      this.onSignOut?.();
      throw new ApiError(401, detail, requestId);
    }

    if (!res.ok) {
      throw new ApiError(
        res.status,
        await this.readDetail(res),
        res.headers.get("X-Request-Id") ?? undefined,
      );
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  /** RFC 7807 problem+json `detail` (or `title`) as a display string. */
  private async readDetail(res: Response): Promise<string> {
    try {
      const problem = (await res.json()) as { detail?: unknown; title?: unknown };
      return formatDetail(problem.detail) ?? formatDetail(problem.title) ?? `HTTP ${res.status}`;
    } catch {
      return `HTTP ${res.status}`;
    }
  }

  /** Single-flight refresh. Concurrent 401s share one in-flight promise; the slot
   * is cleared BEFORE the promise settles (awaiters already hold it), so the next
   * 401 starts a fresh refresh — mirrors app/'s `_inFlight = null` BEFORE
   * `complete()` ordering. */
  private refreshSingleFlight(): Promise<string> {
    if (this.refreshInFlight) return this.refreshInFlight;
    const inFlight = this.doRefresh().finally(() => {
      this.refreshInFlight = null;
    });
    this.refreshInFlight = inFlight;
    return inFlight;
  }

  /** POST /v1/auth/refresh — rotates the refresh token on every call. A plain
   * fetch (never routed through request()) so a 401 here can't recurse into a
   * refresh; mirrors app/'s kSkipAuth on the refresh request. */
  private async doRefresh(): Promise<string> {
    if (this.store.refresh === null) throw new ApiError(401, "no_refresh_token");
    let res: Response;
    try {
      res = await fetch(`${this.store.baseUrl}/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.store.refresh }),
      });
    } catch {
      throw new ApiError(0, "network error during token refresh");
    }
    if (!res.ok) throw new ApiError(res.status, "token refresh failed");
    const data = (await res.json()) as { access_token: string; refresh_token: string };
    this.store.access = data.access_token;
    this.store.refresh = data.refresh_token; // rotation — persist the new refresh token
    return data.access_token;
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
