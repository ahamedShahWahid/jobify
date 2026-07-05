import type { EmployerClient } from "./client";
import type { RecruiterJobRow } from "./types";

/**
 * Shared cursor-drain helpers over `listMyJobs`. Both the dashboard totals and
 * the composer's cold-deep-link edit resolution need to walk a recruiter's full
 * posting list; this is the single bounded implementation so the page cap and
 * cursor contract live in one place.
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

/**
 * Find a posting by id across the recruiter's full list, stopping at the first
 * hit (no need to drain everything once found). Walks both "open" and "closed"
 * explicitly rather than relying on a single ?status=closed call (which already
 * returns the full open+closed view) so this doesn't depend on that filter
 * detail. Only reached on a cold deep-link to the editor; normal edits hand the
 * row over via router state.
 */
export async function findMyJob(
  client: EmployerClient,
  jobId: string,
): Promise<RecruiterJobRow | null> {
  for (const status of ["open", "closed"] as const) {
    let cursor: string | undefined;
    for (let page = 0; page < MAX_JOB_PAGES; page++) {
      const res = await client.listMyJobs(status, cursor);
      const hit = res.items.find((j) => j.id === jobId);
      if (hit) return hit;
      if (!res.next_cursor) break;
      cursor = res.next_cursor;
    }
  }
  return null;
}
