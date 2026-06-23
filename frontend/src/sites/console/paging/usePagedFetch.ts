import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client";

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface PagedFetch<T> {
  rows: T[];
  nextCursor: string | null;
  busy: boolean;
  error: string | null;
  loadMore: () => void;
  reload: () => void;
}

/**
 * Cursor-pagination state machine shared by every list screen (audit log, jobs,
 * applicants). The caller supplies a `fetcher` (closing over client + filters)
 * and a `resetKey` string; whenever the key changes the list resets and reloads
 * from the first page.
 *
 * A monotonically-increasing `seq` ticket guards against out-of-order responses:
 * if the operator flips a filter while a page is in flight, the slower response
 * is discarded instead of clobbering the newer one (a race the three hand-rolled
 * copies all had).
 */
export function usePagedFetch<T>(
  fetcher: (cursor: string | undefined) => Promise<Page<T>>,
  resetKey: string,
): PagedFetch<T> {
  const [rows, setRows] = useState<T[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the latest fetcher without making `load` depend on it (callers pass a
  // fresh closure every render); cursorRef lets loadMore read the current cursor.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const cursorRef = useRef<string | null>(null);
  const seq = useRef(0);

  const load = useCallback(async (cursor: string | null, append: boolean) => {
    const ticket = ++seq.current;
    setBusy(true);
    setError(null);
    try {
      const page = await fetcherRef.current(cursor ?? undefined);
      if (ticket !== seq.current) return; // superseded by a newer load
      cursorRef.current = page.next_cursor;
      setNextCursor(page.next_cursor);
      setRows((prev) => (append ? [...prev, ...page.items] : page.items));
    } catch (e) {
      if (ticket === seq.current) setError(errorMessage(e));
    } finally {
      if (ticket === seq.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    cursorRef.current = null;
    void load(null, false);
  }, [load, resetKey]);

  const loadMore = useCallback(() => void load(cursorRef.current, true), [load]);
  const reload = useCallback(() => void load(null, false), [load]);

  return { rows, nextCursor, busy, error, loadMore, reload };
}
