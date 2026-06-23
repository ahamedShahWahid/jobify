import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { EmployerRead, RecruiterJobRow } from "../../api/types";
import { ctcBandText, EmptyState, ErrorNotice, Stamp } from "../../components/bits";
import { usePagedFetch } from "../../paging/usePagedFetch";
import { useSession } from "../../session";

function ctcBand(job: RecruiterJobRow) {
  if (job.ctc_min === null && job.ctc_max === null)
    return <span className="dim">undisclosed</span>;
  return <span className="num">{ctcBandText(job.ctc_min, job.ctc_max)}</span>;
}

/**
 * Postings — the recruiter's job list. Create/edit open the full-page composer
 * (/recruiter/jobs/new, /…/:id/edit) with its live candidate preview; the edit
 * link hands the row over via router state so the composer doesn't re-fetch.
 * Status flip + delete stay inline as quick actions on the list. The composer
 * returns here with `state.status` so editing a closed job lands on the Closed
 * tab (not the default Open).
 */
export function Jobs() {
  const { client } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const returnedStatus = (location.state as { status?: "open" | "closed" } | null)?.status;
  const [status, setStatus] = useState<"open" | "closed">(returnedStatus ?? "open");
  const [employers, setEmployers] = useState<EmployerRead[]>([]);
  const [opError, setOpError] = useState<string | null>(null);

  const fetcher = useCallback(
    (cursor: string | undefined) => client.listMyJobs(status, cursor),
    [client, status],
  );
  const { rows, nextCursor, busy, error, reload, loadMore } = usePagedFetch(fetcher, status);

  // Needed only to disable "New posting" when the recruiter has no employer yet
  // (the composer's create flow requires one).
  useEffect(() => {
    client.myEmployers().then(setEmployers, () => undefined);
  }, [client]);

  async function flipStatus(job: RecruiterJobRow) {
    setOpError(null);
    try {
      await client.patchJob(job.id, { status: job.status === "open" ? "closed" : "open" });
      reload();
    } catch (e) {
      setOpError(errorMessage(e));
    }
  }

  async function remove(job: RecruiterJobRow) {
    if (!window.confirm(`Delete "${job.title}"? Applicants keep their history; the posting goes.`))
      return;
    setOpError(null);
    try {
      await client.deleteJob(job.id);
      reload();
    } catch (e) {
      setOpError(errorMessage(e));
    }
  }

  return (
    <>
      <div className="headline rise">
        <h1>
          POSTINGS<span className="ghost">/{status.toUpperCase()}</span>
        </h1>
        <div className="sub">
          <span className="flavor">Write the role the way you&apos;d want to read it.</span>
        </div>
      </div>

      <div className="spread rise mb">
        <div className="mode-tabs" style={{ marginBottom: 0, width: 260 }}>
          <button className={status === "open" ? "on" : ""} onClick={() => setStatus("open")}>
            Open
          </button>
          <button className={status === "closed" ? "on" : ""} onClick={() => setStatus("closed")}>
            Closed
          </button>
        </div>
        <button
          className="btn primary"
          onClick={() => navigate("/console/recruiter/jobs/new")}
          disabled={employers.length === 0}
          title={employers.length === 0 ? "Create an employer first" : undefined}
        >
          + New posting
        </button>
      </div>

      <ErrorNotice error={error ?? opError} />

      <div className="table-wrap rise">
        <table className="console">
          <thead>
            <tr>
              <th>Title</th>
              <th>Band</th>
              <th>Exp</th>
              <th>Posted</th>
              <th className="r">Applicants</th>
              <th className="r">Surfaced</th>
              <th className="r">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((job) => (
              <tr key={job.id}>
                <td style={{ maxWidth: 320 }}>
                  <Link to={`/console/recruiter/jobs/${job.id}/applicants`}>{job.title}</Link>
                  <div className="k" style={{ marginTop: 2 }}>
                    {job.locations.join(" · ")}
                    {!job.employer_verified && (
                      <span className="chip" style={{ marginLeft: 8 }}>
                        unverified employer
                      </span>
                    )}
                  </div>
                </td>
                <td>{ctcBand(job)}</td>
                <td className="num">
                  {job.min_exp_years}–{job.max_exp_years}y
                </td>
                <td>
                  <Stamp iso={job.posted_at} />
                </td>
                <td className="r num">
                  <Link to={`/recruiter/jobs/${job.id}/applicants`}>{job.applicant_count}</Link>
                </td>
                <td className="r num acc">{job.surfaced_match_count}</td>
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  <button
                    className="btn ghost sm"
                    onClick={() => navigate(`/console/recruiter/jobs/${job.id}/edit`, { state: { job } })}
                  >
                    Edit
                  </button>{" "}
                  <button className="btn sm" onClick={() => void flipStatus(job)}>
                    {job.status === "open" ? "Close" : "Reopen"}
                  </button>{" "}
                  <button className="btn danger sm" onClick={() => void remove(job)}>
                    Del
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !busy && (
          <EmptyState>
            {status === "open" ? "Nothing open right now." : "Nothing has been closed yet."}
          </EmptyState>
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
