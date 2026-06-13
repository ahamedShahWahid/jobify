import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import { ErrorNotice, Field, UtcClock } from "../components/bits";
import { landingFor, useSessionStore } from "../session";

export function SignIn() {
  const { connectLive, connectDemo, expired } = useSessionStore();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [demoRole, setDemoRole] = useState<"admin" | "recruiter">("admin");
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const identity =
        mode === "demo" ? await connectDemo(demoRole) : await connectLive(baseUrl, token.trim());
      navigate(landingFor(identity.role));
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status || "network"}: ${e.detail}` : errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="gate" data-area="admin">
      <div className="gate-left">
        <div className="spread">
          <span className="k">jobify internal · restricted</span>
          <UtcClock />
        </div>

        <h1 className="gate-title rise">
          OPERATIONS
          <span className="line2">CONSOLE</span>
        </h1>

        <div className="stack">
          <p className="flavor rise" style={{ maxWidth: 520 }}>
            Moderation and recruiting operations for the Jobify placement platform — the audit
            trail, the suspend lever, the job desk, and the team roster, in one instrument panel.
          </p>
          <div className="gate-meta rise">
            <div className="cell">
              <span className="k">areas</span>
              <span>
                <span style={{ color: "#ffb000" }}>■</span> admin&nbsp;&nbsp;
                <span style={{ color: "#4fe3c1" }}>■</span> recruiter
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
            Your session ended — the access token expired or was rejected. Paste a fresh token to
            continue.
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
            <span className="k">enter as</span>
            <div className="mode-tabs" style={{ marginTop: 6 }}>
              <button
                className={demoRole === "admin" ? "on" : ""}
                onClick={() => setDemoRole("admin")}
              >
                Admin
              </button>
              <button
                className={demoRole === "recruiter" ? "on" : ""}
                onClick={() => setDemoRole("recruiter")}
              >
                Recruiter
              </button>
            </div>
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
          your role decides what you can reach — admins land in moderation, recruiters at the job
          desk
        </p>
      </div>
    </div>
  );
}
