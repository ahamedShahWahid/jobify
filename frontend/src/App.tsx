import { HashRouter, Routes } from "react-router-dom";
import { ConsoleRoutes } from "./sites/console/ConsoleRoutes";
import { WebRoutes } from "./sites/web/WebRoutes";

export function App() {
  return (
    <HashRouter>
      {/* HashRouter: static bundle, no server rewrites, tokens stay out of paths. */}
      <Routes>
        {ConsoleRoutes()}
        {WebRoutes()}
      </Routes>
    </HashRouter>
  );
}
