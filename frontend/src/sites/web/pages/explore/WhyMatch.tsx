import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { ApplicantRead, JobDetailResponse, MeResponse, PreferencesRead } from "../../api/types";
import { Masthead } from "../../components/Chrome";
import { ago, ctcBand, ErrorNotice, JobFacts, VerifiedTag } from "../../components/bits";
import { useSession } from "../../session";

/**
 * Match-explanation deep-dive — expands the small feed-card explanation into a
 * rich "why this fits" breakdown. Loads the job detail + the caller's own
 * applicant profile to render a you-vs-role comparison. Behind RequireApplicant.
 */

const COMPONENT_LABELS: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  location: "Location",
  title: "Title",
};

/** A one-line human gloss for each scored dimension, contextualised to THIS role. */
function componentGloss(key: string, data: JobDetailResponse): string {
  const { job } = data;
  switch (key) {
    case "skills":
      return "Your résumé's skills versus what this role asks for.";
    case "experience":
      return `Your years against the role's ${job.min_exp_years}–${job.max_exp_years} yr band.`;
    case "location":
      return `Where you are against the role's locations: ${job.locations.join(" · ")}.`;
    case "title":
      return "How closely your background reads as this kind of role.";
    default:
      return "A scored dimension of the match.";
  }
}

const pct = (v: number) => `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%`;

