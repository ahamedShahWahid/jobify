import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import type { MyInviteRead } from "../api/types";
import { Masthead } from "../components/Chrome";
import { EmptyState, ErrorNotice } from "../components/bits";
import { useSession } from "../session";

/**
 * The Invitation — the invitee side of employer team invites (R4). Real-backed:
 * GET /v1/me/invites, POST /v1/me/invites/{id}/{accept,decline}. Behind
 * RequireApplicant (authorization is by email match, not membership).
 *
 * Accepting flips the account to RECRUITER server-side, but this is the
 * applicant web property — so a successful accept lands on a terminal card that
 * points to the recruiter Console rather than trying to render a workspace the
 * app doesn't host. A 410 (expired between load and accept) is shown inline.
 */

/** Whole days until expiry, floored at 0. */
function daysLeft(iso: string): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));
}

type Outcome =
  | { kind: "accepted"; role: string }
  | { kind: "declined" }
  | { kind: "expired" }
  | { kind: "error"; message: string };

const CONSOLE_HINT = "Open the Jobify Console and sign in with this same account.";

export function Invites() {
  const { client, identity } = useSession();
  const [invites, setInvites] = useState<MyInviteRead[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Per-invite: in-flight action + terminal outcome (keyed by invite id).
  const [busyId, setBusyId] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      setInvites(await client.myInvites());
    } catch (e) {
      setLoadError(errorMessage(e));
      setInvites([]);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  async function accept(invite: MyInviteRead) {
    setBusyId(invite.id);
    try {
      const result = await client.acceptInvite(invite.id);
      setOutcomes((o) => ({ ...o, [invite.id]: { kind: "accepted", role: result.role } }));
    } catch (e) {
      if (e instanceof ApiError && e.status === 410) {
        setOutcomes((o) => ({ ...o, [invite.id]: { kind: "expired" } }));
      } else {
        setOutcomes((o) => ({ ...o, [invite.id]: { kind: "error", message: errorMessage(e) } }));
      }
    } finally {
      setBusyId(null);
    }
  }

  async function decline(invite: MyInviteRead) {
    setBusyId(invite.id);
    try {
      await client.declineInvite(invite.id);
      setOutcomes((o) => ({ ...o, [invite.id]: { kind: "declined" } }));
    } catch (e) {
      setOutcomes((o) => ({ ...o, [invite.id]: { kind: "error", message: errorMessage(e) } }));
    } finally {
      setBusyId(null);
    }
  }

  const pending = (invites ?? []).filter(
    (i) => !outcomes[i.id] || outcomes[i.id].kind === "error",
  );

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div style={{ padding: "26px 0 0" }}>
          <Link to="/explore" className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to feed
          </Link>
        </div>

        <header className="iv-hero rise mt">
          <span className="kicker">By invitation</span>
          <h1 className="iv-h1">You&apos;ve been asked to join a team</h1>
          <p className="deck iv-deck">
            {identity.email ? (
              <>
                Invitations addressed to <span className="mono">{identity.email}</span>. Accepting
                opens a recruiter workspace under your name.
              </>
            ) : (
              "Invitations addressed to your account. Accepting opens a recruiter workspace."
            )}
          </p>
        </header>

        <ErrorNotice error={loadError} />

        <section className="iv-stack rise d1">
          {invites === null && <div className="iv-loading">Reading the post…</div>}

          {invites !== null && pending.length === 0 && Object.keys(outcomes).length === 0 && (
            <EmptyState>
              No open invitations. When a hiring team adds your email, the card lands here — and a
              note arrives on{" "}
              <Link to="/inbox" className="accent">
                the Wire
              </Link>
              .
            </EmptyState>
          )}

          {/* Resolved cards (accepted / declined / expired) stay on screen as a
              receipt rather than vanishing. */}
          {(invites ?? []).map((invite) => {
            const outcome = outcomes[invite.id];
            const busy = busyId === invite.id;

            if (outcome && outcome.kind !== "error") {
              return (
                <article key={invite.id} className={`iv-card resolved ${outcome.kind}`}>
                  <div className="iv-seal" aria-hidden="true">
                    {outcome.kind === "accepted" ? "✓" : outcome.kind === "declined" ? "✕" : "⌛"}
                  </div>
                  <div className="iv-card-body">
                    <span className="iv-emp">{invite.employer_name}</span>
                    {outcome.kind === "accepted" && (
                      <>
                        <h3 className="iv-result">
                          You&apos;re in — as <span className="accent">{outcome.role}</span>.
                        </h3>
                        <p className="iv-note">
                          Your recruiter workspace is live. {CONSOLE_HINT} You can keep using this
                          applicant account too — the same sign-in reaches both.
                        </p>
                      </>
                    )}
                    {outcome.kind === "declined" && (
                      <>
                        <h3 className="iv-result">Invitation declined.</h3>
                        <p className="iv-note">
                          No workspace was created. The team can invite you again if it was a
                          mistake.
                        </p>
                      </>
                    )}
                    {outcome.kind === "expired" && (
                      <>
                        <h3 className="iv-result">This invitation expired.</h3>
                        <p className="iv-note">
                          Ask {invite.employer_name} to send a fresh one — invites are time-limited
                          for security.
                        </p>
                      </>
                    )}
                  </div>
                </article>
              );
            }

            const left = daysLeft(invite.expires_at);
            const urgent = left <= 2;
            return (
              <article key={invite.id} className="iv-card">
                <div className="iv-card-top">
                  <span className="iv-ribbon">Invitation</span>
                  <span className={`iv-expiry num${urgent ? " urgent" : ""}`}>
                    {left === 0 ? "expires today" : `${left} day${left === 1 ? "" : "s"} left`}
                  </span>
                </div>
                <p className="iv-lead serif italic">You are invited to join</p>
                <h2 className="iv-emp-name serif">{invite.employer_name}</h2>
                <p className="iv-role-line">
                  as a <span className="iv-role">{invite.role}</span> on their hiring team
                </p>
                <div className="iv-rule" />
                <p className="iv-fine">
                  Accept and your account gains a recruiter workspace — post roles, review
                  applicants, and manage the team. You can step back anytime.
                </p>
                {outcome?.kind === "error" && <ErrorNotice error={outcome.message} />}
                <div className="iv-actions">
                  <button
                    className="btn ghost"
                    disabled={busy}
                    onClick={() => void decline(invite)}
                  >
                    Decline
                  </button>
                  <button
                    className="btn primary"
                    disabled={busy}
                    onClick={() => void accept(invite)}
                  >
                    {busy ? "Joining…" : "Accept invitation"}
                  </button>
                </div>
              </article>
            );
          })}
        </section>

        <div className="cb-foot-rule" />
      </div>
    </>
  );
}
