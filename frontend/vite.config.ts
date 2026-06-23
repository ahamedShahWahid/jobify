import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Single unified web app. Live surfaces (web applicant + console) need this
// origin in the API's JOBIFY_CORS_ALLOW_ORIGINS. See frontend/README.md.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
