import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PublicLayout } from "../components/Chrome";

/** Count a 0.xx score up on mount — the hero's small moment of delight. */
function useCountUp(target: number, ms = 1100): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setV(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - t, 3);
      setV(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}

const TICKER = [
  ["0.94", "Staff ML Engineer", "Bengaluru"],
  ["0.91", "Data Platform Engineer", "Remote (IN)"],
  ["0.88", "Backend Engineer", "Hybrid"],
  ["0.86", "Product Designer", "Mumbai"],
  ["0.83", "Payments Engineer", "Bengaluru"],
  ["0.79", "Firmware Engineer", "Pune"],
];

export function Landing() {
  const score = useCountUp(0.91);

  return (
    <PublicLayout>
      {/* ---- hero ---- */}
      <section className="hero">
        <div className="wrap hero-grid">
          <div>
            <span className="kicker rise">No. 01 — The matched feed</span>
            <h1 className="rise d1">
              <span className="line">Work that</span>
              <span className="line">
                fits, <em>explained.</em>
              </span>
            </h1>
            <p className="deck hero-deck rise d2">
              Upload your résumé once. Jobify reads it, finds the roles that genuinely match — and
              tells you, in one honest line, why each one does.
            </p>
            <div className="hero-cta rise d3">
              <Link to="/welcome" className="btn primary">
                Build my feed →
              </Link>
              <Link to="/explore" className="link-arrow">
                I already have a feed <span className="arr">→</span>
              </Link>
            </div>
          </div>

          {/* signature match card */}
          <div className="matchcard rise d3">
            <div className="matchcard-top">
              <div>
                <span className="kicker">Today's top match</span>
                <h3>Senior Data Platform Engineer</h3>
                <div className="where">
                  Meridian Analytics · <span className="accent">✓ Verified</span> · Bengaluru
                </div>
              </div>
              <div className="matchcard-score num">
                <sub>FIT</sub>
                {score.toFixed(2)}
              </div>
            </div>
            <div className="matchcard-body">
              <div className="explain">
                <div className="fit">
                  “Your Spark + Iceberg lakehouse work maps almost exactly onto how this team feeds
                  its scoring pipelines.”
                </div>
                <div className="caveat">The band tops out a little below your expectation.</div>
              </div>
              <div className="bars">
                {[
                  ["Skills", 0.88, true],
                  ["Experience", 0.95, false],
                  ["Location", 0.95, false],
                  ["Title", 0.99, false],
                ].map(([label, val, acc]) => (
                  <div className="bar-row" key={label as string}>
                    <span>{label}</span>
                    <span className="bar-track">
                      <span
                        className={`bar-fill${acc ? " acc" : ""}`}
                        style={{ width: `${(val as number) * 100}%` }}
                      />
                    </span>
                    <span className="num">{(val as number).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---- ticker ---- */}
      <div className="ticker" aria-hidden>
        <div className="ticker-track">
          {[...TICKER, ...TICKER].map(([s, title, where], i) => (
            <span className="ticker-item" key={i}>
              <span className="s">{s}</span> {title} <span style={{ opacity: 0.6 }}>· {where}</span>
            </span>
          ))}
        </div>
      </div>

      {/* ---- how it works ---- */}
      <section className="section" id="how">
        <div className="wrap">
          <div className="section-head">
            <div>
              <span className="no">§ 02</span>
              <h2>Three steps, no busywork</h2>
            </div>
            <span className="deck" style={{ maxWidth: "24ch", textAlign: "right" }}>
              Matching should feel like a good editor, not a keyword filter.
            </span>
          </div>
          <div className="steps">
            <div className="step rise">
              <div className="n">Step 1 of 3</div>
              <h3>Upload your résumé</h3>
              <p>
                PDF or DOCX, once. We extract your skills, experience, and the shape of what you've
                built — and never send your résumé to a recruiter unless you apply.
              </p>
            </div>
            <div className="step rise d1">
              <div className="n">Step 2 of 3</div>
              <h3>We read &amp; embed it</h3>
              <p>
                Your profile becomes a vector. Open roles are scored against it on skills,
                experience, location, and title — not a bag of keywords.
              </p>
            </div>
            <div className="step rise d2">
              <div className="n">Step 3 of 3</div>
              <h3>Matches surface — with a reason</h3>
              <p>
                Only roles above the bar appear in your feed, each with a one-line “why this fits”
                and an honest caveat. You decide what to do next.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---- showcase: the explanation ---- */}
      <section className="showcase">
        <div className="wrap">
          <div>
            <span className="kicker">The difference</span>
            <p className="deck" style={{ color: "var(--paper)", opacity: 0.8, marginTop: 14 }}>
              Most job boards hand you a number. We hand you a sentence.
            </p>
          </div>
          <h2>
            Every match arrives with <b>a fit, a caveat, and the four scores</b> behind it — so you
            never wonder why a role landed in your feed.
          </h2>
        </div>
      </section>

      {/* ---- split: applicants / recruiters ---- */}
      <section className="section" id="recruiters">
        <div className="wrap">
          <div className="section-head">
            <div>
              <span className="no">§ 03</span>
              <h2>Two sides, one ledger</h2>
            </div>
          </div>
          <div className="split">
            <div className="split-col">
              <span className="kicker">For applicants</span>
              <h3>A feed that respects you.</h3>
              <ul>
                <li>
                  <span className="mk">—</span> Only roles that clear the match threshold appear.
                  No spam, no “you might also like.”
                </li>
                <li>
                  <span className="mk">—</span> Every card explains itself, caveats included.
                </li>
                <li>
                  <span className="mk">—</span> Apply or save in one tap; your résumé moves only
                  when you do.
                </li>
                <li>
                  <span className="mk">—</span> Export or delete everything, any time.
                </li>
              </ul>
              <Link to="/explore" className="btn ink sm mt">
                Open my feed →
              </Link>
            </div>
            <div className="split-col">
              <span className="kicker">For recruiters</span>
              <h3>Ranked applicants, not a résumé pile.</h3>
              <ul>
                <li>
                  <span className="mk">—</span> Post a role; we surface it to the candidates it
                  actually fits.
                </li>
                <li>
                  <span className="mk">—</span> See each applicant with a match score and the
                  reasoning.
                </li>
                <li>
                  <span className="mk">—</span> Verified-employer badge earns applicant trust.
                </li>
                <li>
                  <span className="mk">—</span> Every résumé view is audited — disclosure you can
                  stand behind.
                </li>
              </ul>
              <a href="mailto:hello@jobify.in" className="btn ghost sm mt">
                Talk to us →
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ---- trust teaser ---- */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div
            className="spread"
            style={{ border: "2px solid var(--ink)", padding: "28px 30px", background: "var(--paper-2)" }}
          >
            <div style={{ maxWidth: "46ch" }}>
              <span className="kicker">Built for DPDP</span>
              <p className="serif italic" style={{ fontSize: 22, margin: "10px 0 0", lineHeight: 1.3 }}>
                Your data is yours. Granular consent, one-tap export, real deletion — not a setting
                buried six screens deep.
              </p>
            </div>
            <Link to="/trust" className="btn">
              Read the trust page →
            </Link>
          </div>
        </div>
      </section>

      {/* ---- CTA band ---- */}
      <section className="cta-band">
        <div className="wrap">
          <h2>
            Stop scrolling job boards. <br />
            Start reading <em>your</em> feed.
          </h2>
          <p className="deck mb" style={{ marginTop: 10 }}>
            Six matches are waiting in the demo. No sign-up to look.
          </p>
          <Link to="/explore" className="btn primary">
            Open my feed →
          </Link>
        </div>
      </section>
    </PublicLayout>
  );
}
