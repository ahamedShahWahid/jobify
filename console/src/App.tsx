import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { Shell } from "./components/Shell";
import { AuditExplorer } from "./pages/admin/AuditExplorer";
import { UserActions } from "./pages/admin/UserActions";
import { Applicants } from "./pages/recruiter/Applicants";
import { Dashboard } from "./pages/recruiter/Dashboard";
import { Jobs } from "./pages/recruiter/Jobs";
import { Team } from "./pages/recruiter/Team";
import { SignIn } from "./pages/SignIn";
import type { Area } from "./session";
import { areasForRole, landingFor, SessionProvider, useSessionStore } from "./session";

function RequireSession({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/signin" replace />;
  return <>{children}</>;
}

/**
 * Gate a route on the operator's area. A recruiter reaching /admin/* (or an admin
 * reaching /recruiter/*) is redirected to their own landing page rather than
 * shown a page whose every API call 403s. Role→area mapping lives in session.ts.
 */
function RequireArea({ area, children }: { area: Area; children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/signin" replace />;
  if (!areasForRole(session.identity.role).includes(area)) {
    return <Navigate to={landingFor(session.identity.role)} replace />;
  }
  return <>{children}</>;
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
            This console is for admins and recruiters. Your account
            {session ? ` (role: ${session.identity.role})` : ""} can't reach either area.
          </span>
        </div>
      </div>
    </div>
  );
}

export function App() {
  return (
    <SessionProvider>
      <div className="atmosphere" />
      {/* HashRouter: the console deploys as a static bundle with no server-side
          rewrites, and tokens stay out of real URL paths. */}
      <HashRouter>
        <Routes>
          <Route path="/signin" element={<SignIn />} />
          <Route
            element={
              <RequireSession>
                <Shell />
              </RequireSession>
            }
          >
            <Route
              path="/admin/audit"
              element={
                <RequireArea area="admin">
                  <AuditExplorer />
                </RequireArea>
              }
            />
            <Route
              path="/admin/users"
              element={
                <RequireArea area="admin">
                  <UserActions />
                </RequireArea>
              }
            />
            <Route
              path="/recruiter"
              element={
                <RequireArea area="recruiter">
                  <Dashboard />
                </RequireArea>
              }
            />
            <Route
              path="/recruiter/jobs"
              element={
                <RequireArea area="recruiter">
                  <Jobs />
                </RequireArea>
              }
            />
            <Route
              path="/recruiter/jobs/:jobId/applicants"
              element={
                <RequireArea area="recruiter">
                  <Applicants />
                </RequireArea>
              }
            />
            <Route
              path="/recruiter/team"
              element={
                <RequireArea area="recruiter">
                  <Team />
                </RequireArea>
              }
            />
            <Route path="/no-access" element={<NoAccess />} />
          </Route>
          <Route path="*" element={<Navigate to="/signin" replace />} />
        </Routes>
      </HashRouter>
    </SessionProvider>
  );
}
