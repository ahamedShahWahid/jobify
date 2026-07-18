import type { AdminAnalyticsSummary } from "../../api/types";

export function analyticsRequestState(
  summary: AdminAnalyticsSummary | null,
  error: string | null,
): "loading" | "ready" | "error" {
  if (summary !== null) return "ready";
  if (error !== null) return "error";
  return "loading";
}
