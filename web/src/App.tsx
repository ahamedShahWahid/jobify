import { HashRouter, Route, Routes, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { Landing } from "./pages/Landing";
import { Trust } from "./pages/Trust";
import { Feed } from "./pages/explore/Feed";
import { Gate } from "./pages/explore/Gate";
import { JobDetail } from "./pages/explore/JobDetail";
import { SessionProvider, useSessionStore } from "./session";

/** Explore routes need an applicant session — otherwise show the sign-in gate. */
function RequireApplicant({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  return session ? <>{children}</> : <Gate />;
}

export function App() {
  return (
    <SessionProvider>
      {/* HashRouter: static bundle, no server rewrites, tokens stay out of paths. */}
      <HashRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/trust" element={<Trust />} />
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </HashRouter>
    </SessionProvider>
  );
}
