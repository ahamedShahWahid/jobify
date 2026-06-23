import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage } from "../../api/client";
import { GoogleSignInButton } from "../../auth/GoogleSignInButton";
import { Masthead } from "../../components/Chrome";
import { API_BASE_URL, GOOGLE_CLIENT_ID } from "../../env";
import { useSessionStore } from "../../session";

/**
 * The Explore surface needs an applicant session. Google sign-in is the primary,
 * real path (ID token → access token → live session). Demo mode runs against seeded
 * fixtures (no backend); live mode takes a pasted applicant access token (dev aid).
 */
export function Gate() {
  const { connectDemo, connectLive, connectGoogle, expired } = useSessionStore();
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function showError(e: unknown) {
    setError(e instanceof ApiError ? `${e.status || "network"}: ${e.detail}` : errorMessage(e));
  }

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      if (mode === "demo") await connectDemo();
      else await connectLive(baseUrl, token.trim());
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  }

  async function onGoogleCredential(idToken: string) {
    setBusy(true);
    setError(null);
    try {
      await connectGoogle(idToken, API_BASE_URL);
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Masthead />
      <div className="wrap">
        <div className="gate rise">
          <div className="gate-head">
            <span className="kicker">Your feed</span>
            <h1>Open the matched feed</h1>
            <p className="dim" style={{ margin: 0 }}>
              Six demo matches are waiting — or connect a live applicant token.
            </p>
          </div>
          <div className="gate-body">
            <div className="google-gate">
              <span className="kicker ink">Sign in</span>
              <p className="dim" style={{ margin: "2px 0 14px" }}>
                Use your Google account to open your real matched feed.
              </p>
              {GOOGLE_CLIENT_ID ? (
                <GoogleSignInButton clientId={GOOGLE_CLIENT_ID} onCredential={onGoogleCredential} />
              ) : (
                <p className="gsi-hint dim" style={{ margin: 0 }}>
                  Set <code>VITE_GOOGLE_CLIENT_ID</code> to enable Google sign-in.
                </p>
              )}
            </div>

            <div className="gate-or">
              <span>or explore without an account</span>
            </div>

            <div className="seg">
              <button className={mode === "demo" ? "on" : ""} onClick={() => setMode("demo")}>
                Demo feed
              </button>
              <button className={mode === "live" ? "on" : ""} onClick={() => setMode("live")}>
                Live token
              </button>
            </div>

            {expired && !error && (
              <div className="notice">
                Your session ended — the access token expired or was rejected. Reconnect to
                continue.
              </div>
            )}
            {error && <div className="notice err">⚠ {error}</div>}

            {mode === "live" ? (
              <>
                <div className="field">
                  <label>API base URL</label>
                  <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                </div>
                <div className="field">
                  <label>Applicant access token</label>
                  <textarea
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="eyJhbGciOiJIUzI1NiIs…"
                    spellCheck={false}
                  />
                  <span className="hint">
                    Short-lived applicant JWT (Google sign-in). Held in memory only. The API must
                    allow this origin in JOBIFY_CORS_ALLOW_ORIGINS.
                  </span>
                </div>
              </>
            ) : (
              <p className="dim" style={{ marginTop: 0, marginBottom: 22 }}>
                Explore the full applicant experience — feed, job detail with score breakdown, apply
                and save — against seeded data. Nothing leaves your browser.
              </p>
            )}

            <button
              className="btn primary"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={connect}
              disabled={busy || (mode === "live" && !token.trim())}
            >
              {busy ? "Connecting…" : mode === "demo" ? "Enter the demo feed →" : "Connect →"}
            </button>

            <p className="center mt">
              <Link to="/" className="link-arrow" style={{ fontSize: 13 }}>
                ← Back to home
              </Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
