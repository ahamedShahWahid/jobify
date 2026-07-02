import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import type { ConsentRead, PreferencesRead } from "../api/types";
import { istDate } from "../../../shared/format";
import { Masthead } from "../components/Chrome";
import { ctcBand, ErrorNotice } from "../components/bits";
import { useSession, useSessionStore } from "../session";

/**
 * Profile & Privacy Center — applicant self-service for the read-only résumé
 * profile, consent/channel preferences, DPDP data export, and account deletion.
 * Real-backed: every interaction mirrors a /v1/me endpoint. Behind RequireApplicant.
 */

interface ScopeMeta {
  label: string;
  desc: string;
}

const SCOPE_META: Record<string, ScopeMeta> = {
  email_transactional: {
    label: "Transactional email",
    desc: "Application receipts, security notices, and account changes. Carries things you need to see.",
  },
  email_marketing: {
    label: "Product & jobs email",
    desc: "Occasional digests of new roles and product news. Off by default.",
  },
  in_app_notifications: {
    label: "In-app notifications",
    desc: "Updates that appear in your feed and notification inbox while you're here.",
  },
  whatsapp_notifications: {
    label: "WhatsApp",
    desc: "Match and application alerts over WhatsApp.",
  },
  sms_notifications: {
    label: "SMS",
    desc: "Text-message alerts to your phone.",
  },
  profile_visibility_recruiters: {
    label: "Recruiter profile visibility",
    desc: "Let verified recruiters discover your profile before you apply.",
  },
  third_party_sharing_recruiters: {
    label: "Third-party recruiter sharing",
    desc: "Share your profile with partner recruiters outside Jobify.",
  },
};

/** Scopes grouped by what acts on them today vs what's stored-but-dormant. */
const LIVE_GROUPS: { title: string; scopes: string[] }[] = [
  { title: "Email", scopes: ["email_transactional", "email_marketing"] },
  { title: "In-app", scopes: ["in_app_notifications"] },
];
const RESERVED_SCOPES = [
  "whatsapp_notifications",
  "sms_notifications",
  "profile_visibility_recruiters",
  "third_party_sharing_recruiters",
];

function fmtWhen(iso: string): string {
  return istDate(iso);
}

