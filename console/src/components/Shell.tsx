import { NavLink, Outlet, useLocation } from "react-router-dom";
import type { Area } from "../session";
import { areasForRole, useSession, useSessionStore } from "../session";
import { UtcClock } from "./bits";

const NAV: Array<{
  area: Area;
  label: string;
  links: Array<{ to: string; idx: string; label: string; end?: boolean }>;
}> = [
  {
    area: "admin",
    label: "Moderation",
    links: [
      { to: "/admin/analytics", idx: "00", label: "Analytics" },
      { to: "/admin/audit", idx: "01", label: "Audit explorer" },
      { to: "/admin/users", idx: "02", label: "User actions" },
      { to: "/admin/verification", idx: "03", label: "Verification" },
    ],
  },
  {
    area: "recruiter",
    label: "Recruiting",
    links: [
      { to: "/recruiter", idx: "04", label: "Dashboard", end: true },
      { to: "/recruiter/jobs", idx: "05", label: "Jobs" },
      { to: "/recruiter/team", idx: "06", label: "Team & invites" },
    ],
  },
];

export function Shell() {
  const { identity, client } = useSession();
  const { disconnect } = useSessionStore();
  const { pathname } = useLocation();
  const area = pathname.startsWith("/admin") ? "admin" : "recruiter";
  const crumb = pathname.split("/").filter(Boolean).join(" / ");

  // Only surface nav for areas this role can actually reach — otherwise every
  // out-of-area link is a guaranteed 403 on click.
  const allowed = areasForRole(identity.role);
  const sections = NAV.filter((section) => allowed.includes(section.area));

  return (
    <div className="shell" data-area={area}>
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
        </div>

        {sections.map((section) => (
          <div className="rail-section" key={section.area} data-area={section.area}>
            <span className="k">{section.label}</span>
            {section.links.map((link) => (
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
        ))}

        <div className="rail-foot">
          <div className="row">
            <span className={`led ${client.mode === "live" ? "live" : "amber"}`} />
            <span className="k">{client.mode === "live" ? "live api" : "demo data"}</span>
          </div>
          <div className="dim" style={{ fontSize: 11, wordBreak: "break-all" }}>
            {identity.email ?? identity.id}
            <span className="chip acc" style={{ marginLeft: 8 }}>
              {identity.role}
            </span>
          </div>
          <button className="btn sm" onClick={disconnect}>
            Disconnect
          </button>
        </div>
      </nav>

      <div className="main">
        <header className="masthead">
          <span className="crumbs">
            console / <b>{crumb || "home"}</b>
          </span>
          <UtcClock />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
