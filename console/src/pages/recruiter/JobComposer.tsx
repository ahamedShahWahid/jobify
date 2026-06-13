import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { ConsoleClient } from "../../api/client";
import type { EmployerRead, JobCreate, RecruiterJobRow } from "../../api/types";
import { ErrorNotice, Field } from "../../components/bits";
import { useSession } from "../../session";
import {
  buildJobPayload,
  emptyForm,
  formFromJob,
  parseCtc,
  parseExp,
  parseLocations,
} from "./jobForm";
import type { JobFormState } from "./jobForm";

/**
 * Job composer — a full-page authoring surface for a posting, with a live
 * candidate-view preview. Reached from the Postings list:
 *   /recruiter/jobs/new            → create
 *   /recruiter/jobs/:jobId/edit    → edit (job passed via router state; on a
 *                                    cold deep-link it's resolved from the
 *                                    open+closed list by id, like the Flutter
 *                                    EditJobResolver).
 *
 * Backend-true semantics (api CLAUDE.md): editing a content field re-embeds the
 * job for matching; a status-only change does not. The composer always sends
 * status with the patch, so the per-field hint flags when a re-embed will fire.
 */

const lakh = (value: number | null | undefined): string | null => {
  if (value === null || value === undefined) return null;
  return `₹${(value / 100_000).toFixed(value % 100_000 === 0 ? 0 : 1)}L`;
};

// Drain bound — a recruiter's full posting list (mirrors Dashboard's drainJobs).
const MAX_PAGES = 50;

/** Find a posting by id across the recruiter's full list. The live backend's
 *  "closed" filter returns open+closed, but the demo client returns only the
 *  named status — so drain BOTH and stop at the first hit (correct for either).
 *  Only hit on a cold deep-link; normal edits pass the row via router state. */
async function resolveJob(client: ConsoleClient, jobId: string): Promise<RecruiterJobRow | null> {
  for (const status of ["open", "closed"] as const) {
    let cursor: string | undefined;
    for (let page = 0; page < MAX_PAGES; page++) {
      const res = await client.listMyJobs(status, cursor);
      const hit = res.items.find((j) => j.id === jobId);
      if (hit) return hit;
      if (!res.next_cursor) break;
      cursor = res.next_cursor;
    }
  }
  return null;
}

/** Lenient parse of the raw form for the preview only — never blocks typing. */
function previewBand(form: JobFormState): string {
  const min = lakh(typeof parseCtc(form.ctc_min) === "number" ? parseCtc(form.ctc_min)! : null);
  const max = lakh(typeof parseCtc(form.ctc_max) === "number" ? parseCtc(form.ctc_max)! : null);
  if (!min && !max) return "Undisclosed";
  return [min, max].filter(Boolean).join(" – ");
}

function previewExp(form: JobFormState): string {
  const min = parseExp(form.min_exp_years);
  const max = parseExp(form.max_exp_years);
  if (min === null && max === null) return "—";
  return `${min ?? "?"}–${max ?? "?"} yrs`;
}

