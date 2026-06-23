import { Navigate, Outlet, Route } from "react-router-dom";
import { useEffect } from "react";
import type { ReactNode } from "react";
import "./styles/console.css";
import { Shell } from "./components/Shell";
import { Analytics } from "./pages/admin/Analytics";
import { AuditExplorer } from "./pages/admin/AuditExplorer";
import { UserActions } from "./pages/admin/UserActions";
import { Verification } from "./pages/admin/Verification";
import { Applicants } from "./pages/recruiter/Applicants";
import { Dashboard } from "./pages/recruiter/Dashboard";
import { JobComposer } from "./pages/recruiter/JobComposer";
import { Jobs } from "./pages/recruiter/Jobs";
import { Team } from "./pages/recruiter/Team";
import { SignIn } from "./pages/SignIn";
import type { Area } from "./session";
import { areasForRole, landingFor, SessionProvider, useSessionStore } from "./session";

function RequireSession({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/console/signin" replace />;
  return <>{children}</>;
}

/**
 * Gate a route on the operator's area. A recruiter reaching /console/admin/* (or an admin
 * reaching /console/recruiter/*) is redirected to their own landing page rather than
 * shown a page whose every API call 403s. Role→area mapping lives in area.ts.
 */
function RequireArea({ area, children }: { area: Area; children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/console/signin" replace />;
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

/** Session + CSS-scope wrapper for the console surface (mounted at "/console/*"). */
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

/** Console (admin + recruiter ops) routes, prefixed at /console. Returned into the top <Routes>. */
export function ConsoleRoutes() {
  return (
    <Route element={<ConsoleLayout />}>
      <Route path="/console/signin" element={<SignIn />} />
      <Route
        element={
          <RequireSession>
            <Shell />
          </RequireSession>
        }
      >
        <Route
          path="/console/admin/analytics"
          element={
            <RequireArea area="admin">
              <Analytics />
            </RequireArea>
          }
        />
        <Route
          path="/console/admin/audit"
          element={
            <RequireArea area="admin">
              <AuditExplorer />
            </RequireArea>
          }
        />
        <Route
          path="/console/admin/users"
          element={
            <RequireArea area="admin">
              <UserActions />
            </RequireArea>
          }
        />
        <Route
          path="/console/admin/verification"
          element={
            <RequireArea area="admin">
              <Verification />
            </RequireArea>
          }
        />
        <Route
          path="/console/recruiter"
          element={
            <RequireArea area="recruiter">
              <Dashboard />
            </RequireArea>
          }
        />
        <Route
          path="/console/recruiter/jobs"
          element={
            <RequireArea area="recruiter">
              <Jobs />
            </RequireArea>
          }
        />
        <Route
          path="/console/recruiter/jobs/new"
          element={
            <RequireArea area="recruiter">
              <JobComposer />
            </RequireArea>
          }
        />
        <Route
          path="/console/recruiter/jobs/:jobId/edit"
          element={
            <RequireArea area="recruiter">
              <JobComposer />
            </RequireArea>
          }
        />
        <Route
          path="/console/recruiter/jobs/:jobId/applicants"
          element={
            <RequireArea area="recruiter">
              <Applicants />
            </RequireArea>
          }
        />
        <Route
          path="/console/recruiter/team"
          element={
            <RequireArea area="recruiter">
              <Team />
            </RequireArea>
          }
        />
        <Route path="/console/no-access" element={<NoAccess />} />
      </Route>
      <Route path="/console/*" element={<Navigate to="/console/signin" replace />} />
    </Route>
  );
}
