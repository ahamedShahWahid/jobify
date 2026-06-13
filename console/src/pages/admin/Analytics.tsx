import { useEffect, useMemo, useRef, useState } from "react";
import type { ConsoleClient } from "../../api/client";
import { errorMessage } from "../../api/client";
import type { AuditLogRead } from "../../api/types";
import { EmptyState, ErrorNotice } from "../../components/bits";
import { useSession } from "../../session";

/**
 * Admins have exactly ONE read endpoint — `listAuditLogs`. Every chart on this
 * page is derived purely from that stream: we drain it (bounded), then bucket
 * and aggregate in the browser. No analytics endpoint exists, and inventing one
 * would lie about the backend contract.
 *
 * Bounded like the recruiter dashboard's drainJobs: a misbehaving cursor must
 * not loop forever. If we hit the cap we surface "most recent N events" rather
 * than silently truncate.
 */
const MAX_PAGES = 40;
const PAGE_LIMIT = 100;

interface Drained {
  rows: AuditLogRead[];
  capped: boolean;
}

async function drainAuditLogs(client: ConsoleClient): Promise<Drained> {
  const rows: AuditLogRead[] = [];
  let cursor: string | undefined;
  for (let page = 0; page < MAX_PAGES; page++) {
    const res = await client.listAuditLogs({ cursor, limit: PAGE_LIMIT });
    rows.push(...res.items);
    if (!res.next_cursor) return { rows, capped: false };
    cursor = res.next_cursor;
  }
  // Drained MAX_PAGES and the cursor still pointed onward.
  return { rows, capped: true };
}

// ---- derivation helpers (pure; all memoized off `rows`) ----------

const DAY_MS = 86_400_000;

/** YYYY-MM-DD bucket key in UTC, so days line up with the audit log's instants. */
function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

interface DayBucket {
  key: string;
  count: number;
}

/** One bucket per calendar day across the full span (gaps filled with 0). */
function bucketByDay(rows: AuditLogRead[]): DayBucket[] {
  if (rows.length === 0) return [];
  const counts = new Map<string, number>();
  let min = Infinity;
  let max = -Infinity;
  for (const row of rows) {
    const key = dayKey(row.created_at);
    counts.set(key, (counts.get(key) ?? 0) + 1);
    const t = Date.parse(`${key}T00:00:00Z`);
    if (t < min) min = t;
    if (t > max) max = t;
  }
  const out: DayBucket[] = [];
  for (let t = min; t <= max; t += DAY_MS) {
    const key = new Date(t).toISOString().slice(0, 10);
    out.push({ key, count: counts.get(key) ?? 0 });
  }
  return out;
}

interface Tally {
  label: string;
  count: number;
}

function tally(rows: AuditLogRead[], pick: (r: AuditLogRead) => string): Tally[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const label = pick(row);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count);
}

function countAction(rows: AuditLogRead[], action: string): number {
  return rows.reduce((n, r) => (r.action === action ? n + 1 : n), 0);
}

const FUNNEL_STEPS: Array<{ action: string; label: string }> = [
  { action: "auth.signed_in", label: "Signed in" },
  { action: "resume.uploaded", label: "Resume uploaded" },
  { action: "resume.parsed", label: "Resume parsed" },
  { action: "application.created", label: "Application created" },
];

const ROLE_ORDER = ["applicant", "recruiter", "admin", "system"];

function fmtPct(n: number): string {
  return `${(n * 100).toFixed(n >= 1 ? 0 : 1)}%`;
}

