import { useEffect, useRef, useState } from "react";
import { renderGoogleButton } from "./gsi";

/**
 * Renders the official Google Identity Services button. On a successful sign-in
 * it hands the Google ID token to `onCredential`. While the GIS SDK loads (or if
 * loading fails) a muted status line stands in for the button.
 */
export function GoogleSignInButton({
  clientId,
  onCredential,
}: {
  clientId: string;
  onCredential: (idToken: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  // Keep the latest callback without re-running the effect (which would re-render
  // the GIS button and could double-init).
  const cbRef = useRef(onCredential);
  cbRef.current = onCredential;

  useEffect(() => {
    let cancelled = false;
    const el = containerRef.current;
    if (!el) return;
    renderGoogleButton(el, clientId, (idToken) => cbRef.current(idToken))
      .then(() => {
        if (!cancelled) setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  return (
    <div className="gsi">
      <div ref={containerRef} className="gsi-btn" />
      {status === "loading" && <span className="gsi-hint dim">Loading Google sign-in…</span>}
      {status === "error" && (
        <span className="gsi-hint err">Couldn’t load Google sign-in — check your connection.</span>
      )}
    </div>
  );
}
