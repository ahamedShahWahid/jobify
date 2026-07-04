import { BaseHttpClient } from "../../../shared/api/transport";
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";

import type {
  AdminUserRead,
  AuditLogFilters,
  AuditLogListResponse,
  EmployerVerificationPage,
  EmployerVerificationRow,
  EmployerVerificationStatus,
  MeResponse,
} from "./types";

/** One interface, two impls: HttpClient (live API) and DemoClient (fixtures). */
export interface ConsoleClient {
  readonly mode: "live" | "demo";

  me(): Promise<MeResponse>;

  listAuditLogs(filters: AuditLogFilters): Promise<AuditLogListResponse>;
  suspendUser(userId: string, reason: string): Promise<AdminUserRead>;
  unsuspendUser(userId: string): Promise<AdminUserRead>;

  // Employer verification review (admin) — GET /v1/admin/employers (status filter
  // + cursor), POST .../{id}/verify, POST .../{id}/reject {reason}. The live
  // response is AdminEmployerRead {id,name,gst,status,created_at,reviewed_at,reason};
  // the demo-only domain/contact_email/reviewer fields are absent here.
  listEmployersForVerification(
    status: EmployerVerificationStatus,
    cursor?: string,
  ): Promise<EmployerVerificationPage>;
  verifyEmployer(employerId: string): Promise<EmployerVerificationRow>;
  rejectEmployer(employerId: string, reason: string): Promise<EmployerVerificationRow>;
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

  suspendUser(userId: string, reason: string): Promise<AdminUserRead> {
    return this.request("POST", `/v1/admin/users/${userId}/suspend`, { reason });
  }

  unsuspendUser(userId: string): Promise<AdminUserRead> {
    return this.request("DELETE", `/v1/admin/users/${userId}/suspend`);
  }

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
}
