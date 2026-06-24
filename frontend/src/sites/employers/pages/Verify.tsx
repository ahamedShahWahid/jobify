import { useEffect } from "react";
import { Link } from "react-router-dom";
import { CONSOLE_URL } from "../EmployersRoutes";
import { Footer, Masthead } from "../components/Chrome";

export function Verify() {
  // Land at the top — HashRouter preserves scroll between routes otherwise.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <>
      <Masthead />

      <section className="verify-hero">
        <div className="wrap">
          <Link to="/employers" className="back-link">
            <span aria-hidden="true">←</span> Back to overview
          </Link>
          <p className="label amber rise d1">Trust &amp; verification</p>
          <h1 className="rise d2">
            Get the badge applicants trust.
          </h1>
          <p className="deck rise d3" style={{ marginTop: 20 }}>
            Verification confirms there&apos;s a real, registered organisation behind your
            roles. It&apos;s a short review — and once you&apos;re verified, the badge appears
            on every job you post.
          </p>
        </div>
      </section>

      <div className="wrap">
        <div className="rule" />
      </div>

      {/* ---- what we check ---------------------------------------------- */}
      <section>
        <div className="wrap">
          <div className="section-head">
            <p className="label amber">What we check</p>
            <h2>A real organisation, confirmed.</h2>
            <p className="deck">
              Lightweight and document-based. We&apos;re confirming legitimacy, not auditing
              your business.
            </p>
          </div>
          <div className="checks">
            <div className="check rise d1">
              <span className="ic" aria-hidden="true">GST</span>
              <div>
                <h3>GST registration</h3>
                <p>
                  Your GSTIN, matched against the registered legal name. The primary proof
                  of a real entity.
                </p>
              </div>
            </div>
            <div className="check rise d2">
              <span className="ic" aria-hidden="true">@</span>
              <div>
                <h3>Company domain</h3>
                <p>
                  A quick check that the recruiter email maps to the organisation&apos;s
                  domain.
                </p>
              </div>
            </div>
            <div className="check rise d3">
              <span className="ic" aria-hidden="true">ID</span>
              <div>
                <h3>Authorised contact</h3>
                <p>
                  Confirmation that the person setting up hiring is authorised to represent
                  the organisation.
                </p>
              </div>
            </div>
            <div className="check rise d4">
              <span className="ic" aria-hidden="true">↻</span>
              <div>
                <h3>Periodic re-check</h3>
                <p>
                  Verification is refreshed over time so the badge keeps meaning something
                  to candidates.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---- the steps -------------------------------------------------- */}
      <section>
        <div className="wrap">
          <div className="section-head">
            <p className="label amber">The procedure</p>
            <h2>Four steps to verified.</h2>
          </div>
          <div className="vsteps">
            <div className="vstep rise d1">
              <span className="vno" />
              <div>
                <h3>Create your employer workspace</h3>
                <p>
                  Sign in to the console and set up your organisation. This makes you the
                  owner and unlocks role posting.
                </p>
              </div>
            </div>
            <div className="vstep rise d2">
              <span className="vno" />
              <div>
                <h3>Submit your details</h3>
                <p>
                  Add your GSTIN and confirm your company domain. It takes a couple of
                  minutes — no paperwork uploads beyond the identifiers.
                </p>
              </div>
            </div>
            <div className="vstep rise d3">
              <span className="vno" />
              <div>
                <h3>We review</h3>
                <p>
                  A short check matches your registration against public records. You&apos;ll
                  hear back quickly; nothing about your roles is blocked while you wait.
                </p>
              </div>
            </div>
            <div className="vstep rise d4">
              <span className="vno" />
              <div>
                <h3>The badge goes live</h3>
                <p>
                  Once approved, the verified-employer badge appears on every role you post —
                  present and future — automatically.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---- the payoff ------------------------------------------------- */}
      <section id="verified">
        <div className="wrap">
          <div className="trust-grid">
            <div className="trust-card rise d1">
              <span className="verified-badge">
                <span className="chk" aria-hidden="true">✓</span>
                Verified employer
              </span>
              <h3>Why it earns applicant trust.</h3>
              <p>
                Candidates spend real effort on every application. The verified badge tells
                them the role is backed by a real organisation before they commit — and
                verified posts consistently draw stronger response.
              </p>
            </div>
            <div className="trust-card dark rise d2">
              <span className="label" style={{ color: "var(--accent)" }}>
                Disclosure you can stand behind
              </span>
              <h3 style={{ color: "var(--paper)" }}>Audited from the first view.</h3>
              <p>
                Verification pairs with our append-only audit trail: every résumé you open
                is logged. Trust runs both ways — candidates trust verified employers, and
                your data handling stays defensible.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---- cta -------------------------------------------------------- */}
      <section className="cta">
        <div className="wrap">
          <div className="panel">
            <p className="label" style={{ color: "var(--accent)" }}>
              Ready when you are
            </p>
            <h2>Get verified in the console.</h2>
            <p className="deck">
              Set up your workspace, submit your details, and post your first role free —
              verification runs alongside.
            </p>
            <div className="hero-cta">
              <a className="btn btn-amber" href={CONSOLE_URL} target="_blank" rel="noreferrer">
                Open the console <span className="arrow" aria-hidden="true">→</span>
              </a>
              <Link
                to="/employers"
                className="btn btn-ghost"
                style={{ color: "var(--paper)", borderColor: "rgba(243,244,241,0.3)" }}
              >
                Back to overview
              </Link>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
