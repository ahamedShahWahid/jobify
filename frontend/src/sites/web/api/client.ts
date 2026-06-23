import { BaseHttpClient } from "../../../shared/api/transport";
import type {
  AcceptResult,
  ApplicationListResponse,
  ApplicationRead,
  ConsentRead,
  FeedResponse,
  JobDetailResponse,
  MeResponse,
  MyInviteRead,
  NotificationListResponse,
  NotificationRead,
  SavedJobListResponse,
  SavedJobRead,
} from "./types";

// Re-export the shared transport surface so existing page imports
// (`import { errorMessage, ApiError, TokenStore } from "../api/client"`) keep working.
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";

/** One interface, two impls: HttpClient (live /v1) and DemoClient (fixtures). */
export interface JobifyClient {
  readonly mode: "live" | "demo";
  me(): Promise<MeResponse>;
  feed(cursor?: string): Promise<FeedResponse>;
  job(jobId: string): Promise<JobDetailResponse>;
  apply(jobId: string): Promise<ApplicationRead>;
  withdraw(applicationId: string): Promise<ApplicationRead>;
  save(jobId: string): Promise<SavedJobRead>;
  unsave(jobId: string): Promise<void>;
  applications(cursor?: string): Promise<ApplicationListResponse>;
  saved(cursor?: string): Promise<SavedJobListResponse>;
  getConsents(): Promise<ConsentRead[]>;
  setConsent(scope: string, granted: boolean): Promise<ConsentRead>;
  dsrExport(): Promise<unknown>;
  dsrDelete(): Promise<unknown>;
  notifications(cursor?: string): Promise<NotificationListResponse>;
  markNotificationRead(notificationId: string): Promise<NotificationRead>;
  myInvites(): Promise<MyInviteRead[]>;
  acceptInvite(inviteId: string): Promise<AcceptResult>;
  declineInvite(inviteId: string): Promise<AcceptResult>;
}

export class HttpClient extends BaseHttpClient implements JobifyClient {
  me() {
    return this.request<MeResponse>("GET", "/v1/me");
  }
  feed(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<FeedResponse>("GET", `/v1/feed${qs}`);
  }
  job(jobId: string) {
    return this.request<JobDetailResponse>("GET", `/v1/jobs/${jobId}`);
  }
  apply(jobId: string) {
    return this.request<ApplicationRead>("POST", `/v1/jobs/${jobId}/apply`, { source: "web" });
  }
  withdraw(applicationId: string) {
    return this.request<ApplicationRead>("PATCH", `/v1/applications/${applicationId}`, { status: "withdrawn" });
  }
  save(jobId: string) {
    return this.request<SavedJobRead>("POST", `/v1/jobs/${jobId}/save`);
  }
  unsave(jobId: string) {
    return this.request<void>("DELETE", `/v1/jobs/${jobId}/save`);
  }
  applications(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<ApplicationListResponse>("GET", `/v1/applications${qs}`);
  }
  saved(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<SavedJobListResponse>("GET", `/v1/saved${qs}`);
  }
  async getConsents() {
    const res = await this.request<{ items: ConsentRead[] }>("GET", "/v1/me/consents");
    return res.items;
  }
  setConsent(scope: string, granted: boolean) {
    return this.request<ConsentRead>("PATCH", `/v1/me/consents/${encodeURIComponent(scope)}`, { granted });
  }
  dsrExport() {
    return this.request<unknown>("POST", "/v1/me/dsr/export");
  }
  dsrDelete() {
    return this.request<unknown>("DELETE", "/v1/me/dsr", { confirmation: "DELETE_MY_ACCOUNT" });
  }
  notifications(cursor?: string) {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<NotificationListResponse>("GET", `/v1/notifications${qs}`);
  }
  markNotificationRead(notificationId: string) {
    return this.request<NotificationRead>("POST", `/v1/notifications/${encodeURIComponent(notificationId)}/read`);
  }
  myInvites() {
    return this.request<MyInviteRead[]>("GET", "/v1/me/invites");
  }
  acceptInvite(inviteId: string) {
    return this.request<AcceptResult>("POST", `/v1/me/invites/${encodeURIComponent(inviteId)}/accept`);
  }
  declineInvite(inviteId: string) {
    return this.request<AcceptResult>("POST", `/v1/me/invites/${encodeURIComponent(inviteId)}/decline`);
  }
}
