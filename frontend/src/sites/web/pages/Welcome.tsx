import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { Masthead } from "../components/Chrome";
import { ctcBand } from "../components/bits";
import { useSessionStore } from "../session";

/**
 * First-run applicant funnel — a guided résumé flow in the warm editorial style.
 * Public route (pre-feed); the final step calls connectDemo() and opens /explore.
 * No real upload happens: this is the illustrative front-door to the live
 * Celery parse + embeddings pipeline.
 */

type StepId = "intent" | "upload" | "parsing" | "profile" | "matches";

const STEPS: { id: StepId; label: string }[] = [
  { id: "intent", label: "Start" },
  { id: "upload", label: "Résumé" },
  { id: "parsing", label: "Reading" },
  { id: "profile", label: "Profile" },
  { id: "matches", label: "Matches" },
];

/** The illustrative parsed profile — mirrors DemoClient.me() with a believable skill set. */
const PARSED = {
  full_name: "You",
  locations: ["Bengaluru"],
  years_experience: "6",
  notice_period_days: 60,
  current_ctc: "2800000",
  expected_ctc: "4000000",
  skills: ["Python", "FastAPI", "PostgreSQL", "pgvector", "Spark", "async"],
};

/** The parsing checklist — staggered reveal that mirrors the real pipeline stages. */
const PARSE_STAGES = [
  "Extracting contact",
  "Reading experience",
  "Mapping skills",
  "Embedding your profile",
  "Scoring open roles",
];

/** Teaser matches for the final step — three roles that clear the bar. */
const TEASERS = [
  { score: 0.91, title: "Senior Data Platform Engineer", org: "Meridian Analytics", fit: "Your Spark + Iceberg work maps almost exactly onto their scoring pipelines." },
  { score: 0.86, title: "ML Engineer — Matching", org: "Karkhana Robotics", fit: "Embeddings, ranking, and the explanation layer — the exact trio you've shipped." },
  { score: 0.83, title: "Backend Engineer (FastAPI)", org: "Lumen Health", fit: "Async SQLAlchemy and an audit trail you can stand behind." },
];

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;

function ProgressRail({ current }: { current: StepId }) {
  const idx = STEPS.findIndex((s) => s.id === current);
  return (
    <ol className="wl-rail" aria-label="Onboarding progress">
      {STEPS.map((s, i) => (
        <li
          key={s.id}
          className={`wl-rail-seg${i === idx ? " on" : ""}${i < idx ? " done" : ""}`}
        >
          <span className="wl-rail-no num">{String(i + 1).padStart(2, "0")}</span>
          <span className="wl-rail-label">{s.label}</span>
        </li>
      ))}
    </ol>
  );
}

