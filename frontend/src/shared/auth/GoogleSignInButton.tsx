import { useEffect, useRef, useState } from "react";
import { renderGoogleButton } from "./gsi";

/**
 * Renders the official GIS button and hands the Google ID token to `onCredential`.
 * While the SDK loads (or if it fails) a muted status line stands in. `theme`
 * selects the Google button style per surface ("outline" web, "filled_black" console).
 */
export function GoogleSignInButton({
  clientId,
  onCredential,
  theme = "outline",
  onLoadError,
}: {
  clientId: string;
  onCredential: (idToken: string) => void;
  theme?: "outline" | "filled_blue" | "filled_black";
  onLoadError?: (message: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  // Keep the latest callback without re-running the effect (which would re-init GIS).
  const cbRef = useRef(onCredential);
  cbRef.current = onCredential;
  const errRef = useRef(onLoadError);
  errRef.current = onLoadError;

  useEffect(() => {
    let cancelled = false;
    const el = containerRef.current;
    if (!el) return;
    renderGoogleButton(el, clientId, (idToken) => cbRef.current(idToken), theme)
      .then(() => {
        if (!cancelled) setStatus("ready");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setStatus("error");
        errRef.current?.(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [clientId, theme]);

  return (
    <div className="gsi">
      <div ref={containerRef} className="gsi-btn" aria-busy={status === "loading"} />
      {status === "loading" && <span className="gsi-hint dim">Loading Google sign-in…</span>}
      {status === "error" && (
        <span className="gsi-hint err">Couldn't load Google sign-in — check your connection.</span>
      )}
    </div>
  );
}
