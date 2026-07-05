import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { findMyJob } from "../../api/recruiterJobs";
import type { EmployerRead, JobCreate, RecruiterJobRow } from "../../api/types";
import { ErrorNotice, Field, lakh } from "../../components/bits";
import { useSession } from "../../session";
import {
  buildJobPayload,
  contentChanged,
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
 *                                    cold deep-link it's resolved by id, like the
 *                                    Flutter EditJobResolver).
 *
 * Backend-true semantics (api CLAUDE.md): editing a content field re-embeds the
 * job for matching; a status-only change does not. The edit PATCH carries only
 * changed fields (jobForm.buildJobPayload diffs), so a status-only save stays
 * status-only and the "re-embeds" hint (contentChanged) never lies.
 */

/** A blank-but-typed CTC field (e.g. "-5") parses to null = invalid; an empty
 *  field parses to undefined = simply omitted. The preview must distinguish them
 *  so an invalid entry isn't silently shown as "Undisclosed". */
function ctcIsInvalid(raw: string): boolean {
  return raw.trim() !== "" && parseCtc(raw) === null;
}

/** Lenient parse of the raw form for the preview only — never blocks typing.
 *  Parses each bound once. */
function previewBand(form: JobFormState): string {
  const min = parseCtc(form.ctc_min);
  const max = parseCtc(form.ctc_max);
  const lo = typeof min === "number" ? lakh(min) : null;
  const hi = typeof max === "number" ? lakh(max) : null;
  if (!lo && !hi) return "Undisclosed";
  return [lo, hi].filter(Boolean).join(" – ");
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
        const job = await findMyJob(client, jobId!);
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

  // Editing a content field re-embeds the job (status-only does not). Computed
  // off the same diff the PATCH sends, so the hint and the wire agree.
  const contentDirty = useMemo(
    () => (!isCreate && editJob ? contentChanged(form, editJob) : false),
    [isCreate, editJob, form],
  );

  // Invalid (non-blank, unparseable) CTC entry → flag it in the preview rather
  // than rendering it identically to a blank "Undisclosed".
  const ctcInvalid = ctcIsInvalid(form.ctc_min) || ctcIsInvalid(form.ctc_max);

  async function save() {
    // Edit diffs against editJob so a status-only change stays status-only.
    const built = buildJobPayload(form, isCreate, editJob ?? undefined);
    if ("error" in built) {
      setFormError(built.error);
      return;
    }
    // Edit that changed nothing — skip the round-trip, just return to the list.
    if ("noChange" in built) {
      navigate("/employers/jobs", { state: { status: form.status } });
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
      // Return to the list on the tab matching the saved status, so editing a
      // closed posting doesn't drop the recruiter back on the Open tab.
      navigate("/employers/jobs", { state: { status: form.status } });
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
        <Link to="/employers/jobs" className="jc-back">
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
              <span className="chip">{form.status}</span>
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
                // The job row carries no employer identity, so the real name is
                // only known when the recruiter belongs to exactly one employer;
                // otherwise show "—" rather than a guessed name in a field that
                // looks authoritative. Employer can't change after creation.
                <Field label="Employer" hint="Employer is fixed once a posting is created.">
                  <input value={employers.length === 1 ? employers[0].name : "—"} disabled />
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
              <Link to="/employers/jobs" className="btn ghost">
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
                  {ctcInvalid ? (
                    <span className="v num jc-invalid">Check CTC entry</span>
                  ) : (
                    <span className="v num">{previewBand(form)}</span>
                  )}
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
