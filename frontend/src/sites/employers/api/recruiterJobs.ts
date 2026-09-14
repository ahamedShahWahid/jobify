import type { EmployerClient } from "./client";
import type { RecruiterJobRow } from "./types";

/**
 * Shared cursor-drain helper over `listMyJobs`, for the dashboard totals
 * (the one remaining caller that needs a recruiter's full posting list —
 * the composer's edit flow now always fetches one job by id via
 * EmployerClient.getMyJob, never drains the list; see JobComposer.tsx).
 */

// Bound so a misbehaving cursor can't loop forever (≈1000 jobs at page size 20).
export const MAX_JOB_PAGES = 50;

/** Walk every page of one status into a single array. */
export async function drainJobs(
  client: EmployerClient,
  status: "open" | "closed",
): Promise<RecruiterJobRow[]> {
  const all: RecruiterJobRow[] = [];
  let cursor: string | undefined;
  for (let page = 0; page < MAX_JOB_PAGES; page++) {
    const res = await client.listMyJobs(status, cursor);
    all.push(...res.items);
    if (!res.next_cursor) break;
    cursor = res.next_cursor;
  }
  return all;
}
