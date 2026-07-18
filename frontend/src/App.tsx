import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { EmployersRoutes } from "./sites/employers/EmployersRoutes";
import { ConsoleRoutes } from "./sites/console/ConsoleRoutes";

// console.jobify.com serves ONLY the console subtree, mounted at the root path
// (CONSOLE_BASE resolves to "" there — see sites/console/base.ts). Every other
// hostname serves the employers surfaces, with /console/* still reachable as a
// path prefix during the transition before DNS cutover.
const isConsoleHost = window.location.hostname.startsWith("console.");

export function App() {
  return (
    <HashRouter>
      {/* HashRouter: static bundle, no server rewrites, tokens stay out of paths. */}
      <Routes>
        {isConsoleHost ? (
          <>
            {ConsoleRoutes()}
            <Route path="/" element={<Navigate to="/signin" replace />} />
          </>
        ) : (
          <>
            {EmployersRoutes()}
            {ConsoleRoutes()}
            {/* Applicant-facing web surface removed — the Flutter app is the applicant client.
                This app now serves employers (marketing + recruiter workspace) and console
                (jobify-internal admin ops) only. */}
            <Route path="/" element={<Navigate to="/employers" replace />} />
          </>
        )}
      </Routes>
    </HashRouter>
  );
}
