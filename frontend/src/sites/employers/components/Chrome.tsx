import { Link } from "react-router-dom";
import { CONSOLE_URL } from "../EmployersRoutes";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";

// The brand lockup (mark + JOBIFY + "Job will find you") lives in the SVG asset;
// alt text carries the wordmark + punchline for a11y. The Link's aria-label stays
// surface-specific ("for employers — home").
const BRAND_ALT = "Jobify — Job will find you";

/** Sticky masthead shared across pages. `onLanding` enables in-page anchors. */
export function Masthead({ onLanding = false }: { onLanding?: boolean }) {
  return (
    <header className="masthead">
      <div className="wrap masthead-inner">
        <Link to="/employers" className="brand" aria-label="Jobify for employers — home">
          <img
            src="/jobify-logo.svg"
            alt={BRAND_ALT}
            className="brand-logo"
          />
        </Link>
        <nav className="mast-nav" aria-label="Primary">
          {onLanding ? (
            <>
              <Link to="/employers#how">How it works</Link>
              <Link to="/employers#verified">Why verified</Link>
              <Link to="/employers#pricing">Pricing</Link>
              <Link to="/employers#faq">FAQ</Link>
            </>
          ) : (
            <>
              <Link to="/employers#how">How it works</Link>
              <Link to="/employers/verify">Get verified</Link>
              <Link to="/employers#pricing">Pricing</Link>
              <Link to="/employers#faq">FAQ</Link>
            </>
          )}
        </nav>
        <div className="mast-cta">
          <ThemeToggle />
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
            <Link to="/employers" className="brand" aria-label="Jobify for employers — home">
              <img
                src="/jobify-logo.svg"
                alt={BRAND_ALT}
                className="brand-logo foot-logo"
              />
            </Link>
            <p>
              A placement platform that ranks applicants by fit and explains why —
              so hiring teams read reasons, not résumé piles.
            </p>
          </div>
          <div className="col">
            <h4>Product</h4>
            <Link to="/employers#how">How it works</Link>
            <Link to="/employers#showcase">Match reasoning</Link>
            <Link to="/employers/verify">Get verified</Link>
            <Link to="/employers#pricing">Pricing</Link>
          </div>
          <div className="col">
            <h4>For applicants</h4>
            <a href="#/" target="_blank" rel="noreferrer">
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
