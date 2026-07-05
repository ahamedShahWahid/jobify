import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import { GoogleButton } from "../auth/GoogleButton";
import { ErrorNotice, Field, IstClock } from "../components/bits";
import { API_BASE_URL, GOOGLE_CLIENT_ID } from "../env";
import { landingFor } from "../landing";
import { useSessionStore } from "../session";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";

export function SignIn() {
  const { connectLive, connectGoogle, expired } = useSessionStore();
  const navigate = useNavigate();
  const [showManual, setShowManual] = useState(false);
  const [baseUrl, setBaseUrl] = useState(API_BASE_URL);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function asMessage(e: unknown): string {
    return e instanceof ApiError ? `${e.status || "network"}: ${e.detail}` : errorMessage(e);
  }

  async function connectManual() {
    setBusy(true);
    setError(null);
    try {
      const identity = await connectLive(baseUrl, token.trim());
      navigate(landingFor(identity.role));
    } catch (e) {
      setError(asMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const onGoogleCredential = useCallback(
    async (idToken: string) => {
      setBusy(true);
      setError(null);
      try {
        const identity = await connectGoogle(idToken, API_BASE_URL);
        navigate(landingFor(identity.role));
      } catch (e) {
        setError(asMessage(e));
      } finally {
        setBusy(false);
      }
    },
    [connectGoogle, navigate],
  );

  const onGoogleLoadError = useCallback((message: string) => setError(message), []);

  return (
    <div className="dash gate">
      <div className="gate-left">
        <div className="spread">
          <span className="k">jobify for employers</span>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <ThemeToggle />
            <IstClock />
          </div>
        </div>

        <img src="/jobify-mark.svg" alt="Jobify" className="gate-mark rise" />
        <h1 className="gate-title rise">
          EMPLOYER
          <span className="line2">WORKSPACE</span>
        </h1>

        <div className="stack">
          <p className="flavor rise" style={{ maxWidth: 520 }}>
            Post roles, review your ranked applicant stack, and manage your team — the job desk
            for hiring on Jobify.
          </p>
          <div className="gate-meta rise">
            <div className="cell">
              <span className="k">api</span>
              <span className="num">/v1 · problem+json</span>
            </div>
            <div className="cell">
              <span className="k">build</span>
              <span className="num">employers v0.1</span>
            </div>
          </div>
        </div>
      </div>

      <div className="gate-right">
        <div className="google-block rise">
          <span className="k">sign in</span>
          {GOOGLE_CLIENT_ID ? (
            <GoogleButton
              clientId={GOOGLE_CLIENT_ID}
              onCredential={onGoogleCredential}
              onLoadError={onGoogleLoadError}
            />
          ) : (
            <p className="dim google-hint">
              Set <code>VITE_GOOGLE_CLIENT_ID</code> to enable Google sign-in.
            </p>
          )}
          <p className="k google-note">
            New here? Sign in with Google and we&apos;ll walk you through setting up your company
            — your first posting is free. Already set up? Sign in the same way.
          </p>
        </div>

        {expired && !error && (
          <div className="notice rise">
            Your session ended — the access token expired or was rejected. Sign in with Google or
            paste a fresh token to continue.
          </div>
        )}

        <ErrorNotice error={error} />

        <button
          type="button"
          className="btn ghost sm rise"
          onClick={() => setShowManual((v) => !v)}
          style={{ marginTop: 18 }}
        >
          {showManual ? "Hide manual token entry" : "Paste an access token instead"}
        </button>

        {showManual && (
          <div className="rise" style={{ marginTop: 14 }}>
            <Field label="API base URL">
              <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </Field>
            <Field
              label="Access token (Bearer)"
              hint="Short-lived JWT from Google sign-in. Held in memory only — reload requires a fresh paste. The API must allow this origin in JOBIFY_CORS_ALLOW_ORIGINS."
            >
              <textarea
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="eyJhbGciOiJIUzI1NiIs…"
                spellCheck={false}
              />
            </Field>
            <button
              className="btn primary rise"
              onClick={connectManual}
              disabled={busy || !token.trim()}
            >
              {busy ? "Connecting…" : "Connect"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
