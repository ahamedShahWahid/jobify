import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { EmployerRead, JobCreate, JobPatch, RecruiterJobRow } from "../../api/types";
import { Drawer, EmptyState, ErrorNotice, Field, Stamp } from "../../components/bits";
import { usePagedFetch } from "../../paging/usePagedFetch";
import { useSession } from "../../session";

const lakh = (value: number | null) =>
  value === null ? null : `₹${(value / 100_000).toFixed(value % 100_000 === 0 ? 0 : 1)}L`;

function ctcBand(job: RecruiterJobRow) {
  const min = lakh(job.ctc_min);
  const max = lakh(job.ctc_max);
  if (!min && !max) return <span className="dim">undisclosed</span>;
  return <span className="num">{[min, max].filter(Boolean).join(" – ")}</span>;
}

interface JobFormState {
  employer_id: string;
  title: string;
  description: string;
  locations: string;
  min_exp_years: string;
  max_exp_years: string;
  ctc_min: string;
  ctc_max: string;
}

const emptyForm = (employerId: string): JobFormState => ({
  employer_id: employerId,
  title: "",
  description: "",
  locations: "",
  min_exp_years: "0",
  max_exp_years: "5",
  ctc_min: "",
  ctc_max: "",
});

/** Whole number in [0,50] or null if the field is blank/non-integer (NOT 0). */
function parseExp(raw: string): number | null {
  if (raw.trim() === "") return null;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 0 && n <= 50 ? n : null;
}

