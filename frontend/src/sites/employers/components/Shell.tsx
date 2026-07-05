import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useSession, useSessionStore } from "../session";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
import { IstClock } from "./bits";

const NAV = [
  { to: "/employers/dashboard", idx: "00", label: "Dashboard", end: true },
  { to: "/employers/jobs", idx: "01", label: "Jobs" },
  { to: "/employers/team", idx: "02", label: "Team & invites" },
];

/** Nav shell for the authenticated recruiter zone (mounted under /employers/*
 *  once signed in). Adapted from console's Shell — single nav section since
 *  this surface only ever serves recruiters, no area-switching needed. The
 *  "dash" class (alongside "shell") scopes dashboard.css above site.css's
 *  same-named classes — see styles/dashboard.css's header comment. */
export function Shell() {
  const { identity, client } = useSession();
  const { signOut } = useSessionStore();
  const { pathname } = useLocation();
  const crumb = pathname.split("/").filter(Boolean).join(" / ");

  return (
    <div className="dash shell">
      <nav className="rail">
        <div className="rail-brand">
          <div className="rail-lockup">
            <img src="/jobify-mark.svg" alt="Jobify" className="rail-mark" />
            <div className="wordmark">
              JOBIFY<em>//</em>EMPLOYERS
            </div>
          </div>
          <div className="k" style={{ marginTop: 4 }}>
            employer workspace
          </div>
          <div style={{ marginTop: 8 }}>
            <ThemeToggle />
          </div>
        </div>

        <div className="rail-section">
          <span className="k">Recruiting</span>
          {NAV.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end ?? false}
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
              to="/employers/settings"
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
            employers / <b>{crumb || "home"}</b>
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
