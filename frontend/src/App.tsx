import { HashRouter, Routes, Route } from "react-router-dom";

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="*" element={<p style={{ padding: 24 }}>frontend scaffold OK</p>} />
      </Routes>
    </HashRouter>
  );
}
