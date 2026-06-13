/** The signature hero visual: a fanned stack of ranked applicant cards,
 *  each with a match score and a one-line "why this fits". Top card = best fit.
 *  Purely illustrative — no live data. */

interface Cand {
  cls: string;
  initials: string;
  name: string;
  role: string;
  score: string;
  pct: number;
  why: React.ReactNode;
}

const CANDIDATES: Cand[] = [
  {
    cls: "c0",
    initials: "RM",
    name: "Riya M.",
    role: "Backend Eng · 5 yrs",
    score: "0.94",
    pct: 94,
    why: (
      <>
        <b>Shipped a sharded Postgres migration</b> — the exact scale ask.
      </>
    ),
  },
  {
    cls: "c1",
    initials: "DK",
    name: "Dev K.",
    role: "Platform Eng · 6 yrs",
    score: "0.91",
    pct: 91,
    why: (
      <>
        <b>Owns the CI &amp; infra</b> a small team needs from day one.
      </>
    ),
  },
  {
    cls: "c2",
    initials: "AS",
    name: "Aman S.",
    role: "Full-stack · 4 yrs",
    score: "0.88",
    pct: 88,
    why: (
      <>
        <b>Strong API + React overlap</b>; lighter on data tooling.
      </>
    ),
  },
  {
    cls: "c3",
    initials: "PN",
    name: "Priya N.",
    role: "Backend Eng · 3 yrs",
    score: "0.85",
    pct: 85,
    why: (
      <>
        <b>Fast-growing</b>; matches stack, fewer years at scale.
      </>
    ),
  },
];

export function RankedStack() {
  return (
    <div className="stack">
      <div className="stack-frame" />
      <span className="stack-tag">RANKED · BY MATCH</span>
      <span className="stack-tag r">ROLE · BACKEND ENG</span>
      <div className="cards">
        {CANDIDATES.map((c) => (
          <article key={c.cls} className={`cand ${c.cls}`}>
            <div className="cand-top">
              <span className="avatar">{c.initials}</span>
              <div className="cand-id">
                <span className="nm">{c.name}</span>
                <span className="role">{c.role}</span>
              </div>
              <div className="score">
                <div className="v">{c.score}</div>
                <div className="l">match</div>
              </div>
            </div>
            <div className="bar">
              <span style={{ width: `${c.pct}%` }} />
            </div>
            <p className="why">{c.why}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
