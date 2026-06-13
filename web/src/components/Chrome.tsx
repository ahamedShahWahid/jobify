import { NavLink, Link } from "react-router-dom";
import type { ReactNode } from "react";

const EDITION = "Placement Press · Bengaluru";

export function Masthead() {
  return (
    <header className="masthead">
      <div className="masthead-row">
        <Link to="/" className="brand">
          <span className="logo">
            Jobify<span className="dot">.</span>
          </span>
          <span className="edition">{EDITION}</span>
        </Link>
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Home
          </NavLink>
          <a href="/#how">How it works</a>
          <NavLink to="/trust" className={({ isActive }) => (isActive ? "active" : "")}>
            Trust
          </NavLink>
          <NavLink to="/explore" className={({ isActive }) => (isActive ? "active" : "")}>
            Explore
          </NavLink>
          <Link to="/explore" className="btn primary sm nav-cta">
            Open my feed →
          </Link>
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="wrap">
        <div className="footer-grid">
          <div>
            <span className="logo serif" style={{ fontSize: 28, fontWeight: 900 }}>
              Jobify<span className="dot accent">.</span>
            </span>
            <p className="colophon mt">
              A placement platform that surfaces roles matched to your résumé — and tells you,
              plainly, why each one fits.
            </p>
          </div>
          <div>
            <h4>Product</h4>
            <Link to="/explore">Your feed</Link>
            <a href="/#how">How matching works</a>
            <a href="/#recruiters">For recruiters</a>
          </div>
          <div>
            <h4>Trust</h4>
            <Link to="/trust">Privacy &amp; consent</Link>
            <Link to="/trust#status">System status</Link>
            <Link to="/trust#data">How we use data</Link>
          </div>
          <div>
            <h4>Company</h4>
            <a href="/#how">About</a>
            <a href="mailto:hello@jobify.in">Contact</a>
            <Link to="/trust">DPDP &amp; your rights</Link>
          </div>
        </div>
        <div className="footer-base">
          <span>© {new Date().getFullYear()} Jobify · Made in India</span>
          <span>Set in Fraunces &amp; Hanken Grotesk</span>
        </div>
      </div>
    </footer>
  );
}

export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <Masthead />
      <main>{children}</main>
      <Footer />
    </>
  );
}
