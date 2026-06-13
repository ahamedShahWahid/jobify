/**
 * Google Identity Services (GIS) web helper — the same flow the Flutter web app
 * uses: render the official Google button and read `response.credential` (the
 * Google ID token) in the callback. The imperative `signIn()` can't return an
 * ID token on web, so `renderButton` is the only way to get one.
 *
 * Minimal ambient types for `window.google.accounts.id` live here (no
 * `@types/...` dependency). Only the surface we call is typed.
 */

interface CredentialResponse {
  /** The Google ID token (JWT) — POST this to `/v1/auth/oauth/google`. */
  credential: string;
}

interface IdConfiguration {
  client_id: string;
  callback: (response: CredentialResponse) => void;
}

interface GsiButtonConfiguration {
  theme?: "outline" | "filled_blue" | "filled_black";
  size?: "small" | "medium" | "large";
  text?: "signin_with" | "signup_with" | "continue_with" | "signin";
  width?: number;
  logo_alignment?: "left" | "center";
}

interface GoogleAccountsId {
  initialize: (config: IdConfiguration) => void;
  renderButton: (parent: HTMLElement, options: GsiButtonConfiguration) => void;
  cancel: () => void;
}

interface GoogleNamespace {
  accounts: { id: GoogleAccountsId };
}

declare global {
  interface Window {
    google?: GoogleNamespace;
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";

let loaderPromise: Promise<GoogleAccountsId> | null = null;

/** Inject the GIS SDK once (idempotent) and resolve with `google.accounts.id`. */
export function loadGoogleIdentity(): Promise<GoogleAccountsId> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (loaderPromise) return loaderPromise;

  loaderPromise = new Promise<GoogleAccountsId>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    const onReady = () => {
      const id = window.google?.accounts?.id;
      if (id) resolve(id);
      else reject(new Error("Google Identity Services loaded but `google.accounts.id` is missing."));
    };
    const onFail = () => {
      loaderPromise = null; // allow a retry on the next attempt
      reject(new Error("Failed to load Google Identity Services — check your network/CSP."));
    };

    if (existing) {
      existing.addEventListener("load", onReady, { once: true });
      existing.addEventListener("error", onFail, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", onReady, { once: true });
    script.addEventListener("error", onFail, { once: true });
    document.head.appendChild(script);
  });
  return loaderPromise;
}

export type { CredentialResponse, GoogleAccountsId, GsiButtonConfiguration };
