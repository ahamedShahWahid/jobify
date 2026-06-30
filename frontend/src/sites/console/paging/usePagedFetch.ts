// The console list screens (audit log, jobs, applicants, verification) use the
// canonical cursor-pagination hook from src/shared/hooks. Kept as a thin
// re-export so call sites need no churn.
export { usePagedFetch } from "../../../shared/hooks/usePagedFetch";
export type { Page, PagedFetch } from "../../../shared/hooks/usePagedFetch";
