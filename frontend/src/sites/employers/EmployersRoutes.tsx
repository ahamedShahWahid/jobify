import { Navigate, Outlet, Route } from "react-router-dom";
import { useEffect } from "react";
import type { ReactNode } from "react";
import "./styles/site.css";
import "./styles/dashboard.css";
import { Landing } from "./pages/Landing";
import { Verify } from "./pages/Verify";
import { SignIn } from "./pages/SignIn";
import { Settings } from "./pages/Settings";
import { Shell } from "./components/Shell";
import { Dashboard } from "./pages/dashboard/Dashboard";
import { Jobs } from "./pages/dashboard/Jobs";
import { JobComposer } from "./pages/dashboard/JobComposer";
import { Applicants } from "./pages/dashboard/Applicants";
import { Team } from "./pages/dashboard/Team";
import { Onboarding } from "./pages/Onboarding";
import { landingFor } from "./landing";
import { SessionProvider, useSessionStore } from "./session";

/** CSS-scope + title wrapper for the employers marketing surface (mounted at "/employers"). */
function EmployersLayout() {
  useEffect(() => {
    document.title = "Jobify for employers — ranked applicants, not a résumé pile";
  }, []);
  return (
    <div className="surface-employers">
      <Outlet />
    </div>
  );
}

function RequireSession({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/employers/signin" replace />;
  return <>{children}</>;
}

/** Gates the recruiter-ops route group at once (unlike console, there's only
 *  one role to check here). A non-recruiter is redirected via landingFor: an
 *  applicant lands on /onboarding, anyone else (e.g. admin) on /no-access. */
function RequireRecruiter() {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/employers/signin" replace />;
  if (session.identity.role !== "recruiter") {
    return <Navigate to={landingFor(session.identity.role)} replace />;
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
            This workspace is for recruiters. Your account
            {session ? ` (role: ${session.identity.role})` : ""} can&apos;t reach the job desk.
          </span>
        </div>
      </div>
    </div>
  );
}

/** Session wrapper for the authenticated recruiter zone (mounted under /employers/*). */
function DashboardLayout() {
  useEffect(() => {
    document.title = "Jobify — employer workspace";
  }, []);
  return (
    <SessionProvider>
      <Outlet />
    </SessionProvider>
  );
}

/** Employers (recruiter marketing + authenticated workspace) routes. Returned into the top <Routes>. */
export function EmployersRoutes() {
  return (
    <Route element={<EmployersLayout />}>
      <Route path="/employers" element={<Landing />} />
      <Route path="/employers/verify" element={<Verify />} />

      <Route element={<DashboardLayout />}>
        <Route path="/employers/signin" element={<SignIn />} />
        <Route
          element={
            <RequireSession>
              <Shell />
            </RequireSession>
          }
        >
          {/* Account & settings — any signed-in recruiter, not role-gated further. */}
          <Route path="/employers/settings" element={<Settings />} />
          <Route path="/employers/no-access" element={<NoAccess />} />
          <Route path="/employers/onboarding" element={<Onboarding />} />
          <Route element={<RequireRecruiter />}>
            <Route path="/employers/dashboard" element={<Dashboard />} />
            <Route path="/employers/jobs" element={<Jobs />} />
            <Route path="/employers/jobs/new" element={<JobComposer />} />
            <Route path="/employers/jobs/:jobId/edit" element={<JobComposer />} />
            <Route path="/employers/jobs/:jobId/applicants" element={<Applicants />} />
            <Route path="/employers/team" element={<Team />} />
          </Route>
        </Route>
      </Route>

      <Route path="/employers/*" element={<Navigate to="/employers" replace />} />
    </Route>
  );
}
