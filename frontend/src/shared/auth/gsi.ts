/**
 * Google Identity Services (GIS) web helper. The imperative `signIn()` can't
 * return an ID token on web, so we `initialize({ callback })` + `renderButton`;
 * the callback yields `response.credential` (the Google ID token), exchanged
 * server-side for an access token. Minimal ambient types only — no `@types/...`.
 */

interface CredentialResponse {
  /** The Google ID token (JWT) — POST to /v1/auth/oauth/google. */
  credential: string;
}

interface GsiButtonConfiguration {
  theme?: "outline" | "filled_blue" | "filled_black";
  size?: "small" | "medium" | "large";
  text?: "signin_with" | "signup_with" | "continue_with" | "signin";
  shape?: "rectangular" | "pill" | "circle" | "square";
  logo_alignment?: "left" | "center";
  width?: number;
}

interface GsiIdConfiguration {
  client_id: string;
  callback: (response: CredentialResponse) => void;
  auto_select?: boolean;
  use_fedcm_for_prompt?: boolean;
}

interface GoogleAccountsId {
  initialize(config: GsiIdConfiguration): void;
  renderButton(parent: HTMLElement, options: GsiButtonConfiguration): void;
  cancel(): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } };
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";
let loadPromise: Promise<GoogleAccountsId> | null = null;

/** Inject the GIS SDK once (idempotent) and resolve with `google.accounts.id`. */
export function loadGsi(): Promise<GoogleAccountsId> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<GoogleAccountsId>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    const onReady = () => {
      const id = window.google?.accounts?.id;
      if (id) resolve(id);
      else reject(new Error("Google Identity Services loaded but window.google.accounts.id is missing"));
    };
    const onFail = () => {
      loadPromise = null; // allow a retry after a transient network failure
      reject(new Error("failed to load Google Identity Services"));
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
  return loadPromise;
}

/** Initialize GIS for `clientId` and render the official button into `container`.
 *  `onCredential` fires with the Google ID token on a successful sign-in. */
export async function renderGoogleButton(
  container: HTMLElement,
  clientId: string,
  onCredential: (idToken: string) => void,
  theme: GsiButtonConfiguration["theme"] = "outline",
): Promise<void> {
  const id = await loadGsi();
  id.initialize({
    client_id: clientId,
    callback: (response) => onCredential(response.credential),
    use_fedcm_for_prompt: true,
  });
  id.renderButton(container, {
    theme,
    size: "large",
    text: "continue_with",
    shape: "rectangular",
    logo_alignment: "left",
    width: 320,
  });
}
