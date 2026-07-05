import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
import { useSession, useSessionStore } from "../session";

/** Recruiter account & appearance — identity, theme, session. No résumé/DSR
 *  data here (that's the Flutter applicant app's responsibility), same
 *  rationale as console's admin-only Settings page. */
export function Settings() {
  const { identity } = useSession();
  const { signOut } = useSessionStore();

  return (
    <>
      <div className="headline">
        <h1>
          ACCOUNT <span className="ghost">SETTINGS</span>
        </h1>
        <div className="sub">
          <span className="flavor">Your recruiter profile, appearance, and session.</span>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 620, marginBottom: 18 }}>
        <div className="panel-head">
          <span className="k">Recruiter</span>
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
          <span className="chip ok">
            live api
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