function num(s: string | null): number | null {
  if (s === null) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Accessible, keyboard-operable consent toggle (a real checkbox styled as a switch). */
function Toggle({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange?: (next: boolean) => void;
  label: string;
}) {
  return (
    <label className={`switch${disabled ? " is-disabled" : ""}`}>
      <input
        type="checkbox"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
      />
      <span className="switch-track" aria-hidden="true">
        <span className="switch-thumb" />
      </span>
    </label>
  );
}

export function Profile() {
  const { client, identity } = useSession();
  const { signOut } = useSessionStore();
  const navigate = useNavigate();

  const applicant = identity.applicant;
  const name = applicant?.full_name ?? identity.email?.split("@")[0] ?? "there";

  // ---- preferences (locations/expected_ctc — moved off ApplicantRead) -----
  const [preferences, setPreferences] = useState<PreferencesRead | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .getPreferences()
      .then((p) => {
        if (!cancelled) setPreferences(p);
      })
      .catch(() => {
        // Read-only display field — a failed fetch just leaves it as "—"
        // rather than surfacing another error banner on this page.
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  // ---- consents -----------------------------------------------------------
  const [consents, setConsents] = useState<ConsentRead[] | null>(null);
  const [consentError, setConsentError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [confirmTxnOff, setConfirmTxnOff] = useState(false);

  const byScope = useMemo(() => {
    const m = new Map<string, ConsentRead>();
    (consents ?? []).forEach((c) => m.set(c.scope, c));
    return m;
  }, [consents]);

  const loadConsents = useCallback(async () => {
    setConsentError(null);
    try {
      setConsents(await client.getConsents());
    } catch (e) {
      setConsentError(errorMessage(e));
    }
  }, [client]);

  useEffect(() => {
    void loadConsents();
  }, [loadConsents]);

  const applyConsent = useCallback(
    async (scope: string, next: boolean) => {
      const prev = consents;
      setPending(scope);
      setConsentError(null);
      // optimistic
      setConsents((cur) =>
        (cur ?? []).map((c) =>
          c.scope === scope ? { ...c, granted: next, updated_at: new Date().toISOString() } : c,
        ),
      );
      try {
        const row = await client.setConsent(scope, next);
        setConsents((cur) => (cur ?? []).map((c) => (c.scope === scope ? row : c)));
      } catch (e) {
        setConsents(prev); // rollback
        setConsentError(errorMessage(e));
      } finally {
        setPending(null);
      }
    },
    [client, consents],
  );

  function onToggle(scope: string, next: boolean) {
    // Turning OFF transactional email loses application/security notices —
    // gate it behind an explicit confirmation.
    if (scope === "email_transactional" && next === false) {
      setConfirmTxnOff(true);
      return;
    }
    void applyConsent(scope, next);
  }

  // ---- export -------------------------------------------------------------
  const [exporting, setExporting] = useState(false);
  const [exportData, setExportData] = useState<unknown>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const exportJson = useMemo(
    () => (exportData === null ? "" : JSON.stringify(exportData, null, 2)),
    [exportData],
  );
  const sectionCounts = useMemo<[string, number][]>(() => {
    if (exportData === null || typeof exportData !== "object") return [];
    const out: [string, number][] = [];
    for (const [k, v] of Object.entries(exportData as Record<string, unknown>)) {
      if (Array.isArray(v) && v.length > 0) out.push([k, v.length]);
    }
    return out;
  }, [exportData]);

  async function runExport() {
    setExporting(true);
    setExportError(null);
    setCopied(false);
    try {
      setExportData(await client.dsrExport());
    } catch (e) {
      setExportError(errorMessage(e));
    } finally {
      setExporting(false);
    }
  }

  async function copyExport() {
    try {
      await navigator.clipboard.writeText(exportJson);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setExportError("Couldn't copy to clipboard — use Download instead.");
    }
  }

  function downloadExport() {
    const blob = new Blob([exportJson], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "jobify-data-export.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // ---- delete -------------------------------------------------------------
  const [danger, setDanger] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteReport, setDeleteReport] = useState<{
    section_counts?: Record<string, number>;
    warnings?: unknown[];
  } | null>(null);

  const canDelete = confirmText === "DELETE_MY_ACCOUNT";

  async function runDelete() {
    if (!canDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const report = (await client.dsrDelete()) as {
        section_counts?: Record<string, number>;
        warnings?: unknown[];
      };
      setDeleteReport(report ?? {});
      // Brief terminal state, then clear the session and return to the gate.
      window.setTimeout(() => {
        signOut();
        navigate("/", { replace: true });
      }, 2600);
    } catch (e) {
      setDeleteError(errorMessage(e));
      setDeleting(false);
    }
  }

  // ---- render -------------------------------------------------------------
  const locations = preferences?.locations.join(" · ") || "—";
  const years = num(applicant?.years_experience ?? null);
  const notice = applicant?.notice_period_days ?? null;
  const curCtc = num(applicant?.current_ctc ?? null);
  const expCtc = num(preferences?.expected_ctc ?? null);
  const ctcLabel =
    curCtc === null && expCtc === null
      ? "Undisclosed"
      : `${ctcBand(curCtc, curCtc).split(" – ")[0]} → ${ctcBand(expCtc, expCtc).split(" – ")[0]}`;

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div style={{ padding: "26px 0 0" }}>
          <Link to="/explore" className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to feed
          </Link>
        </div>

        {/* ---- header ---- */}
        <header className="pf-hero rise mt">
          <div>
            <span className="kicker">Your account &amp; privacy</span>
            <h1 className="pf-h1">Settings &amp; your data</h1>
            <p className="deck pf-deck">
              {name}
              {identity.email ? ` · ${identity.email}` : ""} ·{" "}
              <span className="mono pf-role">{identity.role}</span>
            </p>
          </div>
          <button className="btn ghost sm" onClick={signOut}>
            Sign out
          </button>
        </header>

        {/* ---- profile summary ---- */}
        <section className="pf-sec rise d1">
          <div className="pf-sec-head">
            <span className="no">§ Profile</span>
            <h2>From your résumé</h2>
          </div>
          <div className="pf-card">
            <div className="factline">
              <span className="k">Name</span>
              <span className="v">{applicant?.full_name ?? "—"}</span>
            </div>
            <div className="factline">
              <span className="k">Locations</span>
              <span className="v">{locations}</span>
            </div>
            <div className="factline">
              <span className="k">Experience</span>
              <span className="v num">{years === null ? "—" : `${years} yrs`}</span>
            </div>
            <div className="factline">
              <span className="k">Notice period</span>
              <span className="v num">{notice === null ? "—" : `${notice} days`}</span>
            </div>
            <div className="factline">
              <span className="k">Current → expected</span>
              <span className="v num">{ctcLabel}</span>
            </div>
          </div>
          <p className="pf-note dim">
            Name and experience come from your latest parsed résumé; location and expected CTC are
            what you told us when asked. There's no edit form here by design.
          </p>
        </section>

        {/* ---- consent & channels ---- */}
        <section className="pf-sec rise d1">
          <div className="pf-sec-head">
            <span className="no">§ Consent</span>
            <h2>Channels &amp; consent</h2>
          </div>

          <ErrorNotice error={consentError} />

          {consents === null && !consentError && (
            <div className="spinner-row">Loading your preferences…</div>
          )}

          {consents !== null && (
            <>
              {LIVE_GROUPS.map((group) => (
                <div className="pf-group" key={group.title}>
                  <div className="pf-group-title kicker ink">{group.title}</div>
                  {group.scopes.map((scope) => {
                    const row = byScope.get(scope);
                    const meta = SCOPE_META[scope];
                    if (!row || !meta) return null;
                    return (
                      <div className="pf-toggle-row" key={scope}>
                        <div className="pf-toggle-text">
                          <div className="pf-toggle-label">{meta.label}</div>
                          <p className="pf-toggle-desc dim">{meta.desc}</p>
                          <div className="pf-toggle-when mono">
                            Updated {fmtWhen(row.updated_at)}
                          </div>
                        </div>
                        <Toggle
                          checked={row.granted}
                          disabled={pending === scope}
                          label={meta.label}
                          onChange={(next) => onToggle(scope, next)}
                        />
                      </div>
                    );
                  })}
                </div>
              ))}

              {/* reserved scopes — stored but no channel acts on them yet */}
              <div className="pf-group pf-reserved">
                <div className="pf-group-title kicker ink">
                  Not yet available
                  <span className="tag pf-soon">reserved — coming soon</span>
                </div>
                <p className="pf-reserved-note dim">
                  We store these preferences, but no channel acts on them yet. They're disabled
                  until the feature ships.
                </p>
                {RESERVED_SCOPES.map((scope) => {
                  const row = byScope.get(scope);
                  const meta = SCOPE_META[scope];
                  if (!row || !meta) return null;
                  return (
                    <div className="pf-toggle-row is-reserved" key={scope}>
                      <div className="pf-toggle-text">
                        <div className="pf-toggle-label">{meta.label}</div>
                        <p className="pf-toggle-desc dim">{meta.desc}</p>
                      </div>
                      <Toggle checked={row.granted} disabled label={meta.label} />
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </section>

        {/* ---- export ---- */}
        <section className="pf-sec rise d2">
          <div className="pf-sec-head">
            <span className="no">§ Access</span>
            <h2>Export your data</h2>
          </div>
          <p className="pf-prose">
            Your DPDP right of access — download everything we hold about you as one JSON file:
            profile, applications, matches, consent history. Refresh tokens and session secrets are
            never included.
          </p>

          <ErrorNotice error={exportError} />

          <div className="pf-actions">
            <button className="btn primary" disabled={exporting} onClick={runExport}>
              {exporting ? "Assembling…" : exportData ? "Re-fetch my data" : "Download my data"}
            </button>
            {exportData !== null && (
              <>
                <button className="btn" onClick={downloadExport}>
                  Save .json
                </button>
                <button className="btn ghost" onClick={copyExport}>
                  {copied ? "Copied ✓" : "Copy JSON"}
                </button>
              </>
            )}
          </div>

          {sectionCounts.length > 0 && (
            <div className="pf-counts">
              {sectionCounts.map(([k, v]) => (
                <span className="pf-count-chip" key={k}>
                  <span className="num">{v}</span> {k.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}

          {exportData !== null && (
            <pre className="pf-export-preview mono" aria-label="Data export preview">
              {exportJson.length > 4000 ? `${exportJson.slice(0, 4000)}\n… (truncated)` : exportJson}
            </pre>
          )}
        </section>

        {/* ---- danger zone: delete ---- */}
        <section className="pf-danger rise d2">
          <div className="pf-sec-head">
            <span className="no danger">§ Erasure</span>
            <h2>Delete your account</h2>
          </div>
          <p className="pf-prose">
            Your DPDP right to erasure. We tombstone your account and scrub every identifying field,
            then hard-delete the tables that exist only to hold personal data — atomically, all or
            nothing. Anonymized analytics remain; you can sign up fresh with the same email
            afterwards. This can't be undone.
          </p>

          <ErrorNotice error={deleteError} />

          {deleteReport ? (
            <div className="pf-deleted">
              <div className="pf-deleted-mark">✓</div>
              <div>
                <h3>Your account has been deleted.</h3>
                <p className="dim">
                  {deleteReport.section_counts
                    ? `${Object.values(deleteReport.section_counts).reduce(
                        (a, b) => a + b,
                        0,
                      )} records erased across ${
                        Object.keys(deleteReport.section_counts).length
                      } sections.`
                    : "Your data has been erased."}
                  {deleteReport.warnings && deleteReport.warnings.length > 0
                    ? ` ${deleteReport.warnings.length} warning(s) noted.`
                    : ""}{" "}
                  Signing you out…
                </p>
              </div>
            </div>
          ) : !danger ? (
            <button className="btn danger" onClick={() => setDanger(true)}>
              Delete my account
            </button>
          ) : (
            <div className="pf-confirm">
              <div className="field">
                <label htmlFor="pf-confirm-input">
                  Type DELETE_MY_ACCOUNT to confirm
                </label>
                <input
                  id="pf-confirm-input"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="DELETE_MY_ACCOUNT"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  disabled={deleting}
                />
              </div>
              <div className="pf-actions">
                <button
                  className="btn danger"
                  disabled={!canDelete || deleting}
                  onClick={runDelete}
                >
                  {deleting ? "Deleting…" : "Permanently delete"}
                </button>
                <button
                  className="btn ghost"
                  disabled={deleting}
                  onClick={() => {
                    setDanger(false);
                    setConfirmText("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>

        <div className="why-foot">
          <Link to="/explore" className="link-arrow" style={{ fontSize: 13 }}>
            ← Back to feed
          </Link>
          <Link to="/trust" className="link-arrow" style={{ fontSize: 13 }}>
            How we handle your data →
          </Link>
        </div>

        <div style={{ height: 60 }} />
      </div>

      {/* ---- transactional-email confirm dialog ---- */}
      {confirmTxnOff && (
        <div className="pf-modal-backdrop" role="presentation" onClick={() => setConfirmTxnOff(false)}>
          <div
            className="pf-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pf-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="kicker ink">Confirm</span>
            <h3 id="pf-modal-title">Turn off transactional email?</h3>
            <p className="pf-prose">
              Transactional email carries application receipts and security notices — things you
              generally need to see. You can still turn it back on any time.
            </p>
            <div className="pf-actions">
              <button
                className="btn danger"
                onClick={() => {
                  setConfirmTxnOff(false);
                  void applyConsent("email_transactional", false);
                }}
              >
                Turn it off
              </button>
              <button className="btn ghost" onClick={() => setConfirmTxnOff(false)}>
                Keep it on
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
