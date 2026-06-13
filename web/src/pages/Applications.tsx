import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import type {
  ApplicationListItem,
  ApplicationListResponse,
  SavedJobListItem,
  SavedJobListResponse,
} from "../api/types";
import { Masthead } from "../components/Chrome";
import { ago, ctcBand, EmptyState, ErrorNotice, VerifiedTag } from "../components/bits";
import { useSession } from "../session";
import { usePaged } from "./explore/usePaged";

/**
 * The Casebook — the applicant's own ledger of filed applications and roles set
 * aside. Real-backed: GET /v1/applications + /v1/saved, with withdraw / re-apply
 * / unsave / apply mutations. Behind RequireApplicant.
 *
 * Backend invariants this UI leans on (api CLAUDE.md):
 *  · re-apply after withdraw UPDATEs the same row back to "applied" → call
 *    apply(job_id), then reload re-sorts by updated_at (server does the same).
 *  · the saved list keeps closed jobs (so you see a role you bookmarked close);
 *    apply on a closed job 404s, surfaced as a plain notice.
 */

type Tab = "applied" | "saved";

function StatusStamp({ status }: { status: string }) {
  const withdrawn = status === "withdrawn";
  return (
    <span className={`cb-stamp${withdrawn ? " out" : ""}`}>
      {withdrawn ? "Withdrawn" : "Applied"}
    </span>
  );
}

