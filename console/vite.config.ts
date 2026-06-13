import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Port 5173 must be present in the API's JOBIFY_CORS_ALLOW_ORIGINS for live
// mode (demo mode needs no backend). See console/README.md.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
