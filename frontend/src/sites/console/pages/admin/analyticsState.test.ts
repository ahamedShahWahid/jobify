import { describe, expect, it } from "vitest";
import { analyticsRequestState } from "./analyticsState";

describe("analyticsRequestState", () => {
  it("stops loading when the initial request fails", () => {
    expect(analyticsRequestState(null, "unavailable")).toBe("error");
  });

  it("distinguishes loading and ready data", () => {
    expect(analyticsRequestState(null, null)).toBe("loading");
    expect(analyticsRequestState({} as never, null)).toBe("ready");
  });
});
