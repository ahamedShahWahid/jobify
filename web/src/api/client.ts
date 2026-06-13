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

export class HttpClient implements JobifyClient {
  readonly mode = "live" as const;

  /** In-flight single-flight refresh — concurrent 401s collapse onto one
   * /v1/auth/refresh call rather than each rotating the token separately. */
  private refreshInFlight: Promise<string> | null = null;

  constructor(
    private readonly store: TokenStore,
    /** Invoked when the session is unrecoverable (refresh failed, or a
     * non-refreshable 401) so the session layer can sign the user out. */
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
      const detail = await this.readDetail(res);
      const recoverable =
        detail === INVALID_ACCESS_TOKEN && this.store.refresh !== null && !isRetry;
      if (recoverable) {
        try {
          await this.refreshSingleFlight();
        } catch {
          this.onSignOut?.();
          throw new ApiError(401, detail);
        }
        return this.request<T>(method, path, body, true);
      }
      this.onSignOut?.();
      throw new ApiError(401, detail);
    }

    if (!res.ok) {
      throw new ApiError(res.status, await this.readDetail(res));
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
