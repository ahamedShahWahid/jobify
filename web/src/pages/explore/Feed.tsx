import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import type { ApplicationListItem, FeedItem, SavedJobListItem } from "../../api/types";
import { Masthead } from "../../components/Chrome";
import { ago, ctcBand, EmptyState, ErrorNotice, ScoreStamp, VerifiedTag } from "../../components/bits";
import { useSession, useSessionStore } from "../../session";
import { usePaged } from "./usePaged";

type Tab = "feed" | "applied" | "saved";

/** A clickable job card — used across all three tabs with optional context line. */
function JobCard({
  jobId,
  title,
  org,
  verified,
  locations,
  ctc,
  score,
  fit,
  context,
}: {
  jobId: string;
  title: string;
  org: string;
  verified: boolean;
  locations: string[];
  ctc: [number | null, number | null];
  score?: number;
  fit?: string;
  context?: React.ReactNode;
}) {
  return (
    <Link to={`/explore/jobs/${jobId}`} className="jobcard">
      <div className="jobcard-top">
        <div>
          <h3>{title}</h3>
          <div className="org">
            {org} <VerifiedTag verified={verified} />
          </div>
        </div>
        {score !== undefined && <ScoreStamp score={score} />}
      </div>
      <div className="meta">
        <span className="tag">{locations.join(" · ")}</span>
        <span className="tag accent num">{ctcBand(ctc[0], ctc[1])}</span>
        {context}
      </div>
      {fit && <div className="fitline">“{fit}”</div>}
    </Link>
  );
}

export function Feed() {
  const { client, identity } = useSession();
  const { signOut } = useSessionStore();
  const [tab, setTab] = useState<Tab>("feed");

  const feedFetcher = useCallback((c: string | undefined) => client.feed(c), [client]);
  const appsFetcher = useCallback((c: string | undefined) => client.applications(c), [client]);
  const savedFetcher = useCallback((c: string | undefined) => client.saved(c), [client]);

  const feed = usePaged<FeedItem>(feedFetcher, "feed");
  const apps = usePaged<ApplicationListItem>(appsFetcher, "applied");
  const saved = usePaged<SavedJobListItem>(savedFetcher, "saved");

  const active = tab === "feed" ? feed : tab === "applied" ? apps : saved;
  const name = identity.applicant?.full_name ?? identity.email?.split("@")[0] ?? "there";

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div className="app-head">
          <div className="spread">
            <div>
              <span className="kicker">The matched feed</span>
              <h1>Hello, {name}.</h1>
            </div>
            <button className="btn ghost sm" onClick={signOut}>
              Sign out
            </button>
          </div>

          <div className="tabs">
            <button className={tab === "feed" ? "on" : ""} onClick={() => setTab("feed")}>
              Your matches
            </button>
            <button className={tab === "applied" ? "on" : ""} onClick={() => setTab("applied")}>
              Applied
              {apps.rows.length > 0 && <span className="count num">{apps.rows.length}</span>}
            </button>
            <button className={tab === "saved" ? "on" : ""} onClick={() => setTab("saved")}>
              Saved
              {saved.rows.length > 0 && <span className="count num">{saved.rows.length}</span>}
            </button>
          </div>
        </div>

        <ErrorNotice error={active.error} />

        {/* ---- FEED ---- */}
        {tab === "feed" && (
          <>
            <div className="feed-grid">
              {feed.rows.map((it) => (
                <JobCard
                  key={it.match.id}
                  jobId={it.job.id}
                  title={it.job.title}
                  org={it.employer.name}
                  verified={it.employer.verified}
                  locations={it.job.locations}
                  ctc={[it.job.ctc_min, it.job.ctc_max]}
                  score={it.match.total_score}
                  fit={it.match.explanation?.fit}
                />
              ))}
            </div>
            {feed.rows.length === 0 && !feed.busy && (
              <EmptyState>No matches surfaced yet. Upload a résumé and check back soon.</EmptyState>
            )}
          </>
        )}

        {/* ---- APPLIED ---- */}
        {tab === "applied" && (
          <>
            <div className="feed-grid">
              {apps.rows.map((it) => (
                <JobCard
                  key={it.application.id}
                  jobId={it.job.id}
                  title={it.job.title}
                  org={it.employer.name}
                  verified={it.employer.verified}
                  locations={it.job.locations}
                  ctc={[it.job.ctc_min, it.job.ctc_max]}
                  context={
                    it.application.status === "applied" ? (
                      <span className="tag verified">Applied · {ago(it.application.updated_at)}</span>
                    ) : (
                      <span className="tag">Withdrawn</span>
                    )
                  }
                />
              ))}
            </div>
            {apps.rows.length === 0 && !apps.busy && (
              <EmptyState>You haven't applied to anything yet. Your matches are one tap away.</EmptyState>
            )}
          </>
        )}

        {/* ---- SAVED ---- */}
        {tab === "saved" && (
          <>
            <div className="feed-grid">
              {saved.rows.map((it) => (
                <JobCard
                  key={it.saved_job.id}
                  jobId={it.job.id}
                  title={it.job.title}
                  org={it.employer.name}
                  verified={it.employer.verified}
                  locations={it.job.locations}
                  ctc={[it.job.ctc_min, it.job.ctc_max]}
                  context={
                    it.job.status === "open" ? (
                      <span className="tag">Saved · {ago(it.saved_job.created_at)}</span>
                    ) : (
                      <span className="tag accent">Role closed</span>
                    )
                  }
                />
              ))}
            </div>
            {saved.rows.length === 0 && !saved.busy && (
              <EmptyState>Nothing saved yet. Tap “Save” on a role to keep it here.</EmptyState>
            )}
          </>
        )}

        {active.busy && <div className="spinner-row">Loading…</div>}

        <div className="center mt mb">
          {active.nextCursor && (
            <button className="btn ghost" disabled={active.busy} onClick={active.loadMore}>
              Load more
            </button>
          )}
        </div>
      </div>
    </>
  );
}
