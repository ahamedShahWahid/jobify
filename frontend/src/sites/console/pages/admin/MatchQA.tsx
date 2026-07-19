import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import type {
  AdminMatchFeedbackRow,
  AdminMatchFeedbackSummary,
  MatchFeedbackRating,
} from "../../api/types";
import { EmptyState, ErrorNotice, ScoreBar, ShortId, Stamp } from "../../components/bits";
import { usePagedFetch } from "../../paging/usePagedFetch";
import { useSession } from "../../session";

const FILTERS: Array<{ key: MatchFeedbackRating | "all"; label: string }> = [
  { key: "all", label: "All" },
  { key: "up", label: "▲ Up" },
  { key: "down", label: "▼ Down" },
];

/** n below which the relevance % is statistically meaningless. */
const BELIEVABLE_N = 500;

function pct(share: number | null): string {
  return share == null ? "—" : `${(share * 100).toFixed(1)}%`;
}

export function MatchQA() {
  const { client } = useSession();

  const [filter, setFilter] = useState<MatchFeedbackRating | "all">("all");
  const [summary, setSummary] = useState<AdminMatchFeedbackSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await client.matchFeedbackSummary();
        if (!cancelled) setSummary(result);
      } catch (e) {
        if (!cancelled) setSummaryError(errorMessage(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  const fetcher = useCallback(
    (cursor: string | undefined) => client.listMatchFeedback(filter, cursor),
    [client, filter],
  );
  const { rows, nextCursor, busy, error, loadMore } = usePagedFetch<AdminMatchFeedbackRow>(
    fetcher,
    filter,
  );

  const totalRated = summary ? summary.all_time.up + summary.all_time.down : 0;

  return (
    <>
      <div className="headline rise">
        <h1>
          MATCH <span className="ghost">QA</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            Applicant verdicts on surfaced matches — the relevance metric and the receipts
            behind it.
          </span>
        </div>
      </div>

      <ErrorNotice error={summaryError} />

      <div className="panel rise mb">
        <div className="panel-head">
          <span className="k">relevance · the BRD match-quality metric</span>
        </div>
        <div className="panel-body">
          <div className="compliance-strip">
            <div className="compliance-cell">
              <span className="k">all time</span>
              <div className="num">{summary ? pct(summary.all_time.share) : "·"}</div>
              <span className="k dim">
                {summary ? `${summary.all_time.up}▲ / ${summary.all_time.down}▼` : "—"}
              </span>
            </div>
            <div className="compliance-cell">
              <span className="k">last 30d</span>
              <div className="num">{summary ? pct(summary.last_30d.share) : "·"}</div>
              <span className="k dim">
                {summary ? `${summary.last_30d.up}▲ / ${summary.last_30d.down}▼` : "—"}
              </span>
            </div>
            {summary && totalRated < BELIEVABLE_N && (
              <div className="compliance-cell">
                <span className="k">confidence</span>
                <div className="num">n={totalRated}</div>
                <span className="k dim">below n={BELIEVABLE_N} — not yet believable</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="tiles rise mb">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`tile tile-button${filter === key ? " on" : ""}`}
            onClick={() => setFilter(key)}
          >
            <span className="k">{label}</span>
            <div className="value num">
              {summary
                ? key === "all"
                  ? summary.all_time.up + summary.all_time.down
                  : summary.all_time[key]
                : "·"}
            </div>
          </button>
        ))}
      </div>

      <ErrorNotice error={error} />

      <div className="table-wrap rise">
        <table className="console">
          <thead>
            <tr>
              <th>Verdict</th>
              <th>Job</th>
              <th>Employer</th>
              <th>Applicant</th>
              <th>Score</th>
              <th>Why it was surfaced</th>
              <th>Rated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <span className={row.rating === "up" ? "chip ok" : "chip danger"}>
                    {row.rating === "up" ? "▲ up" : "▼ down"}
                  </span>
                </td>
                <td>{row.job_title}</td>
                <td>{row.employer_name}</td>
                <td className="mono-id">
                  {row.applicant_name ?? <ShortId id={row.applicant_id} />}
                </td>
                <td>
                  <ScoreBar score={row.total_score} />
                </td>
                <td>
                  {row.explanation?.fit ?? <span className="dim">—</span>}
                  {row.explanation?.caveat && (
                    <div className="k dim" style={{ marginTop: 4 }}>
                      caveat: {row.explanation.caveat}
                    </div>
                  )}
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <Stamp iso={row.created_at} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !busy && !error && (
          <EmptyState>No ratings yet — the metric starts when applicants start voting.</EmptyState>
        )}
      </div>

      <div className="row mt">
        {nextCursor && (
          <button className="btn" disabled={busy} onClick={loadMore}>
            {busy ? "Loading…" : "Load more"}
          </button>
        )}
      </div>
    </>
  );
}
