import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { ApplicantsOfJobPage, ApplicationStage } from "../../api/types";
import { EmptyState, ErrorNotice, ScoreBar, ShortId, Stamp } from "../../components/bits";
import { usePagedFetch } from "../../paging/usePagedFetch";
import { useSession } from "../../session";

export function Applicants() {
  const { client } = useSession();
  const { jobId } = useParams<{ jobId: string }>();
  const [savingId, setSavingId] = useState<string | null>(null);
  const [stageError, setStageError] = useState<string | null>(null);

  const fetcher = useCallback(
    (cursor: string | undefined): Promise<ApplicantsOfJobPage> =>
      jobId
        ? client.listJobApplicants(jobId, cursor)
        : Promise.resolve({ items: [], next_cursor: null }),
    [client, jobId],
  );
  const { rows, nextCursor, busy, error, loadMore, reload } = usePagedFetch(fetcher, jobId ?? "");

  const changeStage = async (
    applicationId: string,
    stage: Exclude<ApplicationStage, "applied">,
  ) => {
    if (!jobId) return;
    setSavingId(applicationId);
    setStageError(null);
    try {
      await client.setApplicationStage(jobId, applicationId, stage);
      reload();
    } catch (e) {
      setStageError(errorMessage(e));
    } finally {
      setSavingId(null);
    }
  };

  return (
    <>
      <div className="headline rise">
        <h1>
          APPLICANT <span className="ghost">ROSTER</span>
        </h1>
        <div className="sub">
          <span className="flavor">People, not rows — but the scores help you start somewhere.</span>
          <Link className="btn ghost sm" to="/employers/jobs">
            ← Back to postings
          </Link>
        </div>
      </div>

      <div className="notice rise">
        Viewing this roster is a PII disclosure — the API writes a{" "}
        <span>job.applicants_listed</span> audit row for every load.
      </div>

      <ErrorNotice error={error} />
      <ErrorNotice error={stageError} />

      <div className="table-wrap rise">
        <table className="console">
          <thead>
            <tr>
              <th>Applicant</th>
              <th>Stage</th>
              <th>Applied</th>
              <th>Match</th>
              <th>Why / caveat</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.application_id}>
                <td>
                  {row.display_name ?? <span className="dim">name withheld</span>}
                  <div className="k" style={{ marginTop: 2 }}>
                    {row.email ?? "—"} · <ShortId id={row.applicant_id} />
                  </div>
                </td>
                <td>
                  {row.status === "withdrawn" ? (
                    <span className="chip">withdrawn</span>
                  ) : (
                    <select
                      className="stage-select"
                      value={row.stage}
                      disabled={savingId === row.application_id}
                      onChange={(e) =>
                        void changeStage(
                          row.application_id,
                          e.target.value as Exclude<ApplicationStage, "applied">,
                        )
                      }
                    >
                      {row.stage === "applied" && (
                        <option value="applied" disabled>
                          applied
                        </option>
                      )}
                      {(["shortlisted", "interview", "offer", "hired", "rejected"] as const).map(
                        (s) => (
                          <option key={s} value={s}>
                            {s === "rejected" ? "not selected" : s}
                          </option>
                        ),
                      )}
                    </select>
                  )}
                </td>
                <td>
                  <Stamp iso={row.applied_at} />
                </td>
                <td>
                  <ScoreBar score={row.match_score} />
                </td>
                <td style={{ maxWidth: 360 }}>
                  {row.match_explanation ? (
                    <>
                      <div>{row.match_explanation.fit}</div>
                      {row.match_explanation.caveat && (
                        <div className="dim" style={{ marginTop: 2 }}>
                          ⌁ {row.match_explanation.caveat}
                        </div>
                      )}
                    </>
                  ) : (
                    <span className="dim">no explanation yet</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !busy && !error && (
          <EmptyState>No one has applied yet. Surfaced matches arrive first.</EmptyState>
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
