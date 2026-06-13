/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Google Web OAuth client id (`*.apps.googleusercontent.com`). Optional — Google sign-in
   * hides itself when unset. */
  readonly VITE_GOOGLE_CLIENT_ID?: string;
  /** API base for the live exchange. Defaults to http://localhost:8000 when unset. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
