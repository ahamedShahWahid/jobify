/**
 * Minimal Google Identity Services (GIS) web helper.
 *
 * Mirrors the Flutter web reference: the imperative `signIn()` cannot return an ID
 * token on web, so we use `renderButton` + an `initialize({ callback })` whose
 * `callback(response)` yields `response.credential` (the Google ID token). That token
 * is exchanged server-side for an access token — the gate never holds it long.
 *
 * Ambient types are intentionally minimal (no `@types/...` dependency).
 */

/* --- minimal ambient GIS types ------------------------------------------- */

interface CredentialResponse {
  /** The Google ID token (JWT). */
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

/* --- script loader -------------------------------------------------------- */

const GSI_SRC = "https://accounts.google.com/gsi/client";
let loadPromise: Promise<GoogleAccountsId> | null = null;

/** Inject the GIS SDK once and resolve with `google.accounts.id` when ready. */
export function loadGsi(): Promise<GoogleAccountsId> {
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<GoogleAccountsId>((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve(window.google.accounts.id);
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    const onReady = () => {
      if (window.google?.accounts?.id) resolve(window.google.accounts.id);
      else reject(new Error("Google Identity Services loaded but window.google.accounts.id is missing"));
    };

    if (existing) {
      existing.addEventListener("load", onReady, { once: true });
      existing.addEventListener("error", () => reject(new Error("failed to load Google Identity Services")), {
        once: true,
      });
      return;
    }

    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", onReady, { once: true });
    script.addEventListener("error", () => {
      loadPromise = null; // allow a retry after a transient network failure
      reject(new Error("failed to load Google Identity Services"));
    });
    document.head.appendChild(script);
  });

  return loadPromise;
}

/**
 * Initialize GIS for `clientId` and render the official button into `container`.
 * `onCredential` fires with the Google ID token on a successful sign-in.
 */
export async function renderGoogleButton(
  container: HTMLElement,
  clientId: string,
  onCredential: (idToken: string) => void,
): Promise<void> {
  const id = await loadGsi();
  id.initialize({
    client_id: clientId,
    callback: (response) => onCredential(response.credential),
    use_fedcm_for_prompt: true,
  });
  id.renderButton(container, {
    theme: "outline",
    size: "large",
    text: "continue_with",
    shape: "rectangular",
    logo_alignment: "left",
    width: 320,
  });
}
