import { useEffect, useRef, useState } from "react";
import { loadGoogleIdentity } from "./google-gsi";

/**
 * Renders the official GIS button (dark theme, to match the control-room panel)
 * and fires `onCredential` with the Google ID token on success. Mirrors the
 * Flutter web flow: `initialize({client_id, callback})` then `renderButton`.
 *
 * `onCredential` is held in a ref so re-renders never re-`initialize` GIS (which
 * would re-draw the button and drop an in-flight prompt).
 */
export function GoogleButton({
  clientId,
  onCredential,
  onLoadError,
}: {
  clientId: string;
  onCredential: (idToken: string) => void;
  onLoadError: (message: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onCredentialRef = useRef(onCredential);
  onCredentialRef.current = onCredential;
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadGoogleIdentity()
      .then((id) => {
        if (cancelled || !containerRef.current) return;
        id.initialize({
          client_id: clientId,
          callback: (response) => onCredentialRef.current(response.credential),
        });
        id.renderButton(containerRef.current, {
          theme: "filled_black",
          size: "large",
          text: "continue_with",
          width: 320,
          logo_alignment: "left",
        });
        setReady(true);
      })
      .catch((e: unknown) => {
        if (!cancelled) onLoadError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [clientId, onLoadError]);

  return (
    <div className="google-signin">
      <div ref={containerRef} className="google-btn-host" aria-busy={!ready} />
      {!ready && <span className="k dim">loading Google sign-in…</span>}
    </div>
  );
}
