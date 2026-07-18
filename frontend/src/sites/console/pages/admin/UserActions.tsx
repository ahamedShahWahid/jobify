import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { AdminUserRead } from "../../api/types";
import { ErrorNotice, Field, Stamp } from "../../components/bits";
import { useSession } from "../../session";
import { CONSOLE_BASE } from "../../base";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function UserActions() {
  const { client } = useSession();
  const [params, setParams] = useSearchParams();

  const [userId, setUserId] = useState(params.get("user") ?? "");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<"suspend" | "unsuspend" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AdminUserRead | null>(null);

  const validId = UUID_RE.test(userId.trim());

  async function run(kind: "suspend" | "unsuspend") {
    setBusy(kind);
    setError(null);
    setResult(null);
    try {
      const id = userId.trim();
      const user =
        kind === "suspend"
          ? await client.suspendUser(id, reason.trim())
          : await client.unsuspendUser(id);
      setResult(user);
      setParams({ user: id });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <div className="headline rise">
        <h1>
          USER <span className="ghost">ACTIONS</span>
        </h1>
        <div className="sub">
          <span className="flavor">The suspend lever — pulled deliberately, logged always.</span>
        </div>
      </div>

      <div className="notice rise">
        The API exposes no user search — moderation is keyed by user UUID. Find subjects in the{" "}
        <Link to={`${CONSOLE_BASE}/admin/audit`}>audit trail</Link> (any actor or user-resource id is clickable and
        lands here pre-filled). Every action below writes an <span>admin.user.*</span>{" "}
        audit row.
      </div>

      <div className="panel rise" style={{ maxWidth: 640 }}>
        <div className="panel-head">
          <span className="k">subject</span>
          {validId ? (
            <span className="chip ok">valid uuid</span>
          ) : (
            <span className="chip">awaiting uuid</span>
          )}
        </div>
        <div className="panel-body">
          <Field label="User id">
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="00000000-0000-4000-8000-000000000000"
              spellCheck={false}
            />
          </Field>
          <Field
            label="Suspension reason"
            hint="Required to suspend; shown to tooling and stored on the user row (1–255 chars). Re-suspending writes a fresh audit row — the reason is evidence."
          >
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={255}
              placeholder="e.g. spam job postings"
            />
          </Field>
          <div className="row">
            <button
              className="btn danger"
              disabled={!validId || !reason.trim() || busy !== null}
              onClick={() => void run("suspend")}
            >
              {busy === "suspend" ? "Suspending…" : "Suspend"}
            </button>
            <button
              className="btn"
              disabled={!validId || busy !== null}
              onClick={() => void run("unsuspend")}
            >
              {busy === "unsuspend" ? "Lifting…" : "Lift suspension"}
            </button>
          </div>
        </div>
      </div>

      <div className="mt" />
      <ErrorNotice error={error} />

      {result && (
        <div className="panel rise" style={{ maxWidth: 640 }}>
          <div className="panel-head">
            <span className="k">result</span>
            {result.suspended_at ? (
              <span className="chip danger">
                <span className="led red" /> suspended
              </span>
            ) : (
              <span className="chip ok">
                <span className="led" /> active
              </span>
            )}
          </div>
          <div className="panel-body stack">
            <div className="spread">
              <span className="k">user</span>
              <span className="num">{result.id}</span>
            </div>
            <div className="spread">
              <span className="k">email</span>
              <span>{result.email ?? <span className="dim">— (scrubbed)</span>}</span>
            </div>
            <div className="spread">
              <span className="k">role</span>
              <span className="chip">{result.role}</span>
            </div>
            {result.suspended_at && (
              <>
                <div className="spread">
                  <span className="k">suspended at</span>
                  <Stamp iso={result.suspended_at} />
                </div>
                <div className="spread">
                  <span className="k">reason</span>
                  <span>{result.suspension_reason}</span>
                </div>
              </>
            )}
            <div className="row">
              <Link className="btn ghost sm" to={`${CONSOLE_BASE}/admin/audit?actor=${result.id}`}>
                View their actions in the trail →
              </Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
