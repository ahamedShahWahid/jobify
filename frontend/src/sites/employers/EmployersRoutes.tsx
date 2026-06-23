import { Outlet, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import "./styles/site.css";
import { Landing } from "./pages/Landing";
import { Verify } from "./pages/Verify";

/** The recruiter-facing console (dark ops app) lives here in dev. */
export const CONSOLE_URL = "http://localhost:5173";

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