export function Applications() {
  const { client } = useSession();
  const [tab, setTab] = useState<Tab>("applied");

  const appliedFetcher = useCallback<
    (cursor: string | undefined) => Promise<ApplicationListResponse>
  >((cursor) => client.applications(cursor), [client]);
  const savedFetcher = useCallback<(cursor: string | undefined) => Promise<SavedJobListResponse>>(
    (cursor) => client.saved(cursor),
    [client],
  );

  const applied = usePaged<ApplicationListItem>(appliedFetcher, "applied");
  const saved = usePaged<SavedJobListItem>(savedFetcher, "saved");

  // Per-row in-flight + action error, keyed by application/job id.
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  // Jobs applied to from the Saved tab this session. The saved list KEEPS applied
  // jobs (backend invariant), so without this the row would keep an enabled
  // "Apply" with no feedback and invite repeat taps.
  const [appliedFromSaved, setAppliedFromSaved] = useState<Set<string>>(new Set());

  async function run(id: string, fn: () => Promise<unknown>, after: () => void) {
    setBusyId(id);
    setActionError(null);
    try {
      await fn();
      after();
    } catch (e) {
      setActionError(errorMessage(e));
    } finally {
      setBusyId(null);
    }
  }

  // Apply from the Saved tab: mark the row applied (the saved row persists) and
  // refresh the Applied tab so it includes the new application on switch.
  async function applyFromSaved(jobId: string) {
    setBusyId(jobId);
    setActionError(null);
    try {
      await client.apply(jobId);
      setAppliedFromSaved((prev) => new Set(prev).add(jobId));
      applied.reload();
    } catch (e) {
      setActionError(errorMessage(e));
    } finally {
      setBusyId(null);
    }
  }

  const appliedCount = applied.rows.length;
  const savedCount = saved.rows.length;

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div style={{ padding: "26px 0 0" }}>
          <Link to="/explore" className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to feed
          </Link>
        </div>

        <header className="cb-hero rise mt">
          <div>
            <span className="kicker">Your record</span>
            <h1 className="cb-h1">The Casebook</h1>
            <p className="deck cb-deck">
              Everything you&apos;ve put your name to — and the roles you set aside to weigh.
            </p>
          </div>
          <div className="cb-counts">
            <div className="cb-count">
              <span className="n num">{appliedCount}</span>
              <span className="l">filed{applied.nextCursor ? "+" : ""}</span>
            </div>
            <div className="cb-count">
              <span className="n num">{savedCount}</span>
              <span className="l">set aside{saved.nextCursor ? "+" : ""}</span>
            </div>
          </div>
        </header>

        <div className="cb-tabs rise d1" role="tablist">
          <button
            role="tab"
            aria-selected={tab === "applied"}
            className={tab === "applied" ? "on" : ""}
            onClick={() => setTab("applied")}
          >
            Applications
          </button>
          <button
            role="tab"
            aria-selected={tab === "saved"}
            className={tab === "saved" ? "on" : ""}
            onClick={() => setTab("saved")}
          >
            Saved
          </button>
        </div>

        <ErrorNotice error={actionError} />

        {tab === "applied" ? (
          <section className="cb-list rise d2">
            <ErrorNotice error={applied.error} />
            {applied.rows.map(({ application, job, employer }) => {
              const out = application.status === "withdrawn";
              const busy = busyId === application.id || busyId === job.id;
              return (
                <article key={application.id} className={`cb-row${out ? " is-out" : ""}`}>
                  <div className="cb-rail" aria-hidden="true" />
                  <div className="cb-main">
                    <div className="cb-row-head">
                      <StatusStamp status={application.status} />
                      <span className="cb-when num">
                        {out ? "withdrawn" : "filed"} {ago(application.updated_at)}
                      </span>
                    </div>
                    <h3 className="cb-title">
                      <Link to={`/explore/jobs/${job.id}`}>{job.title}</Link>
                    </h3>
                    <div className="cb-meta">
                      <span className="cb-emp">{employer.name}</span>
                      <VerifiedTag verified={employer.verified} />
                      <span className="cb-dot">·</span>
                      <span className="num">{ctcBand(job.ctc_min, job.ctc_max)}</span>
                      <span className="cb-dot">·</span>
                      <span>{job.locations.join(" · ")}</span>
                    </div>
                  </div>
                  <div className="cb-actions">
                    <Link to={`/explore/jobs/${job.id}/why`} className="btn ghost sm">
                      Why it fit
                    </Link>
                    {out ? (
                      <button
                        className="btn primary sm"
                        disabled={busy}
                        onClick={() =>
                          void run(job.id, () => client.apply(job.id), applied.reload)
                        }
                      >
                        {busy ? "…" : "Re-apply"}
                      </button>
                    ) : (
                      <button
                        className="btn sm"
                        disabled={busy}
                        onClick={() =>
                          void run(
                            application.id,
                            () => client.withdraw(application.id),
                            applied.reload,
                          )
                        }
                      >
                        {busy ? "…" : "Withdraw"}
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
            {appliedCount === 0 && !applied.busy && !applied.error && (
              <EmptyState>
                You haven&apos;t filed anything yet. Your feed is where the matched roles live —{" "}
                <Link to="/explore" className="accent">
                  open it
                </Link>{" "}
                and apply to the ones that fit.
              </EmptyState>
            )}
            {applied.nextCursor && (
              <div className="cb-more">
                <button className="btn" disabled={applied.busy} onClick={applied.loadMore}>
                  {applied.busy ? "Loading…" : "Older applications"}
                </button>
              </div>
            )}
          </section>
        ) : (
          <section className="cb-list rise d2">
            <ErrorNotice error={saved.error} />
            {saved.rows.map(({ saved_job, job, employer }) => {
              const closed = job.status !== "open";
              const busy = busyId === job.id;
              return (
                <article key={saved_job.id} className={`cb-row${closed ? " is-closed" : ""}`}>
                  <div className="cb-rail saved" aria-hidden="true" />
                  <div className="cb-main">
                    <div className="cb-row-head">
                      <span className="cb-stamp saved">Saved</span>
                      <span className="cb-when num">set aside {ago(saved_job.created_at)}</span>
                      {closed && <span className="tag">Role closed</span>}
                    </div>
                    <h3 className="cb-title">
                      <Link to={`/explore/jobs/${job.id}`}>{job.title}</Link>
                    </h3>
                    <div className="cb-meta">
                      <span className="cb-emp">{employer.name}</span>
                      <VerifiedTag verified={employer.verified} />
                      <span className="cb-dot">·</span>
                      <span className="num">{ctcBand(job.ctc_min, job.ctc_max)}</span>
                      <span className="cb-dot">·</span>
                      <span>{job.locations.join(" · ")}</span>
                    </div>
                  </div>
                  <div className="cb-actions">
                    <button
                      className="btn ghost sm"
                      disabled={busy}
                      onClick={() => void run(job.id, () => client.unsave(job.id), saved.reload)}
                    >
                      Remove
                    </button>
                    {appliedFromSaved.has(job.id) ? (
                      <Link to={`/explore/jobs/${job.id}`} className="btn sm cb-applied">
                        Applied ✓
                      </Link>
                    ) : (
                      <button
                        className="btn primary sm"
                        disabled={busy || closed}
                        title={closed ? "This role is closed" : undefined}
                        onClick={() => void applyFromSaved(job.id)}
                      >
                        {busy ? "…" : closed ? "Closed" : "Apply"}
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
            {savedCount === 0 && !saved.busy && !saved.error && (
              <EmptyState>
                Nothing set aside. On any role, tap <span className="accent">Save</span> to keep it
                here while you decide.
              </EmptyState>
            )}
            {saved.nextCursor && (
              <div className="cb-more">
                <button className="btn" disabled={saved.busy} onClick={saved.loadMore}>
                  {saved.busy ? "Loading…" : "Older saves"}
                </button>
              </div>
            )}
          </section>
        )}

        <div className="cb-foot-rule" />
      </div>
    </>
  );
}
