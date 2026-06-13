import type {
  ApplicationListResponse,
  ApplicationRead,
  ConsentRead,
  FeedResponse,
  JobDetailResponse,
  MeResponse,
  SavedJobListResponse,
  SavedJobRead,
} from "./types";

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
  /** GET /v1/me/consents → the caller's consent rows. */
  getConsents(): Promise<ConsentRead[]>;
  /** PATCH /v1/me/consents/{scope} → the updated row (422 on unknown scope). */
  setConsent(scope: string, granted: boolean): Promise<ConsentRead>;
  /** POST /v1/me/dsr/export → the full export envelope as an opaque JSON object. */
  dsrExport(): Promise<unknown>;
  /** DELETE /v1/me/dsr → a DeleteReport; the account is tombstoned on success. */
  dsrDelete(): Promise<unknown>;
}

/** RFC 7807 problem+json error; `detail` is the API's user-visible slug/message. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return String(e);
}

function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) =>
        d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d),
      )
      .join("; ");
  }
  return null;
}

export class HttpClient implements JobifyClient {
  readonly mode = "live" as const;

  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
    /** Invoked on any 401 so the session layer can sign the user out globally. */
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
        /* non-JSON body — keep the status fallback */
      }
      if (res.status === 401) this.onUnauthorized?.();
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

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
    return this.request<ApplicationRead>("PATCH", `/v1/applications/${applicationId}`, {
      status: "withdrawn",
    });
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
    return this.request<ConsentRead>("PATCH", `/v1/me/consents/${encodeURIComponent(scope)}`, {
      granted,
    });
  }
  dsrExport() {
    // The attachment/Content-Disposition headers are irrelevant to fetch — the
    // request helper just returns the parsed JSON envelope.
    return this.request<unknown>("POST", "/v1/me/dsr/export");
  }
  dsrDelete() {
    return this.request<unknown>("DELETE", "/v1/me/dsr", { confirmation: "DELETE_MY_ACCOUNT" });
  }
}
