/** RFC 7807 problem+json error; `detail` is the API's user-visible slug/message.
 *  `requestId` is the X-Request-Id correlation handle when the response carried one. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly requestId?: string,
  ) {
    super(detail);
  }
}

/** Turn any caught value into a display string — used in every page's catch. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return String(e);
}

/**
 * Render an RFC 7807 problem `detail` as one human string. Two shapes arrive:
 *  - HTTPException → `detail` is already a string.
 *  - 422 validation → FastAPI default `{detail: [{loc, msg, type}, ...]}`, flattened
 *    `loc.msg`-style so the UI never shows raw JSON.
 */
export function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === "object" && "msg" in d) {
          const item = d as { loc?: unknown; msg?: unknown };
          const loc = Array.isArray(item.loc) ? item.loc.filter((s) => s !== "body").join(".") : "";
          const msg = String(item.msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return JSON.stringify(d);
      })
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
 * `access` (and rotates `refresh`) in place, so every method picks up the new
 * access token without the client being rebuilt. `refresh` is null on the
 * paste-token path. Mirrors app/'s AccessTokenHolder. */
export class TokenStore {
  constructor(
    readonly baseUrl: string,
    public access: string,
    public refresh: string | null,
  ) {}
}

/** Shared bearer transport with the 401 single-flight refresh ladder. Surface
 * clients EXTEND this and implement their typed endpoint methods by calling
 * `this.request(...)`. */
export class BaseHttpClient {
  readonly mode = "live" as const;

  /** In-flight single-flight refresh — concurrent 401s collapse onto one
   * /v1/auth/refresh call rather than each rotating the token separately. */
  private refreshInFlight: Promise<string> | null = null;

  constructor(
    protected readonly store: TokenStore,
    /** Invoked when the session is unrecoverable (refresh failed, or a
     * non-refreshable 401) so the session layer can sign the user out. */
    private readonly onSignOut?: () => void,
  ) {}

  protected async request<T>(method: string, path: string, body?: unknown, isRetry = false): Promise<T> {
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

    // 401 ladder: only `invalid_access_token`, with a refresh token, on the FIRST
    // attempt is recoverable — refresh once then replay the original request once.
    if (res.status === 401) {
      const requestId = res.headers.get("X-Request-Id") ?? undefined;
      const detail = await this.readDetail(res);
      const recoverable = detail === INVALID_ACCESS_TOKEN && this.store.refresh !== null && !isRetry;
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
      throw new ApiError(res.status, await this.readDetail(res), res.headers.get("X-Request-Id") ?? undefined);
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
   * is cleared BEFORE the promise settles (awaiters already hold it). Mirrors
   * app/'s `_inFlight = null` BEFORE `complete()` ordering. */
  private refreshSingleFlight(): Promise<string> {
    if (this.refreshInFlight) return this.refreshInFlight;
    const inFlight = this.doRefresh().finally(() => {
      this.refreshInFlight = null;
    });
    this.refreshInFlight = inFlight;
    return inFlight;
  }

  /** POST /v1/auth/refresh — rotates the refresh token on every call. A plain
   * fetch (never routed through request()) so a 401 here can't recurse. */
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
}
