import { HashRouter, Route, Routes, Navigate } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Verify } from "./pages/Verify";

/** The recruiter-facing console (dark ops app) lives here in dev. */
export const CONSOLE_URL = "http://localhost:5173";

export function App() {
  return (
    // HashRouter: static marketing bundle, no server rewrites needed.
    <HashRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}
