/** The signature hero object: a ranked hiring ledger. Rank is encoded as
 *  typographic depth — #1 is the fully developed Match Statement (its fit
 *  REASON set in serif-italic display type, the score demoted to a mono
 *  receipt stamp, the caveat in persimmon — the one thing persimmon means).
 *  Ranks 2–4 compress into single mono ledger lines. Purely illustrative. */

interface Row {
  rank: string;
  score: string;
  name: string;
  meta: string;
  reason: string;
}

const REST: Row[] = [
  { rank: "02", score: "0.91", name: "Dev K.", meta: "Platform · 6y", reason: "Owns the CI and infra a small team needs from day one." },
  { rank: "03", score: "0.88", name: "Aman S.", meta: "Full-stack · 4y", reason: "Strong API + React overlap; lighter on data tooling." },
  { rank: "04", score: "0.85", name: "Priya N.", meta: "Backend · 3y", reason: "Fast-growing; matches the stack with fewer years at scale." },
];

export function Ledger() {
  return (
    <div className="ledger" aria-hidden="true">
      <div className="ledger-head">
        <span className="lh-role">RANKED · BACKEND ENGINEER</span>
        <span className="lh-count">27 APPLICANTS</span>
      </div>

      <article className="lrow lead">
        <div className="lr-top">
          <span className="lr-rank">01</span>
          <span className="lr-who">
            <b>Riya M.</b> · Backend · 5 yrs
          </span>
          <span className="lr-score">
            0.94 <i>match</i>
          </span>
        </div>
        <p className="lr-reason">
          &ldquo;Shipped a zero-downtime Postgres shard migration — the exact scale this
          role is built around.&rdquo;
        </p>
        <p className="lr-caveat">
          <span className="ck">caveat</span>
          Kafka exposure is recent; the role leans on it heavily.
        </p>
      </article>

      <div className="lrows">
        {REST.map((r) => (
          <div className="lrow compact" key={r.rank}>
            <span className="lr-rank">{r.rank}</span>
            <span className="lr-score">{r.score}</span>
            <span className="lr-who">
              <b>{r.name}</b> · {r.meta}
            </span>
            <span className="lr-reason">{r.reason}</span>
          </div>
        ))}
      </div>

      <div className="ledger-foot">
        <span>+ 23 more, ranked</span>
        <span className="lf-note">You read signal, not a stack of PDFs.</span>
      </div>
    </div>
  );
}