function fmtDay(key: string): string {
  // "2026-06-13" → "Jun 13"
  const d = new Date(`${key}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

// ---- the activity sparkline (hand-rolled SVG, zero deps) ---------

const CHART_H = 132;
const CHART_PAD = 10;

function ActivityChart({ buckets }: { buckets: DayBucket[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setWidth(Math.round(w));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const max = Math.max(1, ...buckets.map((b) => b.count));
  const peak = buckets.reduce((a, b) => (b.count > a.count ? b : a), buckets[0]);

  const innerW = Math.max(1, width - CHART_PAD * 2);
  const innerH = CHART_H - CHART_PAD * 2;
  // Single-bucket case: a lone point can't draw a line, so plot it centred.
  const x = (i: number) =>
    CHART_PAD + (buckets.length <= 1 ? innerW / 2 : (i / (buckets.length - 1)) * innerW);
  const y = (count: number) => CHART_PAD + innerH - (count / max) * innerH;

  const line = buckets.map((b, i) => `${x(i).toFixed(1)},${y(b.count).toFixed(1)}`).join(" ");
  const area =
    buckets.length > 0
      ? `M ${x(0).toFixed(1)} ${(CHART_H - CHART_PAD).toFixed(1)} ` +
        buckets.map((b, i) => `L ${x(i).toFixed(1)} ${y(b.count).toFixed(1)}`).join(" ") +
        ` L ${x(buckets.length - 1).toFixed(1)} ${(CHART_H - CHART_PAD).toFixed(1)} Z`
      : "";

  return (
    <div className="chart" ref={wrapRef}>
      <svg
        viewBox={`0 0 ${width} ${CHART_H}`}
        width="100%"
        height={CHART_H}
        preserveAspectRatio="none"
        role="img"
        aria-label="Audit events per day"
      >
        {/* hairline baseline */}
        <line
          x1={CHART_PAD}
          y1={CHART_H - CHART_PAD}
          x2={width - CHART_PAD}
          y2={CHART_H - CHART_PAD}
          className="chart-axis"
        />
        {area && <path d={area} className="chart-area" />}
        {buckets.length > 1 && <polyline points={line} className="chart-line" fill="none" />}
        {buckets.map((b, i) => (
          <circle
            key={b.key}
            cx={x(i)}
            cy={y(b.count)}
            r={b.key === peak.key ? 3 : 1.6}
            className={b.key === peak.key ? "chart-dot peak" : "chart-dot"}
          >
            <title>{`${b.key}: ${b.count} events`}</title>
          </circle>
        ))}
      </svg>
      <div className="chart-axislabels">
        <span className="k num">{buckets.length > 0 ? fmtDay(buckets[0].key) : "—"}</span>
        <span className="k num dim">
          peak {peak ? `${peak.count} · ${fmtDay(peak.key)}` : "—"}
        </span>
        <span className="k num">
          {buckets.length > 0 ? fmtDay(buckets[buckets.length - 1].key) : "—"}
        </span>
      </div>
    </div>
  );
}

// ---- page --------------------------------------------------------

export function Analytics() {
  const { client } = useSession();
  const [drained, setDrained] = useState<Drained | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await drainAuditLogs(client);
        if (!cancelled) setDrained(result);
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  const rows = drained?.rows ?? [];
  const loading = drained === null;

  const stats = useMemo(() => {
    if (rows.length === 0) {
      return {
        total: 0,
        actors: 0,
        last24h: 0,
        systemShare: 0,
        spanStart: null as string | null,
        spanEnd: null as string | null,
        spanDays: 0,
      };
    }
    const actors = new Set<string>();
    let last24h = 0;
    let system = 0;
    let minT = Infinity;
    let maxT = -Infinity;
    const cutoff = Date.now() - DAY_MS;
    for (const row of rows) {
      if (row.actor_user_id) actors.add(row.actor_user_id);
      const t = Date.parse(row.created_at);
      if (t >= cutoff) last24h += 1;
      if (row.actor_role === "system") system += 1;
      if (t < minT) minT = t;
      if (t > maxT) maxT = t;
    }
    return {
      total: rows.length,
      actors: actors.size,
      last24h,
      systemShare: system / rows.length,
      spanStart: new Date(minT).toISOString(),
      spanEnd: new Date(maxT).toISOString(),
      spanDays: Math.max(1, Math.round((maxT - minT) / DAY_MS) + 1),
    };
  }, [rows]);

  const buckets = useMemo(() => bucketByDay(rows), [rows]);
  const roleMix = useMemo(() => {
    const counts = tally(rows, (r) => r.actor_role);
    // Stable, meaningful order; unknown roles appended after.
    const known = ROLE_ORDER.map((role) => counts.find((c) => c.label === role)).filter(
      (c): c is Tally => c !== undefined,
    );
    const extra = counts.filter((c) => !ROLE_ORDER.includes(c.label));
    return [...known, ...extra];
  }, [rows]);
  const actions = useMemo(() => tally(rows, (r) => r.action), [rows]);

  const funnel = useMemo(() => {
    const steps = FUNNEL_STEPS.map((step) => ({
      ...step,
      count: countAction(rows, step.action),
    }));
    const top = Math.max(1, steps[0]?.count ?? 0);
    return steps.map((step, i) => {
      const prev = i === 0 ? null : steps[i - 1].count;
      const stepPct = prev && prev > 0 ? step.count / prev : null;
      return { ...step, widthPct: (step.count / top) * 100, stepPct };
    });
  }, [rows]);

  const compliance = useMemo(
    () => ({
      dsrRequested: countAction(rows, "user.dsr_export_requested"),
      dsrCompleted: countAction(rows, "user.dsr_export_completed"),
      suspended: countAction(rows, "admin.user.suspended"),
      unsuspended: countAction(rows, "admin.user.unsuspended"),
      consentUpdates: countAction(rows, "consent.updated"),
    }),
    [rows],
  );

  const actionMax = actions[0]?.count ?? 1;

  return (
    <>
      <div className="headline rise">
        <h1>
          AUDIT <span className="ghost">PULSE</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            One stream, read many ways. Everything below is derived from the audit trail itself —
            no second source.
          </span>
          {!loading && rows.length > 0 && (
            <span className="chip acc">
              <span className="led amber" /> {stats.total} events · {stats.spanDays}d
            </span>
          )}
          {drained?.capped && (
            <span className="chip danger" title="Cursor exceeded the page cap">
              most recent {stats.total}
            </span>
          )}
        </div>
      </div>

      <ErrorNotice error={error} />

      {!loading && rows.length === 0 && !error ? (
        <EmptyState>The audit trail is empty — nothing to chart yet.</EmptyState>
      ) : (
        <>
          <div className="tiles rise mb">
            <div className="tile">
              <span className="k">events analyzed</span>
              <div className="value acc num">{loading ? "·" : stats.total}</div>
            </div>
            <div className="tile">
              <span className="k">distinct actors</span>
              <div className="value num">{loading ? "·" : stats.actors}</div>
            </div>
            <div className="tile">
              <span className="k">last 24h</span>
              <div className="value num">{loading ? "·" : stats.last24h}</div>
            </div>
            <div className="tile">
              <span className="k">system-actor share</span>
              <div className="value num">{loading ? "·" : fmtPct(stats.systemShare)}</div>
            </div>
          </div>

          <div className="panel rise mb">
            <div className="panel-head">
              <span className="k">activity · events per day</span>
              <span className="k num dim">
                {loading
                  ? "draining…"
                  : stats.spanStart && stats.spanEnd
                    ? `${stats.spanStart.slice(0, 10)} → ${stats.spanEnd.slice(0, 10)}`
                    : "—"}
              </span>
            </div>
            <div className="panel-body">
              {loading ? (
                <div className="chart-skeleton k">·</div>
              ) : (
                <ActivityChart buckets={buckets} />
              )}
            </div>
          </div>

          <div className="analytics-grid rise mb">
            <div className="panel">
              <div className="panel-head">
                <span className="k">the funnel</span>
                <span className="k dim">event counts · analyzed window</span>
              </div>
              <div className="panel-body">
                <div className="funnel">
                  {funnel.map((step) => (
                    <div className="funnel-step" key={step.action}>
                      <div className="funnel-meta">
                        <span className="funnel-label">{step.label}</span>
                        <span className="num">
                          {loading ? "·" : step.count}
                          {step.stepPct !== null && (
                            <span className="acc funnel-pct"> · {fmtPct(step.stepPct)}</span>
                          )}
                        </span>
                      </div>
                      <div className="funnel-track">
                        <div
                          className="funnel-fill"
                          style={{ width: loading ? "0%" : `${step.widthPct}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="k dim" style={{ marginTop: 14 }}>
                  Event totals over the analyzed window — not a per-user cohort. Steps share no
                  identity key, so each % is volume-over-previous, not retention.
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <span className="k">actor-role mix</span>
              </div>
              <div className="panel-body">
                <div className="rolebar">
                  {roleMix.map((role) => (
                    <div
                      key={role.label}
                      className={`rolebar-seg role-${role.label}`}
                      style={{ flexGrow: role.count }}
                      title={`${role.label}: ${role.count}`}
                    />
                  ))}
                </div>
                <table className="console" style={{ marginTop: 14 }}>
                  <tbody>
                    {roleMix.map((role) => (
                      <tr key={role.label}>
                        <td>
                          <span className={`role-dot role-${role.label}`} /> {role.label}
                        </td>
                        <td className="r num">{role.count}</td>
                        <td className="r num dim">
                          {stats.total ? fmtPct(role.count / stats.total) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="panel rise mb">
            <div className="panel-head">
              <span className="k">compliance · sensitive events</span>
            </div>
            <div className="panel-body">
              <div className="compliance-strip">
                <div className="compliance-cell">
                  <span className="k">dsr exports</span>
                  <div className="num">
                    <span className="acc">{loading ? "·" : compliance.dsrCompleted}</span>
                    <span className="dim"> / {loading ? "·" : compliance.dsrRequested}</span>
                  </div>
                  <span className="k dim">completed / requested</span>
                </div>
                <div className="compliance-cell">
                  <span className="k">suspensions</span>
                  <div className="num">
                    <span className={compliance.suspended ? "danger-text" : undefined}>
                      {loading ? "·" : compliance.suspended}
                    </span>
                  </div>
                  <span className="k dim">{loading ? "" : `${compliance.unsuspended} lifted`}</span>
                </div>
                <div className="compliance-cell">
                  <span className="k">consent updates</span>
                  <div className="num">{loading ? "·" : compliance.consentUpdates}</div>
                  <span className="k dim">channel-pref flips</span>
                </div>
              </div>
            </div>
          </div>

          <div className="panel rise">
            <div className="panel-head">
              <span className="k">action histogram</span>
              <span className="k dim">{loading ? "·" : `${actions.length} distinct`}</span>
            </div>
            <div className="table-wrap" style={{ border: 0 }}>
              <table className="console">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Distribution</th>
                    <th className="r">Count</th>
                    <th className="r">Share</th>
                  </tr>
                </thead>
                <tbody>
                  {actions.map((row) => (
                    <tr key={row.label}>
                      <td>
                        <span className={row.label.startsWith("admin.") ? "acc" : undefined}>
                          {row.label}
                        </span>
                      </td>
                      <td>
                        <span className="hist-track">
                          <span
                            className="hist-fill"
                            style={{ width: `${(row.count / actionMax) * 100}%` }}
                          />
                        </span>
                      </td>
                      <td className="r num">{row.count}</td>
                      <td className="r num dim">
                        {stats.total ? fmtPct(row.count / stats.total) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
