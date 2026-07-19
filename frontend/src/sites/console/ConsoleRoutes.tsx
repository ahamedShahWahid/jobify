import { Navigate, Outlet, Route } from "react-router-dom";
import { useEffect } from "react";
import type { ReactNode } from "react";
import "./styles/console.css";
import { Shell } from "./components/Shell";
import { Analytics } from "./pages/admin/Analytics";
import { AuditExplorer } from "./pages/admin/AuditExplorer";
import { MatchQA } from "./pages/admin/MatchQA";
import { UserActions } from "./pages/admin/UserActions";
import { Verification } from "./pages/admin/Verification";
import { Settings } from "./pages/Settings";
import { SignIn } from "./pages/SignIn";
import { CONSOLE_BASE } from "./base";
import { areasForRole, SessionProvider, useSessionStore } from "./session";

function RequireSession({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to={`${CONSOLE_BASE}/signin`} replace />;
  return <>{children}</>;
}

/** Gate the admin subtree on role. Console is jobify-internal now — a
 *  recruiter or applicant who signs in here sees /no-access, never a
 *  redirect to /employers (recruiters have their own workspace already). */
function RequireAdmin() {
  const { session } = useSessionStore();
  if (!session) return <Navigate to={`${CONSOLE_BASE}/signin`} replace />;
  if (areasForRole(session.identity.role).length === 0) {
    return <Navigate to={`${CONSOLE_BASE}/no-access`} replace />;
  }
  return <Outlet />;
}

function NoAccess() {
  const { session } = useSessionStore();
  return (
    <div className="content">
      <div className="headline">
        <h1>
          NO <span className="ghost">ACCESS</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            This console is for jobify staff only. Your account
            {session ? ` (role: ${session.identity.role})` : ""} can&apos;t reach it.
          </span>
        </div>
      </div>
    </div>
  );
}

/** Session + CSS-scope wrapper for the console surface. */
function ConsoleLayout() {
  useEffect(() => {
    document.title = "JOBIFY // CONSOLE";
  }, []);
  return (
    <SessionProvider>
      <div className="atmosphere" />
      <div className="surface-console">
        <Outlet />
      </div>
    </SessionProvider>
  );
}

/** Console (jobify-internal admin ops) routes. Returned into the top <Routes>.
 *  Every path is built from CONSOLE_BASE so the whole subtree can remount at a
 *  different base (empty string, once served from console.jobify.com) with
 *  no other code changes — see base.ts. */
export function ConsoleRoutes() {
  return (
    <Route element={<ConsoleLayout />}>
      <Route path={`${CONSOLE_BASE}/signin`} element={<SignIn />} />
      <Route
        element={
          <RequireSession>
            <Shell />
          </RequireSession>
        }
      >
        {/* Account & settings — any signed-in admin, not further gated. */}
        <Route path={`${CONSOLE_BASE}/settings`} element={<Settings />} />
        <Route path={`${CONSOLE_BASE}/no-access`} element={<NoAccess />} />
        <Route element={<RequireAdmin />}>
          <Route path={`${CONSOLE_BASE}/admin/analytics`} element={<Analytics />} />
          <Route path={`${CONSOLE_BASE}/admin/audit`} element={<AuditExplorer />} />
          <Route path={`${CONSOLE_BASE}/admin/users`} element={<UserActions />} />
          <Route path={`${CONSOLE_BASE}/admin/verification`} element={<Verification />} />
          <Route path={`${CONSOLE_BASE}/admin/match-qa`} element={<MatchQA />} />
        </Route>
      </Route>
      <Route path={`${CONSOLE_BASE}/*`} element={<Navigate to={`${CONSOLE_BASE}/signin`} replace />} />
    </Route>
  );
}
