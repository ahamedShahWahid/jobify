import { Link } from "react-router-dom";
import { Footer, Masthead } from "../components/Chrome";
import { Ledger } from "../components/Ledger";

export function Landing() {
  return (
    <>
      <Masthead onLanding />

      {/* ---- hero: the ledger is the thesis ------------------------------ */}
      <section className="hero">
        <div className="wrap">
          <p className="label rise d1">For hiring teams &amp; engineering leaders</p>
          <h1 className="rise d2">
            Read the reasons,
            <br />
            not the résumé pile.
          </h1>
          <p className="deck rise d3">
            Post a role. Jobify surfaces it to the candidates it fits, then hands you
            each applicant ranked — with a one-line reason and an honest caveat.
          </p>
          <div className="hero-cta rise d3">
            <Link className="btn btn-primary" to="/employers/signin">
              Sign in <span className="arrow" aria-hidden="true">→</span>
            </Link>
            <Link className="textlink" to="/employers#how">
              See how it works
            </Link>
          </div>
          <div className="ledger-wrap rise d4">
            <Ledger />
          </div>
        </div>
      </section>

      {/* ---- stat / credential band ------------------------------------- */}
      <section className="band">
        <div className="wrap">
          <div className="stats">
            <div className="stat rise d1">
              <div className="lab">Audited access</div>
              <div className="head">Every résumé view logged</div>
              <p>An append-only trail on every applicant disclosure — defensible by design.</p>
            </div>
            <div className="stat rise d2">
              <div className="lab">Verified employer</div>
              <div className="head">A trust badge applicants read</div>
              <p>Verification earns response. Candidates see who&apos;s real before they apply.</p>
            </div>
            <div className="stat rise d3">
              <div className="lab">Explained match</div>
              <div className="head">Score + reason, per applicant</div>
              <p>Each candidate arrives with a fit score and the model&apos;s one-line rationale.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ---- how it works ------------------------------------------------ */}
      <section id="how">
        <div className="wrap">
          <div className="section-head">
            <p className="label">Procedure · for employers</p>
            <h2>Four steps from role to hire.</h2>
            <p className="deck">
              A drafting-table workflow: post once, let the matching engine do the
              fan-out, then review what fits.
            </p>
          </div>
          <div className="steps">
            <article className="step rise d1">
              <div className="no">01</div>
              <h3>Post a role</h3>
              <p>
                Title, description, locations, experience and CTC band. We embed it and
                add it to the matching index.
              </p>
            </article>
            <article className="step rise d2">
              <div className="no">02</div>
              <h3>We surface it</h3>
              <p>
                The role reaches candidates whose profiles fit — pushed into their feed,
                not blasted to a list.
              </p>
            </article>
            <article className="step rise d3">
              <div className="no">03</div>
              <h3>Review the ranked stack</h3>
              <p>
                Applicants arrive ordered by match score, each with a one-line reason and
                a caveat. Skim the signal.
              </p>
            </article>
            <article className="step rise d4">
              <div className="no">04</div>
              <h3>Hire with a trail</h3>
              <p>
                Open a résumé — the view is audited. Move forward with disclosure you can
                stand behind.
              </p>
            </article>
          </div>
        </div>
      </section>

      <div className="wrap">
        <div className="rule" />
      </div>

      {/* ---- "why this fits" showcase ----------------------------------- */}
      <section id="showcase">
        <div className="wrap showcase">
          <div className="copy">
            <p className="label">The applicant row</p>
            <h2>You see why — not a keyword match.</h2>
            <p>
              Every applicant comes scored against the role, with the model&apos;s reasoning
              and an honest caveat. It&apos;s the difference between &ldquo;contains the word
              Postgres&rdquo; and &ldquo;shipped a sharded Postgres migration at scale.&rdquo;
            </p>
            <ul>
              <li>
                <span className="tick" aria-hidden="true">✓</span>
                <span>
                  <b>A fit score</b> from the role↔profile embedding, weighted across rules.
                </span>
              </li>
              <li>
                <span className="tick" aria-hidden="true">✓</span>
                <span>
                  <b>A one-line reason</b> — the strongest evidence the candidate fits.
                </span>
              </li>
              <li>
                <span className="tick" aria-hidden="true">✓</span>
                <span>
                  <b>A caveat</b> — where they&apos;re light, stated plainly. No hype.
                </span>
              </li>
            </ul>
          </div>
          <div className="applicant-row rise d2">
            <div className="ar-head">
              <span className="avatar" aria-hidden="true">
                RM
              </span>
              <div className="ar-id">
                <span className="nm">Riya M.</span>
                <span className="role">Backend Engineer · 5 yrs</span>
              </div>
              <div className="ar-score">
                <div className="v num">0.94</div>
                <div className="l">match</div>
              </div>
            </div>
            <div className="bar" aria-hidden="true">
              <span style={{ width: "94%" }} />
            </div>
            <div className="ar-grid">
              <div className="ar-cell fit">
                <div className="k">Why this fits</div>
                <p>
                  Led a zero-downtime Postgres shard migration — exactly the scale
                  challenge in the JD.
                </p>
              </div>
              <div className="ar-cell caveat">
                <div className="k">Caveat</div>
                <p>Kafka exposure is recent; the role leans on it heavily.</p>
              </div>
            </div>
            <div className="gen-line">
              <span className="dot" aria-hidden="true" />
              GENERATED · GEMINI-2.5-FLASH · v3
            </div>
          </div>
        </div>
      </section>

      {/* ---- verified trust --------------------------------------------- */}
      <section id="verified">
        <div className="wrap">
          <div className="section-head">
            <p className="label">Trust &amp; disclosure</p>
            <h2>Verified employers. Audited access.</h2>
            <p className="deck">
              Two mechanisms that make candidates trust you — and make your data
              handling defensible.
            </p>
          </div>
          <div className="trust-grid">
            <div className="trust-card rise d1">
              <span className="verified-badge">
                <span className="chk" aria-hidden="true">✓</span>
                Verified employer
              </span>
              <h3>A badge candidates actually read.</h3>
              <p>
                Verification confirms a real, registered organisation behind the role.
                Applicants respond more to verified posts — the badge is trust they can
                see before they spend a single résumé.{" "}
                <Link to="/employers/verify" className="textlink">
                  How verification works
                </Link>
              </p>
            </div>
            <div className="trust-card dark rise d2">
              <span className="label on-dark">Append-only audit</span>
              <h3>Every résumé view is logged.</h3>
              <p>
                Each disclosure of an applicant&apos;s résumé writes an immutable audit row.
                It&apos;s disclosure you can stand behind — and DPDP-aligned by construction.
              </p>
              <div className="audit-log" aria-hidden="true">
                <div className="row">
                  <span className="ts">14:02:11</span>
                  <span>resume.accessed · applicant 4f2a…</span>
                  <span className="who">recruiter@acme</span>
                </div>
                <div className="row">
                  <span className="ts">14:05:47</span>
                  <span>job.applicants_listed · 12 rows</span>
                  <span className="who">recruiter@acme</span>
                </div>
                <div className="row">
                  <span className="ts">14:09:03</span>
                  <span>resume.accessed · applicant 9c01…</span>
                  <span className="who">recruiter@acme</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---- pricing ----------------------------------------------------- */}
      <section id="pricing">
        <div className="wrap">
          <div className="section-head">
            <p className="label">Plans</p>
            <h2>Pricing that scales with hiring.</h2>
            <p className="deck">
              Illustrative tiers. Every plan includes match scores, reasons, and audited
              access — the differences are volume and team size.
            </p>
          </div>
          <div className="plans">
            <article className="plan rise d1">
              <div className="tier">Starter</div>
              <div className="price">
                ₹0<span className="per">/ first role</span>
              </div>
              <p className="blurb">Post your first role and see the ranked stack for free.</p>
              <ul>
                <li><span className="mk">+</span> 1 open role</li>
                <li><span className="mk">+</span> Ranked applicants with scores</li>
                <li><span className="mk">+</span> Match reason &amp; caveat</li>
                <li className="off"><span className="mk">–</span> Single seat</li>
                <li className="off"><span className="mk">–</span> Verified badge</li>
              </ul>
              <Link className="btn btn-ghost" to="/employers/signin">
                Start free
              </Link>
            </article>
            <article className="plan featured rise d2">
              <div className="tier">
                Team <span className="pill">POPULAR</span>
              </div>
              <div className="price">
                ₹24k<span className="per">/ month</span>
              </div>
              <p className="blurb">For active hiring teams running several roles at once.</p>
              <ul>
                <li><span className="mk">+</span> Up to 15 open roles</li>
                <li><span className="mk">+</span> Verified-employer badge</li>
                <li><span className="mk">+</span> 5 recruiter seats</li>
                <li><span className="mk">+</span> Full audit trail export</li>
                <li><span className="mk">+</span> Team &amp; invite management</li>
              </ul>
              <Link className="btn btn-primary" to="/employers/signin">
                Choose Team <span className="arrow" aria-hidden="true">→</span>
              </Link>
            </article>
            <article className="plan rise d3">
              <div className="tier">Scale</div>
              <div className="price">
                Custom<span className="per">/ talk to us</span>
              </div>
              <p className="blurb">High-volume hiring with SSO, controls, and support.</p>
              <ul>
                <li><span className="mk">+</span> Unlimited roles</li>
                <li><span className="mk">+</span> Unlimited seats &amp; SSO</li>
                <li><span className="mk">+</span> Custom match weights</li>
                <li><span className="mk">+</span> Priority verification</li>
                <li><span className="mk">+</span> Dedicated support</li>
              </ul>
              <a className="btn btn-ghost" href="mailto:hello@jobify.in">
                Contact sales
              </a>
            </article>
          </div>
        </div>
      </section>

      {/* ---- faq --------------------------------------------------------- */}
      <section id="faq">
        <div className="wrap">
          <div className="section-head">
            <p className="label">Questions</p>
            <h2>Frequently asked.</h2>
          </div>
          <dl className="faq">
            <div className="qa">
              <dt>
                <span className="q">Q1</span>How does the matching actually work?
              </dt>
              <dd>
                We embed each role and each candidate profile, then score the pair across
                weighted rules — vector similarity plus experience and location fit. Above a
                threshold, the role surfaces to the candidate and the applicant appears in
                your ranked stack with a score and an explanation.
              </dd>
            </div>
            <div className="qa">
              <dt>
                <span className="q">Q2</span>What does becoming a verified employer require?
              </dt>
              <dd>
                Proof of a registered organisation — typically your GST details and a domain
                check. It&apos;s a short review, and the badge then appears on every role you
                post.{" "}
                <Link to="/employers/verify" className="textlink">
                  See the steps
                </Link>
              </dd>
            </div>
            <div className="qa">
              <dt>
                <span className="q">Q3</span>How do you handle applicant data and DPDP?
              </dt>
              <dd>
                Consent is recorded per channel, every résumé view is written to an
                append-only audit log, and applicants can export or delete their data on
                request. Data handling is DPDP-aligned by construction, not bolted on.
              </dd>
            </div>
            <div className="qa">
              <dt>
                <span className="q">Q4</span>Can applicants control what recruiters see?
              </dt>
              <dd>
                Yes. Applicants manage notification consent and can request export or
                deletion. Recruiters only access a résumé through an audited disclosure —
                there&apos;s no silent download.
              </dd>
            </div>
            <div className="qa">
              <dt>
                <span className="q">Q5</span>Is the match reason reliable enough to act on?
              </dt>
              <dd>
                Treat it as triage, not a decision. The score ranks; the reason and caveat
                tell you where to look. You still read the résumé — but you read the right
                ones first.
              </dd>
            </div>
            <div className="qa">
              <dt>
                <span className="q">Q6</span>How do we get started?
              </dt>
              <dd>
                Sign in, create your employer workspace, and post your first role.
                The first role is free — you&apos;ll see the ranked stack before you commit
                to a plan.
              </dd>
            </div>
          </dl>
        </div>
      </section>

      {/* ---- cta band ---------------------------------------------------- */}
      <section className="cta">
        <div className="wrap">
          <div className="panel">
            <p className="label on-dark">Start hiring on signal</p>
            <h2>Read reasons, not résumé piles.</h2>
            <p className="deck">
              Post your first role free and see ranked applicants with a score and a
              reason on each. Sign-in is one click away.
            </p>
            <div className="hero-cta">
              <Link className="btn btn-invert" to="/employers/signin">
                Sign in <span className="arrow" aria-hidden="true">→</span>
              </Link>
              <Link to="/employers/verify" className="btn btn-ghost on-dark-ghost">
                Get verified first
              </Link>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
