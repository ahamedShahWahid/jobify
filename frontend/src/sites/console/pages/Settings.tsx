import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
import { useSession, useSessionStore } from "../session";

/** Operator account & appearance — the console's profile/settings, available to
 *  any signed-in admin or recruiter (not area-gated). Operators have no résumé /
 *  DSR data, so this is scoped to identity, theme, and session. */
export function Settings() {
  const { identity, client } = useSession();
  const { signOut } = useSessionStore();
  const isLive = client.mode === "live";

  return (
    <>
      <div className="headline">
        <h1>
          ACCOUNT <span className="ghost">SETTINGS</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            Your operator profile, appearance, and session — the same controls the rest of the
            platform gets, here for internal users too.
          </span>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 620, marginBottom: 18 }}>
        <div className="panel-head">
          <span className="k">Operator</span>
          <span className="chip">{identity.role}</span>
        </div>
        <div className="panel-body">
          <div className="field-row">
            <div className="field">
              <span className="k">Email</span>
              <div style={{ marginTop: 4 }}>{identity.email ?? "—"}</div>
            </div>
            <div className="field">
              <span className="k">User ID</span>
              <div className="num dim" style={{ marginTop: 4, wordBreak: "break-all" }}>
                {identity.id}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 620, marginBottom: 18 }}>
        <div className="panel-head">
          <span className="k">Appearance</span>
        </div>
        <div className="panel-body" style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <ThemeToggle />
          <span className="dim" style={{ fontSize: 13 }}>
            Light, dark, or match your system — saved to this browser.
          </span>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 620 }}>
        <div className="panel-head">
          <span className="k">Session</span>
          <span className={`chip ${isLive ? "ok" : ""}`}>
            {isLive ? "live api" : "demo data"}
          </span>
        </div>
        <div className="panel-body" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <span className="dim" style={{ fontSize: 13 }}>
            End this session and return to sign-in.
          </span>
          <button className="btn" onClick={signOut}>
            Log out
          </button>
        </div>
      </div>
    </>
  );
}
