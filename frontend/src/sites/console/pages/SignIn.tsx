import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import { GoogleButton } from "../auth/GoogleButton";
import { ErrorNotice, Field, IstClock } from "../components/bits";
import { API_BASE_URL, GOOGLE_CLIENT_ID } from "../env";
import { landingFor, useSessionStore } from "../session";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";

export function SignIn() {
  const { connectLive, connectGoogle, connectDemo, expired } = useSessionStore();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [baseUrl, setBaseUrl] = useState(API_BASE_URL);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function asMessage(e: unknown): string {
    return e instanceof ApiError ? `${e.status || "network"}: ${e.detail}` : errorMessage(e);
  }

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const identity =
        mode === "demo" ? await connectDemo() : await connectLive(baseUrl, token.trim());
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
    <div className="gate">
      <div className="gate-left">
        <div className="spread">
          <span className="k">jobify internal · restricted</span>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <ThemeToggle />
            <IstClock />
          </div>
        </div>

        <img src="/jobify-mark.svg" alt="Jobify" className="gate-mark rise" />
        <h1 className="gate-title rise">
          OPERATIONS
          <span className="line2">CONSOLE</span>
        </h1>

        <div className="stack">
          <p className="flavor rise" style={{ maxWidth: 520 }}>
            Moderation operations for the Jobify placement platform — the audit trail, the
            suspend lever, and the employer verification queue, in one instrument panel.
          </p>
          <div className="gate-meta rise">
            <div className="cell">
              <span className="k">access</span>
              <span>
                <span style={{ color: "#ffb000" }}>■</span> jobify staff only
              </span>
            </div>
            <div className="cell">
              <span className="k">api</span>
              <span className="num">/v1 · problem+json</span>
            </div>
            <div className="cell">
              <span className="k">build</span>
              <span className="num">console v0.1</span>
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
            jobify staff only — recruiters sign in at the employers workspace instead. New Google
            users provision as applicants and see the no-access page.
          </p>
        </div>

        <div className="google-divider rise">
          <span>or use a manual session</span>
        </div>

        <div className="mode-tabs rise">
          <button className={mode === "demo" ? "on" : ""} onClick={() => setMode("demo")}>
            Demo data
          </button>
          <button className={mode === "live" ? "on" : ""} onClick={() => setMode("live")}>
            Live API
          </button>
        </div>

        {expired && !error && (
          <div className="notice rise">
            Your session ended — the access token expired or was rejected. Sign in with Google or
            paste a fresh token to continue.
          </div>
        )}

        <ErrorNotice error={error} />

        {mode === "live" ? (
          <div className="rise">
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
          </div>
        ) : (
          <div className="rise" style={{ marginBottom: 22 }}>
            <p className="dim" style={{ marginBottom: 14 }}>
              Explore the full console against seeded in-memory fixtures — every table, drawer and
              action works; nothing leaves the browser.
            </p>
          </div>
        )}

        <button
          className="btn primary rise"
          onClick={connect}
          disabled={busy || (mode === "live" && !token.trim())}
        >
          {busy ? "Connecting…" : mode === "demo" ? "Enter demo console" : "Connect"}
        </button>

        <p className="k" style={{ marginTop: 26 }}>
          jobify staff only — your role decides what you can reach
        </p>
      </div>
    </div>
  );
}
