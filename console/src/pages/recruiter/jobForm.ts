import type { JobCreate, JobPatch, RecruiterJobRow } from "../../api/types";

/**
 * Shared job-form state + validation for the recruiter composer (and any other
 * surface that authors a posting). Mirrors the backend's JobCreate constraints
 * and the _ordered_bands model validator (api/src/jobify/routes/jobs.py) so the
 * operator sees plain messages instead of a raw 422 list, and a blank exp field
 * reads as "missing" rather than silently coercing to 0 (which a PATCH would
 * otherwise write over a real value).
 */
export interface JobFormState {
  employer_id: string;
  title: string;
  description: string;
  locations: string;
  min_exp_years: string;
  max_exp_years: string;
  ctc_min: string;
  ctc_max: string;
  status: "open" | "closed";
}

export const emptyForm = (employerId: string): JobFormState => ({
  employer_id: employerId,
  title: "",
  description: "",
  locations: "",
  min_exp_years: "0",
  max_exp_years: "5",
  ctc_min: "",
  ctc_max: "",
  status: "open",
});

/** Hydrate the form from an existing posting for the edit flow. */
export const formFromJob = (job: RecruiterJobRow): JobFormState => ({
  employer_id: "",
  title: job.title,
  description: job.description,
  locations: job.locations.join(", "),
  min_exp_years: String(job.min_exp_years),
  max_exp_years: String(job.max_exp_years),
  ctc_min: job.ctc_min === null ? "" : String(job.ctc_min),
  ctc_max: job.ctc_max === null ? "" : String(job.ctc_max),
  status: job.status === "closed" ? "closed" : "open",
});

/** Whole number in [0,50] or null if the field is blank/non-integer (NOT 0). */
export function parseExp(raw: string): number | null {
  if (raw.trim() === "") return null;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 0 && n <= 50 ? n : null;
}

/** undefined = blank (send null) · null = invalid · number = a valid CTC ≥ 0. */
export function parseCtc(raw: string): number | null | undefined {
  if (raw.trim() === "") return undefined;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/** Split + trim the comma-separated locations field into a clean list. */
export function parseLocations(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Validate + build the create/patch payload. Returns either { payload } or a
 * single human { error } string. `status` is always included for create (the
 * backend defaults open, but the composer lets you publish closed); for patch
 * it's included too so a status flip rides the same save.
 */
export function buildJobPayload(
  form: JobFormState,
  isCreate: boolean,
): { payload: JobCreate | JobPatch } | { error: string } {
  const title = form.title.trim();
  if (title.length < 2 || title.length > 200) return { error: "Title must be 2–200 characters." };

  const description = form.description.trim();
  if (description.length < 10 || description.length > 10_000)
    return { error: "Description must be 10–10,000 characters." };

  const locations = parseLocations(form.locations);
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
    status: form.status,
  };
  if (isCreate) {
    if (!form.employer_id) return { error: "Choose an employer." };
    return { payload: { ...base, employer_id: form.employer_id } };
  }
  return { payload: base };
}
