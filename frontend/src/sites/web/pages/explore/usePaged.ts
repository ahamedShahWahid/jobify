// The web Explore lists (feed / applied / saved / inbox / applications) use the
// canonical cursor-pagination hook from src/shared/hooks. Kept as a thin
// re-export under the historical `usePaged` name so call sites need no churn.
export { usePagedFetch as usePaged } from "../../../../shared/hooks/usePagedFetch";
export type { Page, PagedFetch } from "../../../../shared/hooks/usePagedFetch";
