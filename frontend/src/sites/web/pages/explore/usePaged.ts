import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../../api/client";

interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

/** Compact cursor-pagination hook for the Explore lists (feed / applied / saved). */
export function usePaged<T>(
  fetcher: (cursor: string | undefined) => Promise<Page<T>>,
  resetKey: string,
) {
  const [rows, setRows] = useState<T[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      if (ticket !== seq.current) return;
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
