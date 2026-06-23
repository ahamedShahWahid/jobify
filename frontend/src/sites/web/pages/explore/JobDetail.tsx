import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { JobDetailResponse } from "../../api/types";
import { Masthead } from "../../components/Chrome";
import { ago, ctcBand, ErrorNotice, VerifiedTag } from "../../components/bits";
import { useSession } from "../../session";

const COMPONENT_LABELS: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  location: "Location",
  title: "Title",
};

export function JobDetail() {
  const { client } = useSession();
  const { jobId } = useParams<{ jobId: string }>();
  const [data, setData] = useState<JobDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    if (!jobId) return;
    setError(null);
    try {
      setData(await client.job(jobId));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [client, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<unknown>) {
    setActing(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setActing(false);
    }
  }

  if (error && !data) {
    return (
      <>
        <Masthead />
        <div className="wrap">
          <div className="notice err mt">⚠ {error}</div>
          <Link to="/explore" className="link-arrow">
            ← Back to feed
          </Link>
        </div>
      </>
    );
  }
  if (!data) {
    return (
      <>
        <Masthead />
        <div className="wrap">
          <div className="spinner-row mt">Loading role…</div>
        </div>
      </>
    );
  }

  const { job, employer, match, application, saved_job } = data;
  const applied = application?.status === "applied";
  const isSaved = saved_job !== null;
  const closed = job.status !== "open";

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div style={{ padding: "26px 0 0" }}>
          <Link to="/explore" className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to feed
          </Link>
        </div>

        <ErrorNotice error={error} />

        <div className="detail mt">
          {/* left: the role */}
          <div>
            <div className="row">
              <span className="kicker">{employer.name}</span>
              <VerifiedTag verified={employer.verified} />
              {closed && <span className="tag accent">Role closed</span>}
            </div>
            <h1>{job.title}</h1>
            <div className="row mb">
              <span className="tag">{job.locations.join(" · ")}</span>
              <span className="tag accent num">{ctcBand(job.ctc_min, job.ctc_max)}</span>
              <span className="dim" style={{ fontSize: 13 }}>
                Posted {ago(job.posted_at)}
              </span>
            </div>
            <hr className="rule mb" />
            <div className="body">
              {job.description.split("\n\n").map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          </div>

          {/* right: the match */}
          <aside className="aside">
            {match ? (
              <>
                <div className="aside-score">
                  <span className="big num">{match.total_score.toFixed(2)}</span>
                  <div>
                    <div className="kicker">Match</div>
                    <div className="dim" style={{ fontSize: 13 }}>
                      why this surfaced
                    </div>
                  </div>
                </div>
                {match.explanation?.fit && (
                  <div className="aside-section">
                    <div className="explain" style={{ marginBottom: 0 }}>
                      <div className="fit">“{match.explanation.fit}”</div>
                      {match.explanation.caveat && (
                        <div className="caveat">{match.explanation.caveat}</div>
                      )}
                    </div>
                  </div>
                )}
                <div className="aside-section">
                  <div className="kicker ink mb" style={{ marginBottom: 10 }}>
                    Score breakdown
                  </div>
                  <div className="bars">
                    {Object.entries(match.components).map(([key, val]) => (
                      <div className="bar-row" key={key}>
                        <span>{COMPONENT_LABELS[key] ?? key}</span>
                        <span className="bar-track">
                          <span
                            className={`bar-fill${key === "skills" ? " acc" : ""}`}
                            style={{ width: `${Math.max(0, Math.min(1, val)) * 100}%` }}
                          />
                        </span>
                        <span className="num">{val.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                  <Link
                    to={`/explore/jobs/${job.id}/why`}
                    className="link-arrow"
                    style={{ fontSize: 13, marginTop: 14 }}
                  >
                    See the full breakdown <span className="arr">→</span>
                  </Link>
                </div>
              </>
            ) : (
              <div className="aside-section">
                <div className="kicker ink">No match record</div>
                <p className="dim" style={{ fontSize: 14, margin: "8px 0 0" }}>
                  You reached this role by link — it isn't in your surfaced feed.
                </p>
              </div>
            )}

            <div className="aside-actions">
              {applied ? (
                <button
                  className="btn ghost"
                  disabled={acting || !application}
                  onClick={() => application && act(() => client.withdraw(application.id))}
                >
                  Withdraw
                </button>
              ) : (
                <button
                  className="btn primary"
                  disabled={acting || closed}
                  onClick={() => act(() => client.apply(job.id))}
                >
                  {closed ? "Role closed" : "Apply"}
                </button>
              )}
              <button
                className={`btn${isSaved ? " ink" : ""}`}
                disabled={acting}
                onClick={() => act(() => (isSaved ? client.unsave(job.id) : client.save(job.id)))}
              >
                {isSaved ? "Saved ✓" : "Save"}
              </button>
            </div>
            {applied && application && (
              <div className="aside-section" style={{ borderTop: "1px solid var(--line)", borderBottom: 0 }}>
                <span className="tag verified">Applied · {ago(application.updated_at)}</span>
              </div>
            )}
          </aside>
        </div>
        <div style={{ height: 60 }} />
      </div>
    </>
  );
}
