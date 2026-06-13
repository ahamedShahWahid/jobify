import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ConsoleClient } from "../../api/client";
import { errorMessage } from "../../api/client";
import type { EmployerRead, RecruiterJobRow } from "../../api/types";
import { EmptyState, ErrorNotice, Stamp } from "../../components/bits";
import { useSession } from "../../session";

// The dashboard totals must count ALL jobs, not the first page — otherwise a
// recruiter with >20 jobs of a status silently sees undercounted tiles and a
// top-5 that misses high-applicant postings on later pages. Bounded so a
// misbehaving cursor can't loop forever.
const MAX_PAGES = 50;

async function drainJobs(
  client: ConsoleClient,
  status: "open" | "closed",
): Promise<RecruiterJobRow[]> {
  const all: RecruiterJobRow[] = [];
  let cursor: string | undefined;
  for (let page = 0; page < MAX_PAGES; page++) {
    const res = await client.listMyJobs(status, cursor);
    all.push(...res.items);
    if (!res.next_cursor) break;
    cursor = res.next_cursor;
  }
  return all;
}

export function Dashboard() {
  const { client, identity } = useSession();
  const [open, setOpen] = useState<RecruiterJobRow[] | null>(null);
  const [closed, setClosed] = useState<RecruiterJobRow[] | null>(null);
  const [employers, setEmployers] = useState<EmployerRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [openJobs, closedJobs, employerList] = await Promise.all([
          drainJobs(client, "open"),
          drainJobs(client, "closed"),
          client.myEmployers(),
        ]);
        if (cancelled) return;
        setOpen(openJobs);
        setClosed(closedJobs);
        setEmployers(employerList);
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  const all = [...(open ?? []), ...(closed ?? [])];
  const totalApplicants = all.reduce((sum, job) => sum + job.applicant_count, 0);
  const totalSurfaced = all.reduce((sum, job) => sum + job.surfaced_match_count, 0);
  const loading = open === null;

  return (
    <>
      <div className="headline rise">
        <h1>
          JOB <span className="ghost">DESK</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            Good morning{identity.email ? `, ${identity.email.split("@")[0]}` : ""}. The pipeline,
            at a glance.
          </span>
        </div>
      </div>

      <ErrorNotice error={error} />

      <div className="tiles rise mb">
        <div className="tile">
          <span className="k">open postings</span>
          <div className="value acc num">{loading ? "·" : open.length}</div>
        </div>
        <div className="tile">
          <span className="k">closed</span>
          <div className="value num">{loading ? "·" : (closed?.length ?? 0)}</div>
        </div>
        <div className="tile">
          <span className="k">applicants, all time</span>
          <div className="value num">{loading ? "·" : totalApplicants}</div>
        </div>
        <div className="tile">
          <span className="k">surfaced matches</span>
          <div className="value num">{loading ? "·" : totalSurfaced}</div>
        </div>
      </div>

      <div className="panel rise mb">
        <div className="panel-head">
          <span className="k">most active open postings</span>
          <Link className="btn ghost sm" to="/recruiter/jobs">
            All jobs →
          </Link>
        </div>
        <div className="table-wrap" style={{ border: 0 }}>
          <table className="console">
            <thead>
              <tr>
                <th>Title</th>
                <th>Posted</th>
                <th className="r">Applicants</th>
                <th className="r">Surfaced</th>
              </tr>
            </thead>
            <tbody>
              {(open ?? [])
                .slice()
                .sort((a, b) => b.applicant_count - a.applicant_count)
                .slice(0, 5)
                .map((job) => (
                  <tr key={job.id}>
                    <td>
                      <Link to={`/recruiter/jobs/${job.id}/applicants`}>{job.title}</Link>
                      <div className="k" style={{ marginTop: 2 }}>
                        {job.locations.join(" · ")}
                      </div>
                    </td>
                    <td>
                      <Stamp iso={job.posted_at} />
                    </td>
                    <td className="r num">{job.applicant_count}</td>
                    <td className="r num acc">{job.surfaced_match_count}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          {open !== null && open.length === 0 && (
            <EmptyState>
              No open postings yet — <Link to="/recruiter/jobs">post the first one</Link>.
            </EmptyState>
          )}
        </div>
      </div>

      <div className="panel rise">
        <div className="panel-head">
          <span className="k">your employers</span>
          <Link className="btn ghost sm" to="/recruiter/team">
            Team & invites →
          </Link>
        </div>
        <div className="table-wrap" style={{ border: 0 }}>
          <table className="console">
            <thead>
              <tr>
                <th>Name</th>
                <th>GST</th>
                <th>Verification</th>
                <th>Since</th>
              </tr>
            </thead>
            <tbody>
              {(employers ?? []).map((employer) => (
                <tr key={employer.id}>
                  <td>{employer.name}</td>
                  <td className="num">{employer.gst ?? <span className="dim">—</span>}</td>
                  <td>
                    {employer.verified_at ? (
                      <span className="chip ok">
                        <span className="led" /> verified
                      </span>
                    ) : (
                      <span className="chip">unverified</span>
                    )}
                  </td>
                  <td>
                    <Stamp iso={employer.created_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
