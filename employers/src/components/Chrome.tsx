import { Link } from "react-router-dom";
import { CONSOLE_URL } from "../App";

/** Sticky masthead shared across pages. `onLanding` enables in-page anchors. */
export function Masthead({ onLanding = false }: { onLanding?: boolean }) {
  return (
    <header className="masthead">
      <div className="wrap masthead-inner">
        <Link to="/" className="wordmark" aria-label="Jobify for employers — home">
          <span className="glyph" aria-hidden="true">
            J
          </span>
          Jobify
          <span className="sub">for employers</span>
        </Link>
        <nav className="mast-nav" aria-label="Primary">
          {onLanding ? (
            <>
              <a href="#how">How it works</a>
              <a href="#verified">Why verified</a>
              <a href="#pricing">Pricing</a>
              <a href="#faq">FAQ</a>
            </>
          ) : (
            <>
              <Link to="/#how">How it works</Link>
              <Link to="/verify">Get verified</Link>
              <Link to="/#pricing">Pricing</Link>
              <Link to="/#faq">FAQ</Link>
            </>
          )}
        </nav>
        <div className="mast-cta">
          <a
            className="btn btn-primary btn-sm"
            href={CONSOLE_URL}
            target="_blank"
            rel="noreferrer"
          >
            Open the console <span className="arrow" aria-hidden="true">→</span>
          </a>
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="site">
      <div className="wrap">
        <div className="foot-grid">
          <div className="col foot-brand">
            <Link to="/" className="wordmark" aria-label="Jobify for employers — home">
              <span className="glyph" aria-hidden="true">
                J
              </span>
              Jobify
              <span className="sub">for employers</span>
            </Link>
            <p>
              A placement platform that ranks applicants by fit and explains why —
              so hiring teams read reasons, not résumé piles.
            </p>
          </div>
          <div className="col">
            <h4>Product</h4>
            <a href="/#how">How it works</a>
            <a href="/#showcase">Match reasoning</a>
            <Link to="/verify">Get verified</Link>
            <a href="/#pricing">Pricing</a>
          </div>
          <div className="col">
            <h4>For applicants</h4>
            <a href="http://localhost:5273" target="_blank" rel="noreferrer">
              Jobify for candidates
            </a>
            <span className="faint">Find roles that fit, explained</span>
          </div>
          <div className="col">
            <h4>Access</h4>
            <a href={CONSOLE_URL} target="_blank" rel="noreferrer">
              Console sign-in
            </a>
            <a href="mailto:hello@jobify.in">hello@jobify.in</a>
          </div>
        </div>
        <div className="foot-bottom">
          <span>JOBIFY · FOR EMPLOYERS — © 2026</span>
          <span>DPDP-aligned · Audited résumé access · Made in India</span>
        </div>
      </div>
    </footer>
  );
}
