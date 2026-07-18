import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import type { EmployerRead } from "../api/types";
import { ErrorNotice, Field } from "../components/bits";
import { useSession, useSessionStore } from "../session";

/** First-run setup for a signed-in user whose role is still "applicant" (see
 *  landingFor.ts, which routes them here instead of /no-access). Creating an
 *  employer flips APPLICANT -> RECRUITER server-side; refreshIdentity() then
 *  re-fetches /v1/me so the very next navigation is admitted as a recruiter. */
export function Onboarding() {
  const { identity, client } = useSession();
  const { refreshIdentity } = useSessionStore();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [gst, setGst] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function asMessage(e: unknown): string {
    if (e instanceof ApiError && e.status === 409) {
      return "That company name is already registered — try a slightly different name.";
    }
    return errorMessage(e);
  }

  const nameValid = name.trim().length >= 2 && name.trim().length <= 200;
  const gstValid = gst.trim().length === 0 || gst.trim().length === 15;

  async function submit() {
    setBusy(true);
    setError(null);
    let created: EmployerRead;
    try {
      created = await client.createEmployer({ name: name.trim(), gst: gst.trim() || undefined });
    } catch (e) {
      setError(asMessage(e));
      setBusy(false);
      return;
    }
    try {
      await refreshIdentity();
      navigate("/employers/jobs/new");
    } catch {
      // createEmployer already committed (employer + role flip are atomic server-side) —
      // this is a refresh failure, not a creation failure. Retrying the form would just
      // hit a 409 on the now-existing company name, so point at the one safe recovery
      // path instead of inviting an immediate resubmit.
      setError(
        `"${created.name}" was created — we just couldn't refresh your session. Use "Log out" in the sidebar and sign back in to continue.`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="headline">
        <h1>
          SET UP <span className="ghost">YOUR COMPANY</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            One step between {identity.email ?? "you"} and your first posting — it&apos;s free.
          </span>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 560 }}>
        <div className="panel-head">
          <span className="k">Company details</span>
        </div>
        <div className="panel-body">
          <Field label="Company name" hint="2–200 characters.">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Robotics" />
          </Field>
          <Field label="GST (optional)" hint="15 characters, if you have one — you can add this later too.">
            <input value={gst} onChange={(e) => setGst(e.target.value)} placeholder="29ABCDE1234F1Z5" />
          </Field>

          <ErrorNotice error={error} />

          <button
            className="btn primary"
            onClick={submit}
            disabled={busy || !nameValid || !gstValid}
            style={{ marginTop: 12 }}
          >
            {busy ? "Setting up…" : "Create workspace & post your first role"}
          </button>
        </div>
      </div>
    </>
  );
}
