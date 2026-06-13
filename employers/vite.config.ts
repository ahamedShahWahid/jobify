import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Port 5373 keeps this clear of the console (5173) and the applicant web app
// (5273). Marketing-only surface — no live API, so no CORS wiring needed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5373 },
});
