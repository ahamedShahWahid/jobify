import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useSession, useSessionStore } from "../session";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
import { IstClock } from "./bits";
import { CONSOLE_BASE } from "../base";

const NAV = [
  { to: `${CONSOLE_BASE}/admin/analytics`, idx: "00", label: "Analytics" },
  { to: `${CONSOLE_BASE}/admin/audit`, idx: "01", label: "Audit explorer" },
  { to: `${CONSOLE_BASE}/admin/users`, idx: "02", label: "User actions" },
  { to: `${CONSOLE_BASE}/admin/verification`, idx: "03", label: "Verification" },
];

export function Shell() {
  const { identity, client } = useSession();
  const { signOut } = useSessionStore();
  const { pathname } = useLocation();
  const crumb = pathname.split("/").filter(Boolean).join(" / ");

  return (
    <div className="shell">
      <nav className="rail">
        <div className="rail-brand">
          <div className="rail-lockup">
            {/* J-person mark only — the wordmark's letter counters would read as
                light fills on this dark rail; the solid mark stays crisp. */}
            <img src="/jobify-mark.svg" alt="Jobify" className="rail-mark" />
            <div className="wordmark">
              JOBIFY<em>//</em>CONSOLE
            </div>
          </div>
          <div className="k" style={{ marginTop: 4 }}>
            internal operations
          </div>
          <div style={{ marginTop: 8 }}>
            <ThemeToggle />
          </div>
        </div>

        <div className="rail-section">
          <span className="k">Moderation</span>
          {NAV.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => `rail-link${isActive ? " active" : ""}`}
            >
              <span className="idx num">{link.idx}</span>
              {link.label}
            </NavLink>
          ))}
        </div>

        <div className="rail-foot">
          <div className="row">
            <span className={`led ${client.mode === "live" ? "live" : "amber"}`} />
            <span className="k">{client.mode === "live" ? "live api" : "demo data"}</span>
          </div>
          <div className="dim" style={{ fontSize: 11, wordBreak: "break-all" }}>
            {identity.email ?? identity.id}
            <span className="chip" style={{ marginLeft: 8 }}>
              {identity.role}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <NavLink
              to={`${CONSOLE_BASE}/settings`}
              className={({ isActive }) => `btn sm ghost${isActive ? " active" : ""}`}
              style={{ flex: 1, justifyContent: "center" }}
            >
              Settings
            </NavLink>
            <button className="btn sm" onClick={signOut} style={{ flex: 1 }}>
              Log out
            </button>
          </div>
        </div>
      </nav>

      <div className="main">
        <header className="masthead">
          <span className="crumbs">
            console / <b>{crumb || "home"}</b>
          </span>
          <IstClock />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
