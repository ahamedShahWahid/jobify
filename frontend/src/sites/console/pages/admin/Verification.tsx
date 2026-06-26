import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { errorMessage } from "../../api/client";
import type { ConsoleClient } from "../../api/client";
import type {
  EmployerVerificationRow,
  EmployerVerificationStatus,
} from "../../api/types";
import { Drawer, EmptyState, ErrorNotice, Field, ShortId, Stamp } from "../../components/bits";
import { usePagedFetch } from "../../paging/usePagedFetch";
import { useSession } from "../../session";

const STATUSES: EmployerVerificationStatus[] = ["pending", "verified", "rejected"];

const STATUS_LABEL: Record<EmployerVerificationStatus, string> = {
  pending: "Pending",
  verified: "Verified",
  rejected: "Rejected",
};

/** The chip variant that paints each status in the house palette. */
function statusChipClass(status: EmployerVerificationStatus): string {
  if (status === "verified") return "chip ok";
  if (status === "rejected") return "chip danger";
  return "chip acc";
}

const EMPTY_COPY: Record<EmployerVerificationStatus, string> = {
  pending: "Queue's clear — no employers waiting on a verdict.",
  verified: "No employers have been verified yet.",
  rejected: "Nothing rejected. Clean slate.",
};

// Bounded drain (mirrors Analytics' drainAuditLogs) purely to compute the per-
// status tile counts. The list endpoint has no count, so we page through each
// status once. A misbehaving cursor must not loop forever.
const MAX_PAGES = 20;

async function countStatus(
  client: ConsoleClient,
  status: EmployerVerificationStatus,
): Promise<number> {
  let total = 0;
  let cursor: string | undefined;
  for (let page = 0; page < MAX_PAGES; page++) {
    const res = await client.listEmployersForVerification(status, cursor);
    total += res.items.length;
    if (!res.next_cursor) break;
    cursor = res.next_cursor;
  }
  return total;
}

/** The verification checklist — display-only booleans derived per row. The
 * domain/email checks only appear when the (demo-only) fields are present; the
 * live API carries just GST + status, so those are always shown. */
function checklist(row: EmployerVerificationRow): Array<{ ok: boolean; label: string }> {
  const checks = [
    { ok: row.gst !== null && row.gst.trim().length > 0, label: "GST number present" },
    { ok: row.status !== "rejected", label: "Not previously rejected" },
  ];
  if (row.domain != null) {
    checks.push({ ok: true, label: "Company domain on file" });
    const emailDomain = row.contact_email?.split("@")[1]?.toLowerCase() ?? null;
    if (emailDomain != null) {
      checks.push({
        ok: emailDomain === row.domain.toLowerCase(),
        label: "Contact email matches the company domain",
      });
    }
  }
  return checks;
}

function DetailRow({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="spread">
      <span className="k">{k}</span>
      <span>{children}</span>
    </div>
  );
}

