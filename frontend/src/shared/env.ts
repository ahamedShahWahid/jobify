/**
 * Build-time config from Vite env (`VITE_*`, baked at `vite build`).
 * `GOOGLE_CLIENT_ID` is optional — when unset the sign-in gate hides the Google
 * button (demo + paste-token still work).
 */

/** Google **Web** OAuth client id; `undefined` ⇒ Google sign-in disabled. */
export const GOOGLE_CLIENT_ID: string | undefined =
  import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim() || undefined;

/** API base for the Google exchange + live calls; defaults to the local dev API. */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000";