export function JobComposer() {
  const { client } = useSession();
  const { jobId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const isCreate = !jobId;

  const stateJob = (location.state as { job?: RecruiterJobRow } | null)?.job ?? null;

  const [employers, setEmployers] = useState<EmployerRead[]>([]);
  const [form, setForm] = useState<JobFormState>(emptyForm(""));
  const [editJob, setEditJob] = useState<RecruiterJobRow | null>(stateJob);
  const [resolving, setResolving] = useState(!isCreate && stateJob === null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Load employers (for the create selector + the preview's company name/badge).
  useEffect(() => {
    client.myEmployers().then(setEmployers, () => undefined);
  }, [client]);

  // Seed the form: create → empty (employer filled once employers load); edit →
  // from the passed job, or resolve it by id on a cold deep-link.
  useEffect(() => {
    if (isCreate) return;
    if (stateJob) {
      setForm(formFromJob(stateJob));
      setEditJob(stateJob);
      setResolving(false);
      return;
    }
    let cancelled = false;
    setResolving(true);
    (async () => {
      try {
        const job = await resolveJob(client, jobId!);
        if (cancelled) return;
        if (!job) {
          setLoadError("That posting couldn't be found — it may have been deleted.");
        } else {
          setForm(formFromJob(job));
          setEditJob(job);
        }
      } catch (e) {
        if (!cancelled) setLoadError(errorMessage(e));
      } finally {
        if (!cancelled) setResolving(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, isCreate, jobId, stateJob]);

  // Default the employer selector to the first employer once loaded (create).
  useEffect(() => {
    if (isCreate && !form.employer_id && employers[0]) {
      setForm((f) => ({ ...f, employer_id: employers[0].id }));
    }
  }, [employers, isCreate, form.employer_id]);

  const update = useCallback(
    <K extends keyof JobFormState>(key: K, value: JobFormState[K]) =>
      setForm((f) => ({ ...f, [key]: value })),
    [],
  );

  // Preview company: create → the selected employer; edit → the recruiter's sole
  // employer if unambiguous, else a neutral label. Badge always reflects truth.
  const previewCompany = useMemo(() => {
    if (isCreate) {
      const sel = employers.find((e) => e.id === form.employer_id);
      return { name: sel?.name ?? "Your company", verified: sel?.verified_at != null };
    }
    const name = employers.length === 1 ? employers[0].name : "Your company";
    return { name, verified: editJob?.employer_verified ?? false };
  }, [isCreate, employers, form.employer_id, editJob]);

  // Editing any content field re-embeds the job (status-only does not).
  const contentDirty = useMemo(() => {
    if (isCreate || !editJob) return false;
    return (
      form.title.trim() !== editJob.title ||
      form.description.trim() !== editJob.description ||
      parseLocations(form.locations).join("|") !== editJob.locations.join("|") ||
      parseExp(form.min_exp_years) !== editJob.min_exp_years ||
      parseExp(form.max_exp_years) !== editJob.max_exp_years ||
      (parseCtc(form.ctc_min) ?? null) !== editJob.ctc_min ||
      (parseCtc(form.ctc_max) ?? null) !== editJob.ctc_max
    );
  }, [isCreate, editJob, form]);

  async function save() {
    const built = buildJobPayload(form, isCreate);
    if ("error" in built) {
      setFormError(built.error);
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (isCreate) {
        await client.createJob(built.payload as JobCreate);
      } else {
        await client.patchJob(jobId!, built.payload);
      }
      navigate("/recruiter/jobs");
    } catch (e) {
      setFormError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  const previewLocations = parseLocations(form.locations);
  const descLines = form.description.split("\n").filter((l) => l.trim().length > 0);

  if (resolving) {
    return (
      <div className="content">
        <div className="jc-resolving">Loading posting…</div>
      </div>
    );
  }

  return (
    <div className="content">
      <div className="jc-top rise">
        <Link to="/recruiter/jobs" className="jc-back">
          ← Postings
        </Link>
      </div>

      <div className="headline rise">
        <h1>
          {isCreate ? "NEW" : "EDIT"} <span className="ghost">POSTING</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            Write the role the way you&apos;d want to read it — the candidate&apos;s view is on the
            right, updating as you type.
          </span>
        </div>
      </div>

      {loadError ? (
        <ErrorNotice error={loadError} />
      ) : (
        <div className="jc-grid rise">
          {/* ---- authoring column ---- */}
          <div className="jc-form panel">
            <div className="panel-head">
              <span className="k">draft</span>
              <span className="chip acc">{form.status}</span>
            </div>
            <div className="panel-body">
              <ErrorNotice error={formError} />

              {isCreate ? (
                <Field label="Employer" hint="The team this posting belongs to.">
                  <select
                    value={form.employer_id}
                    onChange={(e) => update("employer_id", e.target.value)}
                  >
                    {employers.length === 0 && <option value="">No employers yet</option>}
                    {employers.map((employer) => (
                      <option key={employer.id} value={employer.id}>
                        {employer.name}
                        {employer.verified_at ? "" : " (unverified)"}
                      </option>
                    ))}
                  </select>
                </Field>
              ) : (
                <Field label="Employer">
                  <input value={previewCompany.name} disabled />
                </Field>
              )}

              <Field label="Title" hint="2–200 characters.">
                <input
                  value={form.title}
                  onChange={(e) => update("title", e.target.value)}
                  maxLength={200}
                  placeholder="e.g. Senior Backend Engineer"
                />
              </Field>

              <Field
                label="Description"
                hint={
                  !isCreate && contentDirty
                    ? "Edited — saving re-embeds this job for matching."
                    : "10–10,000 chars. Blank lines separate paragraphs in the preview."
                }
              >
                <textarea
                  value={form.description}
                  onChange={(e) => update("description", e.target.value)}
                  rows={9}
                  placeholder="What the team owns, who you're looking for, how you work…"
                />
              </Field>

              <Field label="Locations" hint="Comma-separated, e.g. Bengaluru, Remote (IN)">
                <input
                  value={form.locations}
                  onChange={(e) => update("locations", e.target.value)}
                  placeholder="Bengaluru, Remote (IN)"
                />
              </Field>

              <div className="field-row">
                <Field label="Min exp (years)">
                  <input
                    type="number"
                    min={0}
                    max={50}
                    value={form.min_exp_years}
                    onChange={(e) => update("min_exp_years", e.target.value)}
                  />
                </Field>
                <Field label="Max exp (years)">
                  <input
                    type="number"
                    min={0}
                    max={50}
                    value={form.max_exp_years}
                    onChange={(e) => update("max_exp_years", e.target.value)}
                  />
                </Field>
              </div>

              <div className="field-row">
                <Field label="CTC min (₹/yr)" hint="Blank = undisclosed">
                  <input
                    type="number"
                    min={0}
                    value={form.ctc_min}
                    onChange={(e) => update("ctc_min", e.target.value)}
                    placeholder="—"
                  />
                </Field>
                <Field label="CTC max (₹/yr)">
                  <input
                    type="number"
                    min={0}
                    value={form.ctc_max}
                    onChange={(e) => update("ctc_max", e.target.value)}
                    placeholder="—"
                  />
                </Field>
              </div>

              <Field label="Visibility" hint="Open postings surface in candidate feeds.">
                <div className="mode-tabs" style={{ width: 220 }}>
                  <button
                    type="button"
                    className={form.status === "open" ? "on" : ""}
                    onClick={() => update("status", "open")}
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    className={form.status === "closed" ? "on" : ""}
                    onClick={() => update("status", "closed")}
                  >
                    Closed
                  </button>
                </div>
              </Field>
            </div>
            <div className="jc-foot">
              <Link to="/recruiter/jobs" className="btn ghost">
                Cancel
              </Link>
              <button className="btn primary" onClick={() => void save()} disabled={saving}>
                {saving ? "Saving…" : isCreate ? "Publish posting" : "Save changes"}
              </button>
            </div>
          </div>

          {/* ---- live candidate preview ---- */}
          <div className="jc-preview-col">
            <div className="jc-preview-label">
              <span className="dot" /> What the candidate sees
            </div>
            <article className="jc-card">
              <div className="jc-card-top">
                <span className={`jc-status ${form.status}`}>
                  {form.status === "open" ? "Open role" : "Closed"}
                </span>
                <span className={`jc-badge${previewCompany.verified ? " ok" : ""}`}>
                  {previewCompany.verified ? "✓ Verified employer" : "Unverified"}
                </span>
              </div>
              <div className="jc-company">{previewCompany.name}</div>
              <h2 className="jc-title">{form.title.trim() || "Your role title"}</h2>

              <div className="jc-facts">
                <div className="jc-fact">
                  <span className="k">Compensation</span>
                  <span className="v num">{previewBand(form)}</span>
                </div>
                <div className="jc-fact">
                  <span className="k">Experience</span>
                  <span className="v num">{previewExp(form)}</span>
                </div>
                <div className="jc-fact">
                  <span className="k">Location</span>
                  <span className="v">
                    {previewLocations.length ? previewLocations.join(" · ") : "—"}
                  </span>
                </div>
              </div>

              {previewLocations.length > 0 && (
                <div className="jc-chips">
                  {previewLocations.map((loc, i) => (
                    <span key={`${loc}-${i}`} className="jc-chip">
                      {loc}
                    </span>
                  ))}
                </div>
              )}

              <div className="jc-desc">
                {descLines.length > 0 ? (
                  descLines.map((line, i) => <p key={i}>{line}</p>)
                ) : (
                  <p className="jc-placeholder">
                    Your description will appear here as the candidate reads it.
                  </p>
                )}
              </div>
            </article>
            <p className="jc-preview-note">
              Preview only — match scores and the &ldquo;why this fits&rdquo; line are generated
              after you publish and the role is embedded.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
