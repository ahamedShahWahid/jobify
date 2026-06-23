import { HashRouter, Routes } from "react-router-dom";
import { EmployersRoutes } from "./sites/employers/EmployersRoutes";
import { ConsoleRoutes } from "./sites/console/ConsoleRoutes";
import { WebRoutes } from "./sites/web/WebRoutes";

export function App() {
  return (
    <HashRouter>
      {/* HashRouter: static bundle, no server rewrites, tokens stay out of paths. */}
      <Routes>
        {EmployersRoutes()}
        {ConsoleRoutes()}
        {WebRoutes()}
      </Routes>
    </HashRouter>
  );
}