/** Step 3 — the animated "reading your résumé" checklist; the delight moment. */
function ParsingStep({ onDone }: { onDone: () => void }) {
  const [filled, setFilled] = useState(prefersReducedMotion() ? PARSE_STAGES.length : 0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      const t = setTimeout(onDone, 400);
      return () => clearTimeout(t);
    }
    const timers: number[] = [];
    PARSE_STAGES.forEach((_, i) => {
      timers.push(
        window.setTimeout(() => setFilled(i + 1), 360 + i * 480),
      );
    });
    timers.push(window.setTimeout(onDone, 360 + PARSE_STAGES.length * 480 + 520));
    return () => timers.forEach(clearTimeout);
  }, [onDone]);

  return (
    <div className="wl-step rise">
      <span className="kicker">Step 03 — Reading</span>
      <h1 className="wl-h">Reading your résumé.</h1>
      <p className="deck wl-deck">
        This is what the real pipeline does on upload — parse, extract, embed, then score every
        open role against your profile.
      </p>
      <ul className="wl-checklist">
        {PARSE_STAGES.map((stage, i) => {
          const state = i < filled ? "done" : i === filled ? "active" : "pending";
          return (
            <li key={stage} className={`wl-check ${state}`}>
              <span className="wl-check-mark" aria-hidden>
                {state === "done" ? "✓" : state === "active" ? "◐" : "○"}
              </span>
              <span className="wl-check-label">{stage}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function Welcome() {
  const navigate = useNavigate();
  const { connectDemo } = useSessionStore();
  const [step, setStep] = useState<StepId>("intent");
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const expectedBand = useMemo(() => {
    const cur = Number(PARSED.current_ctc);
    const exp = Number(PARSED.expected_ctc);
    return ctcBand(Number.isFinite(cur) ? cur : null, Number.isFinite(exp) ? exp : null);
  }, []);

  const chooseFile = useCallback((name: string) => {
    setFileName(name);
    setStep("parsing");
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files?.[0];
      if (f) chooseFile(f.name);
    },
    [chooseFile],
  );

  const openFeed = useCallback(async () => {
    setOpening(true);
    setError(null);
    try {
      await connectDemo();
      navigate("/explore");
    } catch (e) {
      setError(errorMessage(e));
      setOpening(false);
    }
  }, [connectDemo, navigate]);

  return (
    <>
      <Masthead />
      <div className="wrap wl-wrap">
        <ProgressRail current={step} />

        {error && <div className="notice err">⚠ {error}</div>}

        {/* ---- 1 · intent ---- */}
        {step === "intent" && (
          <div className="wl-step rise">
            <span className="kicker">Step 01 — Welcome</span>
            <h1 className="wl-h">
              Let's build <em>your feed.</em>
            </h1>
            <p className="deck wl-deck">
              Upload your résumé once. Jobify reads it, extracts your skills and experience, scores
              every open role against your profile — and tells you, in one honest line, why each one
              fits.
            </p>
            <p className="wl-body">
              No endless forms. No keyword roulette. Just the roles that genuinely match, with the
              reasoning shown.
            </p>
            <div className="wl-actions">
              <button className="btn primary" onClick={() => setStep("upload")}>
                Continue →
              </button>
              <Link to="/explore" className="link-arrow wl-skip">
                I have a live token
              </Link>
            </div>
          </div>
        )}

        {/* ---- 2 · upload ---- */}
        {step === "upload" && (
          <div className="wl-step rise">
            <span className="kicker">Step 02 — Your résumé</span>
            <h1 className="wl-h">Drop in your résumé.</h1>
            <p className="deck wl-deck">
              We'll read it, extract your skills and experience, and never send it to a recruiter
              unless you apply.
            </p>

            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) chooseFile(f.name);
              }}
            />
            <div
              className={`wl-drop${dragging ? " over" : ""}`}
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  inputRef.current?.click();
                }
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <span className="wl-drop-ico" aria-hidden>
                ⇪
              </span>
              <span className="wl-drop-title serif">Drag &amp; drop, or click to browse</span>
              <span className="wl-drop-sub">PDF or DOCX · stays in your browser for this demo</span>
              {fileName && <span className="tag accent num wl-drop-file">{fileName}</span>}
            </div>

            <div className="wl-actions">
              <button
                className="btn ghost"
                onClick={() => chooseFile("sample-resume.pdf")}
              >
                Use a sample résumé
              </button>
              <button className="btn ink" onClick={() => setStep("intent")}>
                ← Back
              </button>
            </div>
          </div>
        )}

        {/* ---- 3 · parsing ---- */}
        {step === "parsing" && <ParsingStep onDone={() => setStep("profile")} />}

        {/* ---- 4 · profile reveal ---- */}
        {step === "profile" && (
          <div className="wl-step rise">
            <span className="kicker">Step 04 — What we read</span>
            <h1 className="wl-h">Here's what we read.</h1>
            <p className="deck wl-deck">
              Pulled straight from {fileName ?? "your résumé"}. Edit any of it later in your profile.
            </p>

            <div className="wl-profile">
              <div className="wl-profile-head">
                <div>
                  <div className="kicker ink">Profile</div>
                  <div className="wl-profile-name serif">{PARSED.full_name}</div>
                </div>
                <span className="tag verified">Parsed ✓</span>
              </div>
              <div className="wl-profile-grid">
                <div className="factline">
                  <span className="k">Location</span>
                  <span className="v">{PARSED.locations.join(" · ")}</span>
                </div>
                <div className="factline">
                  <span className="k">Experience</span>
                  <span className="v num">{PARSED.years_experience} yrs</span>
                </div>
                <div className="factline">
                  <span className="k">Notice period</span>
                  <span className="v num">{PARSED.notice_period_days} days</span>
                </div>
                <div className="factline">
                  <span className="k">Expected band</span>
                  <span className="v num">{expectedBand}</span>
                </div>
              </div>
              <div className="wl-profile-skills">
                <div className="kicker ink mb-sm">Skills</div>
                <div className="wl-chips">
                  {PARSED.skills.map((s) => (
                    <span key={s} className="tag">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <p className="wl-note dim">↳ Edit later in your profile — nothing here is final.</p>

            <div className="wl-actions">
              <button className="btn primary" onClick={() => setStep("matches")}>
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* ---- 5 · first matches / done ---- */}
        {step === "matches" && (
          <div className="wl-step rise">
            <span className="kicker">Step 05 — Your feed is ready</span>
            <h1 className="wl-h">
              <span className="num">3</span> roles already clear your bar.
            </h1>
            <p className="deck wl-deck">
              Scored against your parsed profile. Here's a glimpse — open the feed to see all six,
              each with its full breakdown.
            </p>

            <div className="wl-teasers">
              {TEASERS.map((t, i) => (
                <div key={t.title} className={`wl-teaser rise d${i + 1}`}>
                  <div className="wl-teaser-score mono num">{t.score.toFixed(2)}</div>
                  <div className="wl-teaser-body">
                    <div className="wl-teaser-title serif">{t.title}</div>
                    <div className="wl-teaser-org dim">{t.org}</div>
                    <div className="wl-teaser-fit">“{t.fit}”</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="wl-actions">
              <button className="btn primary" onClick={openFeed} disabled={opening}>
                {opening ? "Opening…" : "Open my feed →"}
              </button>
              <Link to="/explore" className="link-arrow wl-skip">
                I have a live token
              </Link>
            </div>
          </div>
        )}

        <div style={{ height: 60 }} />
      </div>
    </>
  );
}
