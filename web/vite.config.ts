import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Port 5273 keeps this clear of the console's 5173. For live mode the API must
// list this origin in JOBIFY_CORS_ALLOW_ORIGINS (see web/README.md).
export default defineConfig({
  plugins: [react()],
  server: { port: 5273 },
});
