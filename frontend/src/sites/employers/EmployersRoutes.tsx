import { Outlet, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import "./styles/site.css";
import { Landing } from "./pages/Landing";
import { Verify } from "./pages/Verify";

/** The recruiter-facing console is the `/console` surface of this same app.
 *  Hash route (not an absolute port) so it resolves to the console sign-in on
 *  whatever origin the unified app is served from. */
export const CONSOLE_URL = "#/console/signin";

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

/** Employers (recruiter marketing) routes. Returned into the top <Routes>. */
export function EmployersRoutes() {
  return (
    <Route element={<EmployersLayout />}>
      <Route path="/employers" element={<Landing />} />
      <Route path="/employers/verify" element={<Verify />} />
      <Route path="/employers/*" element={<Navigate to="/employers" replace />} />
    </Route>
  );
}