function num(s: string | null): number | null {
  if (s === null) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Coarse overlap markers for the you-vs-role comparison rows. */
function locationAlign(preferences: PreferencesRead | null, job: JobDetailResponse["job"]): "✓" | "~" {
  const mine = preferences?.locations ?? [];
  const hit = mine.some((m) =>
    job.locations.some(
      (j) => j.toLowerCase().includes(m.toLowerCase()) || m.toLowerCase().includes(j.toLowerCase()),
    ),
  );
  const remote = job.locations.some((j) => j.toLowerCase().includes("remote"));
  return hit || remote ? "✓" : "~";
}

function experienceAlign(applicant: ApplicantRead | null, job: JobDetailResponse["job"]): "✓" | "~" {
  const yrs = num(applicant?.years_experience ?? null);
  if (yrs === null) return "~";
  return yrs >= job.min_exp_years && yrs <= job.max_exp_years ? "✓" : "~";
}

function ctcAlign(preferences: PreferencesRead | null, job: JobDetailResponse["job"]): "✓" | "~" {
  const want = num(preferences?.expected_ctc ?? null);
  if (want === null || job.ctc_max === null) return "~";
  return job.ctc_max >= want ? "✓" : "~";
}

export function WhyMatch() {
  const { client } = useSession();
  const { jobId } = useParams<{ jobId: string }>();
  const [data, setData] = useState<JobDetailResponse | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [preferences, setPreferences] = useState<PreferencesRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    if (!jobId) return;
    setError(null);
    try {
      const [detail, identity] = await Promise.all([client.job(jobId), client.me()]);
      setData(detail);
      setMe(identity);
    } catch (e) {
      setError(errorMessage(e));
      return;
    }
    // Fetched separately, non-blocking: the you-vs-role comparison degrades
    // to "—"/"~" if this fails, but the rest of the breakdown (score,
    // components) doesn't depend on it and shouldn't fail the whole page.
    client.getPreferences().then(setPreferences).catch(() => {});
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
          <div className="spinner-row mt">Loading the breakdown…</div>
        </div>
      </>
    );
  }

  const { job, employer, match, application, saved_job } = data;
  const backToJob = `/explore/jobs/${job.id}`;

  // graceful state when the role has no match record (reached by link)
  if (!match) {
    return (
      <>
        <Masthead />
        <div className="wrap wl-wrap">
          <div className="why-empty rise">
            <span className="kicker">No match record</span>
            <h1 className="wl-h">This role isn't in your surfaced feed.</h1>
            <p className="deck wl-deck">
              We can only explain a fit we scored. {job.title} at {employer.name} hasn't cleared
              your bar — or you reached it by link.
            </p>
            <div className="wl-actions">
              <Link to={backToJob} className="btn primary">
                See the role →
              </Link>
              <Link to="/explore" className="link-arrow wl-skip">
                ← Back to feed
              </Link>
            </div>
          </div>
        </div>
      </>
    );
  }

  const applicant = me?.applicant ?? null;
  const applied = application?.status === "applied";
  const isSaved = saved_job !== null;
  const closed = job.status !== "open";

  const components = Object.entries(match.components);
  const strongestKey = components.reduce<string | null>(
    (best, [k, v]) => (best === null || v > (match.components[best] ?? 0) ? k : best),
    null,
  );

  const fitLine =
    match.explanation?.fit ??
    (strongestKey
      ? `Your strongest signal here is ${(COMPONENT_LABELS[strongestKey] ?? strongestKey).toLowerCase()} — that's what pulled this role onto your feed.`
      : "This role cleared your bar across the board.");

  const myLocations = preferences?.locations.join(" · ") || "—";
  const myExp = num(applicant?.years_experience ?? null);
  const myExpLabel = myExp === null ? "—" : `${myExp} yrs`;
  const myExpected = num(preferences?.expected_ctc ?? null);
  const myExpectedLabel = myExpected === null ? "—" : ctcBand(myExpected, myExpected).split(" – ")[0];

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div style={{ padding: "26px 0 0" }}>
          <Link to={backToJob} className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to the role
          </Link>
        </div>

        <ErrorNotice error={error} />

        {/* ---- hero ---- */}
        <header className="why-hero rise mt">
          <div className="why-hero-text">
            <div className="row">
              <span className="kicker">{employer.name}</span>
              <VerifiedTag verified={employer.verified} />
              {closed && <span className="tag accent">Role closed</span>}
            </div>
            <h1 className="why-title">{job.title}</h1>
            <p className="deck why-deck">Why this surfaced.</p>
          </div>
          <div className="why-hero-stat">
            <div className="why-stat-num mono num">{match.total_score.toFixed(2)}</div>
            <div className="why-stat-label">total match</div>
          </div>
        </header>

        {/* ---- narrative ---- */}
        <section className="why-narrative rise d1">
          <blockquote className="why-quote serif">“{fitLine}”</blockquote>
          {match.explanation?.caveat && (
            <p className="why-caveat">{match.explanation.caveat}</p>
          )}
        </section>

        {/* ---- composition: vector vs structured ---- */}
        <section className="why-compose rise d1">
          <div className="why-compose-row">
            <div className="why-half">
              <div className="kicker ink">Semantic fit</div>
              <div className="why-half-num mono num">{match.vector_score.toFixed(2)}</div>
              <div className="dim why-half-sub">
                Your résumé's meaning against the role, via embeddings.
              </div>
            </div>
            <div className="why-half-op mono">×0.6&nbsp;&nbsp;+&nbsp;&nbsp;×0.4</div>
            <div className="why-half">
              <div className="kicker ink">Structured fit</div>
              <div className="why-half-num mono num">{match.structured_score.toFixed(2)}</div>
              <div className="dim why-half-sub">
                Hard signals — title, experience band, location.
              </div>
            </div>
          </div>
          <p className="why-weight-note dim">
            The total weights semantic fit at roughly 0.6 and structured fit at 0.4 — meaning
            matters more than checkbox overlap, but both count.
          </p>
        </section>

        {/* ---- four components in depth ---- */}
        <section className="why-components rise d2">
          <div className="why-sec-head">
            <span className="kicker ink">The four dimensions</span>
          </div>
          <div className="why-comp-list">
            {components.map(([key, val]) => (
              <div className="why-comp" key={key}>
                <div className="bar-row why-comp-bar">
                  <span>{COMPONENT_LABELS[key] ?? key}</span>
                  <span className="bar-track">
                    <span
                      className={`bar-fill${key === strongestKey ? " acc" : ""}`}
                      style={{ width: pct(val) }}
                    />
                  </span>
                  <span className="num">{val.toFixed(2)}</span>
                </div>
                <p className="why-comp-gloss dim">{componentGloss(key, data)}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ---- you vs the role ---- */}
        <section className="why-vs rise d2">
          <div className="why-sec-head">
            <span className="kicker ink">You ⇄ this role</span>
          </div>
          <div className="why-vs-grid">
            <div className="why-vs-col">
              <div className="why-vs-h">You</div>
              <div className="factline">
                <span className="k">Location</span>
                <span className="v">{myLocations}</span>
              </div>
              <div className="factline">
                <span className="k">Experience</span>
                <span className="v num">{myExpLabel}</span>
              </div>
              <div className="factline">
                <span className="k">Expected</span>
                <span className="v num">{myExpectedLabel}</span>
              </div>
            </div>
            <div className="why-vs-marks">
              <span className={`why-mark ${locationAlign(preferences, job) === "✓" ? "ok" : "near"}`}>
                {locationAlign(preferences, job)}
              </span>
              <span className={`why-mark ${experienceAlign(applicant, job) === "✓" ? "ok" : "near"}`}>
                {experienceAlign(applicant, job)}
              </span>
              <span className={`why-mark ${ctcAlign(preferences, job) === "✓" ? "ok" : "near"}`}>
                {ctcAlign(preferences, job)}
              </span>
            </div>
            <div className="why-vs-col">
              <div className="why-vs-h">This role</div>
              <JobFacts job={job} />
            </div>
          </div>
        </section>

        {/* ---- trust + next step ---- */}
        <section className="why-trust rise d3">
          <div className="why-trust-note">
            <span className="kicker ink">Before you apply</span>
            <p className="why-trust-text">
              {employer.verified
                ? `${employer.name} is a verified employer. `
                : `${employer.name} hasn't completed verification yet. `}
              If you apply, your résumé is shared — and every recruiter view of it is logged, so the
              disclosure is on the record.
            </p>
          </div>
          <div className="why-actions">
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
            <span className="tag verified why-applied">Applied · {ago(application.updated_at)}</span>
          )}
        </section>

        <div className="why-foot">
          <Link to={backToJob} className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to the role
          </Link>
          <Link to="/explore" className="link-arrow" style={{ fontSize: 13 }}>
            Back to feed →
          </Link>
        </div>

        <div style={{ height: 60 }} />
      </div>
    </>
  );
}
