/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Google **Web** OAuth client id (`*.apps.googleusercontent.com`). Unset ⇒ Google sign-in hidden. */
  readonly VITE_GOOGLE_CLIENT_ID?: string;
  /** API base URL for the live exchange + console calls (default `http://localhost:8000`). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