export function Verification() {
  const { client } = useSession();

  const [status, setStatus] = useState<EmployerVerificationStatus>("pending");
  const [counts, setCounts] = useState<Record<EmployerVerificationStatus, number> | null>(null);

  const [reviewing, setReviewing] = useState<EmployerVerificationRow | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [acting, setActing] = useState<"verify" | "reject" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetcher = useCallback(
    (cursor: string | undefined) => client.listEmployersForVerification(status, cursor),
    [client, status],
  );
  const { rows, nextCursor, busy, error, loadMore, reload } = usePagedFetch(fetcher, status);

  // Recompute the tile counts whenever the underlying data may have changed:
  // on mount, on client swap, and after each successful review (via `bump`).
  const [bump, setBump] = useState(0);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [pending, verified, rejected] = await Promise.all(
          STATUSES.map((s) => countStatus(client, s)),
        );
        if (!cancelled) setCounts({ pending, verified, rejected });
      } catch {
        // Tile counts are best-effort; the table itself surfaces real errors.
        if (!cancelled) setCounts(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, bump]);

  function openReview(row: EmployerVerificationRow) {
    setReviewing(row);
    setRejecting(false);
    setReason("");
    setActionError(null);
  }

  function closeReview() {
    setReviewing(null);
    setRejecting(false);
    setReason("");
    setActionError(null);
    setActing(null);
  }

  async function act(kind: "verify" | "reject") {
    if (!reviewing) return;
    setActing(kind);
    setActionError(null);
    try {
      if (kind === "verify") {
        await client.verifyEmployer(reviewing.id);
      } else {
        await client.rejectEmployer(reviewing.id, reason.trim());
      }
      closeReview();
      reload();
      setBump((n) => n + 1);
    } catch (e) {
      setActionError(errorMessage(e));
    } finally {
      setActing(null);
    }
  }

  const reasonValid = reason.trim().length >= 1 && reason.trim().length <= 255;
  const checks = reviewing ? checklist(reviewing) : [];

  return (
    <>
      <div className="headline rise">
        <h1>
          VERIFY <span className="ghost">EMPLOYERS</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            Gatekeeping the supply side — who gets the verified badge applicants trust.
          </span>
        </div>
      </div>

      <div className="tiles rise mb">
        {STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            className={`tile tile-button${status === s ? " on" : ""}`}
            onClick={() => setStatus(s)}
          >
            <span className="k">{STATUS_LABEL[s]}</span>
            <div className="value num">
              {counts ? counts[s] : "·"}
            </div>
          </button>
        ))}
      </div>

      <ErrorNotice error={error} />

      <div className="table-wrap rise">
        <table className="console">
          <thead>
            <tr>
              <th>Employer</th>
              <th>GST</th>
              <th>Submitted</th>
              <th className="r">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="expandable" onClick={() => openReview(row)}>
                <td style={{ maxWidth: 280 }}>
                  {row.name}
                  <div className="k" style={{ marginTop: 2 }}>
                    {row.contact_email ?? <ShortId id={row.id} />}
                  </div>
                </td>
                <td className="mono-id">{row.gst ?? <span className="dim">—</span>}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <Stamp iso={row.created_at} />
                </td>
                <td className="r">
                  <span className={statusChipClass(row.status)}>{row.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !busy && !error && <EmptyState>{EMPTY_COPY[status]}</EmptyState>}
      </div>

      <div className="row mt">
        {nextCursor && (
          <button className="btn" disabled={busy} onClick={loadMore}>
            {busy ? "Loading…" : "Load more"}
          </button>
        )}
      </div>

      {reviewing && (
        <Drawer
          title={`Review — ${reviewing.name}`}
          onClose={closeReview}
          foot={
            reviewing.status === "pending" ? (
              rejecting ? (
                <>
                  <button className="btn ghost" onClick={() => setRejecting(false)}>
                    Back
                  </button>
                  <button
                    className="btn danger"
                    disabled={!reasonValid || acting !== null}
                    onClick={() => void act("reject")}
                  >
                    {acting === "reject" ? "Rejecting…" : "Confirm rejection"}
                  </button>
                </>
              ) : (
                <>
                  <button
                    className="btn danger"
                    disabled={acting !== null}
                    onClick={() => setRejecting(true)}
                  >
                    Reject…
                  </button>
                  <button
                    className="btn primary"
                    disabled={acting !== null}
                    onClick={() => void act("verify")}
                  >
                    {acting === "verify" ? "Approving…" : "Approve verification"}
                  </button>
                </>
              )
            ) : (
              <button className="btn ghost" onClick={closeReview}>
                Close
              </button>
            )
          }
        >
          <ErrorNotice error={actionError} />

          <div className="panel" style={{ marginBottom: 18 }}>
            <div className="panel-head">
              <span className="k">application</span>
              <span className={statusChipClass(reviewing.status)}>{reviewing.status}</span>
            </div>
            <div className="panel-body stack">
              <DetailRow k="employer">
                <span className="num">{reviewing.name}</span>
              </DetailRow>
              {reviewing.domain != null && (
                <DetailRow k="domain">
                  <span className="num">{reviewing.domain}</span>
                </DetailRow>
              )}
              {reviewing.contact_email != null && (
                <DetailRow k="contact email">{reviewing.contact_email}</DetailRow>
              )}
              <DetailRow k="gst">
                {reviewing.gst ? (
                  <span className="mono-id num">{reviewing.gst}</span>
                ) : (
                  <span className="dim">— (not supplied)</span>
                )}
              </DetailRow>
              <DetailRow k="submitted">
                <Stamp iso={reviewing.created_at} />
              </DetailRow>
              <DetailRow k="id">
                <ShortId id={reviewing.id} />
              </DetailRow>
            </div>
          </div>

          <div className="panel" style={{ marginBottom: 18 }}>
            <div className="panel-head">
              <span className="k">verification checklist</span>
            </div>
            <div className="panel-body">
              <ul className="checklist">
                {checks.map((check) => (
                  <li key={check.label} className={check.ok ? "ok" : "miss"}>
                    <span className="mark">{check.ok ? "✓" : "✕"}</span>
                    {check.label}
                  </li>
                ))}
              </ul>
              <div className="k dim" style={{ marginTop: 12 }}>
                Heuristics only — the verdict is yours. Approving sets the verified badge applicants
                see on this employer's postings.
              </div>
            </div>
          </div>

          {reviewing.status !== "pending" && (
            <div className="panel">
              <div className="panel-head">
                <span className="k">already reviewed</span>
              </div>
              <div className="panel-body stack">
                <DetailRow k="reviewed">
                  {reviewing.reviewed_at ? (
                    <Stamp iso={reviewing.reviewed_at} />
                  ) : (
                    <span className="dim">—</span>
                  )}
                </DetailRow>
                {reviewing.reviewer != null && (
                  <DetailRow k="reviewer">{reviewing.reviewer}</DetailRow>
                )}
                {reviewing.status === "rejected" && (
                  <DetailRow k="reason">
                    {reviewing.reason ?? <span className="dim">—</span>}
                  </DetailRow>
                )}
              </div>
            </div>
          )}

          {rejecting && (
            <div className="panel">
              <div className="panel-head">
                <span className="k">rejection reason</span>
                {reasonValid ? (
                  <span className="chip ok">ready</span>
                ) : (
                  <span className="chip">1–255 chars</span>
                )}
              </div>
              <div className="panel-body">
                <Field
                  label="Reason"
                  hint="Required (1–255 chars). Shown to the employer and stored on the review."
                >
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    maxLength={255}
                    rows={3}
                    placeholder="e.g. Contact email domain does not match the stated company domain."
                  />
                </Field>
              </div>
            </div>
          )}
        </Drawer>
      )}
    </>
  );
}
