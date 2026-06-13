import { useCallback, useState } from "react";
import { Fragment } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { AuditLogFilters } from "../../api/types";
import { EmptyState, ErrorNotice, JsonView, ShortId, Stamp } from "../../components/bits";
import { usePagedFetch } from "../../paging/usePagedFetch";
import { useSession } from "../../session";

const EMPTY_FILTERS: AuditLogFilters = {};

/**
 * `datetime-local` inputs yield a naive local wall time ("2026-06-13T14:30", no
 * zone). The backend compares against a TIMESTAMPTZ column, so send a real UTC
 * instant: interpret the value in the browser's zone, then `.toISOString()`.
 */
function localToUtcIso(local: string | undefined): string | undefined {
  if (!local) return undefined;
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
}

function toApiFilters(filters: AuditLogFilters): AuditLogFilters {
  return { ...filters, from: localToUtcIso(filters.from), to: localToUtcIso(filters.to) };
}

export function AuditExplorer() {
  const { client } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  // Deep-link support: /admin/audit?actor=<uuid> from the user-actions page.
  const initial: AuditLogFilters = params.get("actor")
    ? { actor_user_id: params.get("actor")! }
    : EMPTY_FILTERS;
  const [draft, setDraft] = useState<AuditLogFilters>(initial);
  const [applied, setApplied] = useState<AuditLogFilters>(initial);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetcher = useCallback(
    (cursor: string | undefined) =>
      client.listAuditLogs({ ...toApiFilters(applied), cursor, limit: 50 }),
    [client, applied],
  );
  const { rows, nextCursor, busy, error, loadMore } = usePagedFetch(fetcher, JSON.stringify(applied));

  const set = (key: keyof AuditLogFilters) => (value: string) =>
    setDraft((d) => ({ ...d, [key]: value || undefined }));

  const pickUser = (id: string) => navigate(`/admin/users?user=${id}`);

  return (
    <>
      <div className="headline rise">
        <h1>
          AUDIT <span className="ghost">TRAIL</span>
        </h1>
        <div className="sub">
          <span className="flavor">Append-only. Every disclosure, every lever pulled.</span>
          <span className="chip acc">
            <span className="led amber" /> {rows.length} loaded
          </span>
        </div>
      </div>

      <form
        className="filters rise"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        <label className="field">
          <span className="k">action</span>
          <input
            placeholder="e.g. admin.user.suspended"
            value={draft.action ?? ""}
            onChange={(e) => set("action")(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="k">resource type</span>
          <input
            placeholder="user · job · resume…"
            value={draft.resource_type ?? ""}
            onChange={(e) => set("resource_type")(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="k">actor user id</span>
          <input
            placeholder="uuid"
            value={draft.actor_user_id ?? ""}
            onChange={(e) => set("actor_user_id")(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="k">resource id</span>
          <input
            placeholder="uuid"
            value={draft.resource_id ?? ""}
            onChange={(e) => set("resource_id")(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="k">from (local → utc)</span>
          <input
            type="datetime-local"
            value={draft.from ?? ""}
            onChange={(e) => set("from")(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="k">to (local → utc)</span>
          <input
            type="datetime-local"
            value={draft.to ?? ""}
            onChange={(e) => set("to")(e.target.value)}
          />
        </label>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <button className="btn primary" type="submit" disabled={busy}>
            Apply
          </button>
          <button
            className="btn ghost"
            type="button"
            onClick={() => {
              setDraft(EMPTY_FILTERS);
              setApplied(EMPTY_FILTERS);
            }}
          >
            Reset
          </button>
        </div>
      </form>

      <ErrorNotice error={error} />

      <div className="table-wrap rise">
        <table className="console">
          <thead>
            <tr>
              <th>When</th>
              <th>Action</th>
              <th>Actor</th>
              <th>Resource</th>
              <th className="r">Context</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Fragment key={row.id}>
                <tr
                  className="expandable"
                  onClick={() => setExpanded(expanded === row.id ? null : row.id)}
                >
                  <td style={{ whiteSpace: "nowrap" }}>
                    <Stamp iso={row.created_at} />
                  </td>
                  <td>
                    <span className={row.action.startsWith("admin.") ? "acc" : undefined}>
                      {row.action}
                    </span>
                  </td>
                  <td className="mono-id">
                    <span className="chip" style={{ marginRight: 8 }}>
                      {row.actor_role}
                    </span>
                    {row.actor_user_id ? (
                      <ShortId id={row.actor_user_id} onPick={pickUser} />
                    ) : (
                      <span className="dim">system</span>
                    )}
                  </td>
                  <td className="mono-id">
                    {row.resource_type ?? "—"}
                    {row.resource_id && (
                      <>
                        {" "}
                        <ShortId
                          id={row.resource_id}
                          onPick={row.resource_type === "user" ? pickUser : undefined}
                        />
                      </>
                    )}
                  </td>
                  <td className="r dim">{expanded === row.id ? "▾" : "▸"}</td>
                </tr>
                {expanded === row.id && (
                  <tr>
                    <td colSpan={5} style={{ background: "var(--bg0)" }}>
                      <JsonView value={row.context} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !busy && (
          <EmptyState>Nothing in the trail matches these filters.</EmptyState>
        )}
      </div>

      <div className="row mt">
        {nextCursor && (
          <button className="btn" disabled={busy} onClick={loadMore}>
            {busy ? "Loading…" : "Load older entries"}
          </button>
        )}
        {!nextCursor && rows.length > 0 && <span className="k">end of trail</span>}
      </div>
    </>
  );
}
