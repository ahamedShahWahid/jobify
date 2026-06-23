import { Outlet, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import "./styles/site.css";
import { Landing } from "./pages/Landing";
import { Trust } from "./pages/Trust";
import { Welcome } from "./pages/Welcome";
import { Feed } from "./pages/explore/Feed";
import { Gate } from "./pages/explore/Gate";
import { JobDetail } from "./pages/explore/JobDetail";
import { WhyMatch } from "./pages/explore/WhyMatch";
import { Profile } from "./pages/Profile";
import { Applications } from "./pages/Applications";
import { Inbox } from "./pages/Inbox";
import { Invites } from "./pages/Invites";
import { SessionProvider, useSessionStore } from "./session";

/** Explore routes need an applicant session — otherwise show the sign-in gate. */
function RequireApplicant({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  return session ? <>{children}</> : <Gate />;
}

/** Session + CSS-scope wrapper for the applicant surface (mounted at "/"). */
function WebLayout() {
  return (
    <SessionProvider>
      <div className="surface-web">
        <Outlet />
      </div>
    </SessionProvider>
  );
}

/** Web (applicant + public) routes, at the root. Returned into the top <Routes>. */
export function WebRoutes() {
  return (
    <Route element={<WebLayout />}>
      <Route path="/" element={<Landing />} />
      <Route path="/trust" element={<Trust />} />
      {/* First-run funnel — public, ahead of the session gate. */}
      <Route path="/welcome" element={<Welcome />} />
      <Route
        path="/explore"
        element={
          <RequireApplicant>
            <Feed />
          </RequireApplicant>
        }
      />
      <Route
        path="/explore/jobs/:jobId"
        element={
          <RequireApplicant>
            <JobDetail />
          </RequireApplicant>
        }
      />
      {/* More specific than /:jobId but React Router ranks by specificity, so order is safe. */}
      <Route
        path="/explore/jobs/:jobId/why"
        element={
          <RequireApplicant>
            <WhyMatch />
          </RequireApplicant>
        }
      />
      <Route
        path="/applications"
        element={
          <RequireApplicant>
            <Applications />
          </RequireApplicant>
        }
      />
      <Route
        path="/inbox"
        element={
          <RequireApplicant>
            <Inbox />
          </RequireApplicant>
        }
      />
      <Route
        path="/invites"
        element={
          <RequireApplicant>
            <Invites />
          </RequireApplicant>
        }
      />
      <Route
        path="/profile"
        element={
          <RequireApplicant>
            <Profile />
          </RequireApplicant>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Route>
  );
}
