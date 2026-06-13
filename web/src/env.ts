/**
 * Compile-time config from Vite env (`import.meta.env`). Both are optional at the
 * type level; `GOOGLE_CLIENT_ID` being undefined disables the Google button without
 * crashing the gate (demo + paste-token keep working).
 */

/** Google Web OAuth client id, or undefined when `VITE_GOOGLE_CLIENT_ID` is unset. */
export const GOOGLE_CLIENT_ID: string | undefined = import.meta.env.VITE_GOOGLE_CLIENT_ID;

/** API base for the live token exchange; defaults to the local dev API. */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
