import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { EmployersRoutes } from "./sites/employers/EmployersRoutes";
import { ConsoleRoutes } from "./sites/console/ConsoleRoutes";

export function App() {
  return (
    <HashRouter>
      {/* HashRouter: static bundle, no server rewrites, tokens stay out of paths. */}
      <Routes>
        {EmployersRoutes()}
        {ConsoleRoutes()}
        {/* Applicant-facing web surface removed — the Flutter app is the applicant client.
            This app now serves employers/recruiters (marketing) and console (recruiter ops + admin) only. */}
        <Route path="/" element={<Navigate to="/employers" replace />} />
      </Routes>
    </HashRouter>
  );
}