/** undefined = blank (send null) · null = invalid · number = a valid CTC ≥ 0. */
function parseCtc(raw: string): number | null | undefined {
  if (raw.trim() === "") return undefined;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/**
 * Validate + build the payload, mirroring the backend's JobCreate constraints
 * and the _ordered_bands model validator. Returning the error here means the
 * operator sees a plain message instead of a raw 422 list, and a blank exp field
 * is flagged as missing rather than silently coerced to 0 (which a PATCH would
 * otherwise write over a real value).
 */
function buildJobPayload(
  form: JobFormState,
  isCreate: boolean,
): { payload: JobCreate | JobPatch } | { error: string } {
  const title = form.title.trim();
  if (title.length < 2 || title.length > 200)
    return { error: "Title must be 2–200 characters." };

  const description = form.description.trim();
  if (description.length < 10 || description.length > 10_000)
    return { error: "Description must be 10–10,000 characters." };

  const locations = form.locations
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (locations.length === 0) return { error: "Add at least one location." };
  if (locations.length > 20) return { error: "At most 20 locations." };

  const minExp = parseExp(form.min_exp_years);
  if (minExp === null) return { error: "Min experience must be a whole number from 0 to 50." };
  const maxExp = parseExp(form.max_exp_years);
  if (maxExp === null) return { error: "Max experience must be a whole number from 0 to 50." };
  if (maxExp < minExp) return { error: "Max experience must be ≥ min experience." };

  const ctcMin = parseCtc(form.ctc_min);
  if (ctcMin === null) return { error: "CTC min must be a number ≥ 0 (or blank)." };
  const ctcMax = parseCtc(form.ctc_max);
  if (ctcMax === null) return { error: "CTC max must be a number ≥ 0 (or blank)." };
  if (ctcMin !== undefined && ctcMax !== undefined && ctcMax < ctcMin)
    return { error: "CTC max must be ≥ CTC min." };

  const base = {
    title,
    description,
    locations,
    min_exp_years: minExp,
    max_exp_years: maxExp,
    ctc_min: ctcMin ?? null,
    ctc_max: ctcMax ?? null,
  };
  if (isCreate) {
    if (!form.employer_id) return { error: "Choose an employer." };
    return { payload: { ...base, employer_id: form.employer_id } };
  }
  return { payload: base };
}

export function Jobs() {
  const { client } = useSession();
  const [status, setStatus] = useState<"open" | "closed">("open");
  const [employers, setEmployers] = useState<EmployerRead[]>([]);
  const [opError, setOpError] = useState<string | null>(null);

  const fetcher = useCallback(
    (cursor: string | undefined) => client.listMyJobs(status, cursor),
    [client, status],
  );
  const { rows, nextCursor, busy, error, reload, loadMore } = usePagedFetch(fetcher, status);

  // drawer state: null = closed; "new" = create; otherwise the job being edited
  const [editing, setEditing] = useState<"new" | RecruiterJobRow | null>(null);
  const [form, setForm] = useState<JobFormState>(emptyForm(""));
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    client.myEmployers().then(setEmployers, () => undefined);
  }, [client]);

  function openCreate() {
    setForm(emptyForm(employers[0]?.id ?? ""));
    setFormError(null);
    setEditing("new");
  }

  function openEdit(job: RecruiterJobRow) {
    setForm({
      employer_id: "",
      title: job.title,
      description: job.description,
      locations: job.locations.join(", "),
      min_exp_years: String(job.min_exp_years),
      max_exp_years: String(job.max_exp_years),
      ctc_min: job.ctc_min === null ? "" : String(job.ctc_min),
      ctc_max: job.ctc_max === null ? "" : String(job.ctc_max),
    });
    setFormError(null);
    setEditing(job);
  }

  async function save() {
    const built = buildJobPayload(form, editing === "new");
    if ("error" in built) {
      setFormError(built.error);
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (editing === "new") {
        await client.createJob(built.payload as JobCreate);
      } else if (editing) {
        await client.patchJob(editing.id, built.payload);
      }
      setEditing(null);
      reload();
    } catch (e) {
      setFormError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function flipStatus(job: RecruiterJobRow) {
    setOpError(null);
    try {
      await client.patchJob(job.id, { status: job.status === "open" ? "closed" : "open" });
      reload();
    } catch (e) {
      setOpError(errorMessage(e));
    }
  }

  async function remove(job: RecruiterJobRow) {
    if (!window.confirm(`Delete "${job.title}"? Applicants keep their history; the posting goes.`))
      return;
    setOpError(null);
    try {
      await client.deleteJob(job.id);
      reload();
    } catch (e) {
      setOpError(errorMessage(e));
    }
  }

  return (
    <>
      <div className="headline rise">
        <h1>
          POSTINGS<span className="ghost">/{status.toUpperCase()}</span>
        </h1>
        <div className="sub">
          <span className="flavor">Write the role the way you'd want to read it.</span>
        </div>
      </div>

      <div className="spread rise mb">
        <div className="mode-tabs" style={{ marginBottom: 0, width: 260 }}>
          <button className={status === "open" ? "on" : ""} onClick={() => setStatus("open")}>
            Open
          </button>
          <button className={status === "closed" ? "on" : ""} onClick={() => setStatus("closed")}>
            Closed
          </button>
        </div>
        <button className="btn primary" onClick={openCreate} disabled={employers.length === 0}>
          + New posting
        </button>
      </div>

      <ErrorNotice error={error ?? opError} />

      <div className="table-wrap rise">
        <table className="console">
          <thead>
            <tr>
              <th>Title</th>
              <th>Band</th>
              <th>Exp</th>
              <th>Posted</th>
              <th className="r">Applicants</th>
              <th className="r">Surfaced</th>
              <th className="r">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((job) => (
              <tr key={job.id}>
                <td style={{ maxWidth: 320 }}>
                  <Link to={`/recruiter/jobs/${job.id}/applicants`}>{job.title}</Link>
                  <div className="k" style={{ marginTop: 2 }}>
                    {job.locations.join(" · ")}
                    {!job.employer_verified && (
                      <span className="chip" style={{ marginLeft: 8 }}>
                        unverified employer
                      </span>
                    )}
                  </div>
                </td>
                <td>{ctcBand(job)}</td>
                <td className="num">
                  {job.min_exp_years}–{job.max_exp_years}y
                </td>
                <td>
                  <Stamp iso={job.posted_at} />
                </td>
                <td className="r num">
                  <Link to={`/recruiter/jobs/${job.id}/applicants`}>{job.applicant_count}</Link>
                </td>
                <td className="r num acc">{job.surfaced_match_count}</td>
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  <button className="btn ghost sm" onClick={() => openEdit(job)}>
                    Edit
                  </button>{" "}
                  <button className="btn sm" onClick={() => void flipStatus(job)}>
                    {job.status === "open" ? "Close" : "Reopen"}
                  </button>{" "}
                  <button className="btn danger sm" onClick={() => void remove(job)}>
                    Del
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !busy && (
          <EmptyState>
            {status === "open" ? "Nothing open right now." : "Nothing has been closed yet."}
          </EmptyState>
        )}
      </div>

      <div className="row mt">
        {nextCursor && (
          <button className="btn" disabled={busy} onClick={loadMore}>
            {busy ? "Loading…" : "Load more"}
          </button>
        )}
      </div>

      {editing !== null && (
        <Drawer
          title={editing === "new" ? "New posting" : `Edit — ${editing.title}`}
          onClose={() => setEditing(null)}
          foot={
            <>
              <button className="btn ghost" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button className="btn primary" onClick={() => void save()} disabled={saving}>
                {saving ? "Saving…" : editing === "new" ? "Publish posting" : "Save changes"}
              </button>
            </>
          }
        >
          <ErrorNotice error={formError} />
          {editing === "new" && (
            <Field label="Employer">
              <select
                value={form.employer_id}
                onChange={(e) => setForm({ ...form, employer_id: e.target.value })}
              >
                {employers.map((employer) => (
                  <option key={employer.id} value={employer.id}>
                    {employer.name}
                    {employer.verified_at ? "" : " (unverified)"}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label="Title">
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              maxLength={200}
            />
          </Field>
          <Field label="Description" hint="10–10,000 chars. Editing content re-embeds the job for matching.">
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={7}
            />
          </Field>
          <Field label="Locations" hint="Comma-separated, e.g. Bengaluru, Remote (IN)">
            <input
              value={form.locations}
              onChange={(e) => setForm({ ...form, locations: e.target.value })}
            />
          </Field>
          <div className="field-row">
            <Field label="Min exp (years)">
              <input
                type="number"
                min={0}
                max={50}
                value={form.min_exp_years}
                onChange={(e) => setForm({ ...form, min_exp_years: e.target.value })}
              />
            </Field>
            <Field label="Max exp (years)">
              <input
                type="number"
                min={0}
                max={50}
                value={form.max_exp_years}
                onChange={(e) => setForm({ ...form, max_exp_years: e.target.value })}
              />
            </Field>
          </div>
          <div className="field-row">
            <Field label="CTC min (₹/yr)" hint="Blank = undisclosed">
              <input
                type="number"
                min={0}
                value={form.ctc_min}
                onChange={(e) => setForm({ ...form, ctc_min: e.target.value })}
              />
            </Field>
            <Field label="CTC max (₹/yr)">
              <input
                type="number"
                min={0}
                value={form.ctc_max}
                onChange={(e) => setForm({ ...form, ctc_max: e.target.value })}
              />
            </Field>
          </div>
        </Drawer>
      )}
    </>
  );
}
