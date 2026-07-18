import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, BaseHttpClient, TokenStore } from "./transport";

class TestClient extends BaseHttpClient {
  get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BaseHttpClient auth recovery", () => {
  it("collapses concurrent invalid-token responses onto one rotating refresh", async () => {
    let releaseRefresh: (() => void) | undefined;
    const refreshGate = new Promise<void>((resolve) => {
      releaseRefresh = resolve;
    });
    let refreshCalls = 0;
    let protectedCalls = 0;

    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/auth/refresh")) {
        refreshCalls += 1;
        await refreshGate;
        return jsonResponse(200, {
          access_token: "access-2",
          refresh_token: "refresh-2",
        });
      }
      protectedCalls += 1;
      const authorization = (init?.headers as Record<string, string>).Authorization;
      if (authorization === "Bearer access-1") {
        return jsonResponse(401, { detail: "invalid_access_token" });
      }
      return jsonResponse(200, { path: url, authorization });
    });
    vi.stubGlobal("fetch", fetchMock);

    const store = new TokenStore("https://api.example", "access-1", "refresh-1");
    const client = new TestClient(store);
    const first = client.get<{ authorization: string }>("/v1/one");
    const second = client.get<{ authorization: string }>("/v1/two");

    await vi.waitFor(() => expect(refreshCalls).toBe(1));
    releaseRefresh?.();
    const results = await Promise.all([first, second]);

    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(4);
    expect(results.map((row) => row.authorization)).toEqual([
      "Bearer access-2",
      "Bearer access-2",
    ]);
    expect(store.refresh).toBe("refresh-2");
  });

  it("signs out without refreshing for a structurally invalid session", async () => {
    const onSignOut = vi.fn();
    const fetchMock = vi.fn(async () => jsonResponse(401, { detail: "user_suspended" }));
    vi.stubGlobal("fetch", fetchMock);

    const client = new TestClient(
      new TokenStore("https://api.example", "access-1", "refresh-1"),
      onSignOut,
    );

    await expect(client.get("/v1/me")).rejects.toMatchObject({
      status: 401,
      detail: "user_suspended",
    } satisfies Partial<ApiError>);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(onSignOut).toHaveBeenCalledOnce();
  });
});
