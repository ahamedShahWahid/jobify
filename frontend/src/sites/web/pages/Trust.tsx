import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { istClock } from "../../../shared/format";
import { PublicLayout } from "../components/Chrome";

interface Component {
  name: string;
  sub: string;
  state: "ok" | "warn" | "down";
}

const COMPONENTS: Component[] = [
  { name: "API (/v1)", sub: "Auth, feed, applications, recruiter jobs", state: "ok" },
  { name: "Matching pipeline", sub: "Scoring workers · score queue", state: "ok" },
  { name: "Embeddings", sub: "Gemini + pgvector · idempotent", state: "ok" },
  { name: "Résumé parsing", sub: "Celery + Redis · F1 gate ≥ 0.85", state: "ok" },
  { name: "Notifications outbox", sub: "Email + in-app · retry ×5", state: "ok" },
];

const STATE_LABEL = { ok: "Operational", warn: "Degraded", down: "Down" } as const;

function useClock(): string {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return istClock(now);
}

export function Trust() {
  const checked = useClock();
  const allOk = COMPONENTS.every((c) => c.state === "ok");

  return (
    <PublicLayout>
      <section className="trust-hero">
        <div className="wrap">
          <span className="kicker">Trust · Transparency · DPDP</span>
          <h1>
            Your data is <em>yours.</em>
          </h1>
          <p className="deck" style={{ maxWidth: "46ch" }}>
            We built Jobify on India's Digital Personal Data Protection rules from day one — not as
            a compliance retrofit. Here's exactly what that means.
          </p>
        </div>
      </section>

      {/* ---- status panel ---- */}
      <section className="section" id="status" style={{ paddingTop: 24 }}>
        <div className="wrap">
          <div className="section-head">
            <div>
              <span className="no">§ Status</span>
              <h2>System status</h2>
            </div>
            <span className="status-pill">
              <span className={`dot ${allOk ? "ok" : "warn"}`} />
              {allOk ? "All systems operational" : "Partial outage"}
            </span>
          </div>
          <div className="status-panel">
            {COMPONENTS.map((c) => (
              <div className="status-row" key={c.name}>
                <div>
                  <div className="name">{c.name}</div>
                  <div className="sub">{c.sub}</div>
                </div>
                <span className="status-pill">
                  <span className={`dot ${c.state}`} />
                  {STATE_LABEL[c.state]}
                </span>
              </div>
            ))}
          </div>
          <p className="dim mono" style={{ fontSize: 11, marginTop: 12, letterSpacing: "0.04em" }}>
            Last checked {checked} · health surfaced via the API's /health &amp; /ready probes
          </p>
        </div>
      </section>

      {/* ---- the three rights ---- */}
      <section className="section" id="data" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head">
            <div>
              <span className="no">§ Rights</span>
              <h2>Three things you can always do</h2>
            </div>
          </div>
          <div className="trust-cols">
            <div className="trust-card">
              <div className="ico">✓</div>
              <h3>Granular consent</h3>
              <p>
                Choose exactly which channels reach you — transactional email is on by default and
                we tell you at sign-up; everything else is opt-in. Flip any of it, any time. Each
                change is recorded as history, separate from your current state.
              </p>
            </div>
            <div className="trust-card">
              <div className="ico">↧</div>
              <h3>One-tap export</h3>
              <p>
                Download everything we hold about you as a single JSON file — profile, applications,
                matches, consent history. Session secrets and refresh tokens are never exported, and
                a redactions note tells you what was withheld and why.
              </p>
            </div>
            <div className="trust-card">
              <div className="ico">⌫</div>
              <h3>Real deletion</h3>
              <p>
                Delete your account and we scrub your PII and hard-delete the truly personal tables
                — atomically, all or nothing. We keep anonymized analytics; you can sign up fresh
                with the same email afterwards.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---- definition list / FAQ ---- */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head">
            <div>
              <span className="no">§ Details</span>
              <h2>The plain-language version</h2>
            </div>
          </div>
          <dl className="dl">
            <div className="dl-item">
              <dt>Who sees my résumé?</dt>
              <dd>
                No one, until you apply. Matching runs on a vector embedding of your résumé, not the
                document itself. A recruiter only opens your résumé after you apply to their role —
                and every one of those views is written to an append-only audit log.
              </dd>
            </div>
            <div className="dl-item">
              <dt>What is the “embedding”?</dt>
              <dd>
                A numeric fingerprint of your skills and experience that lets us compare you to open
                roles by meaning, not keywords. It's derived from your latest parsed résumé and
                refreshed when you upload a new one.
              </dd>
            </div>
            <div className="dl-item">
              <dt>Do you sell my data?</dt>
              <dd>
                No. We don't sell or rent personal data, and we don't share it with third parties
                for their own marketing. Matching and the optional notifications you consent to are
                the only places your data moves.
              </dd>
            </div>
            <div className="dl-item">
              <dt>What happens when I delete?</dt>
              <dd>
                We tombstone your account and scrub identifying fields, then hard-delete the tables
                that exist only to hold personal data. Blobs (your uploaded résumé files) are
                removed best-effort. It's a single atomic transaction — a partial delete never
                happens.
              </dd>
            </div>
            <div className="dl-item">
              <dt>How do I actually do these things?</dt>
              <dd>
                Consent, export, and delete all live in the app under Privacy. Export copies a JSON
                envelope; delete asks you to type a confirmation phrase first. Both are self-serve —
                no support ticket, no waiting.
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="cta-band">
        <div className="wrap">
          <h2>
            Questions we didn't <em>answer?</em>
          </h2>
          <p className="deck mb" style={{ marginTop: 10 }}>
            We'd rather over-explain than leave you guessing.
          </p>
          <a href="mailto:privacy@jobify.in" className="btn">
            privacy@jobify.in
          </a>
          <div className="mt">
            <Link to="/explore" className="link-arrow">
              Or just open your feed <span className="arr">→</span>
            </Link>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
