# Split recruiter ops out of `/console` into `/employers` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/console` strictly jobify-internal (admin-only), give recruiters their own authenticated workspace under `/employers` (dashboard, job CRUD, applicants, team/invites, settings — with a demo mode), update the marketing CTAs that used to point at "the console", and make console's remaining routes remountable at a bare subdomain later with no code changes.

**Architecture:** `console/` and `employers/` each become a fully independent per-surface module: own `api/{client,types,demo}.ts`, own `session.tsx`, own `components/{Shell,bits}.tsx`, own CSS file — mirroring the existing per-surface pattern in this codebase (each surface already has its own `SessionProvider`; this extends that independence to the API layer). Five recruiter pages move from `console/pages/recruiter/*` to `employers/pages/dashboard/*` verbatim except for internal route-string updates. Console's remaining routes are built from a `CONSOLE_BASE` constant instead of hardcoded `/console/...` strings, so serving console from its own subdomain later is a one-line constant change, not a route-tree rewrite.

**Tech Stack:** React 18, react-router-dom v6 (HashRouter), TypeScript, Vite. No new dependencies.

## Global Constraints

- `npm run build` (`tsc -b && vite build`, from `frontend/`) must stay clean after every task — this is the project's only CI-equivalent check for this package (per root `CLAUDE.md`: `frontend/README.md` documents `npm run build` as the sole build/typecheck command; there is no ESLint config in this repo).
- No backend changes — every recruiter/admin method already exists on `/v1/jobs*`, `/v1/employers*`, `/v1/admin*` and is role-gated server-side regardless of which frontend surface calls it.
- No changes to the Flutter app (`app/`).
- Per `frontend/CLAUDE.md`: each surface keeps its own independent `SessionProvider`; per-surface CSS is scoped under that surface's wrapper class; design tokens (`shared/styles/tokens.css`) are never redefined per-surface.
- Preserve all seeded demo-data values (uuids' generation scheme, seed content, timestamps-relative-to-now helpers) verbatim when moving/splitting `demo.ts` — these are fixtures, not behavior, and changing them isn't part of this task.
- Follow the existing repo convention of NOT writing multi-line doc comments — one-line comments only where the *why* isn't obvious from the code.

---

## Task 1: Split `api/types.ts` into console (admin) and employers (recruiter) type files

**Files:**
- Create: `frontend/src/sites/employers/api/types.ts`
- Modify: `frontend/src/sites/console/api/types.ts`

**Interfaces:**
- Produces: `employers/api/types.ts` exports `MeResponse`, `JobRead`, `RecruiterJobRow`, `RecruiterJobsPage`, `JobCreate`, `JobPatch`, `ApplicantOfJobRow`, `ApplicantsOfJobPage`, `EmployerRead`, `MemberRead`, `InviteRead` — all later tasks importing recruiter types use these exact names.
- Produces: `console/api/types.ts` (trimmed) keeps exporting `MeResponse`, `AdminUserRead`, `AuditLogRead`, `AuditLogListResponse`, `AuditLogFilters`, `EmployerVerificationStatus`, `EmployerVerificationRow`, `EmployerVerificationPage`.

- [ ] **Step 1: Create `frontend/src/sites/employers/api/types.ts`**

```ts
/**
 * Wire types mirroring the FastAPI Pydantic response models verbatim.
 * Source of truth: api/src/jobify_api/routes/{jobs,employers,me}.py.
 * Decimal fields (ctc_*) serialize as JSON numbers (schemas declare float).
 */

// ---- /v1/me ----------------------------------------------------

export interface MeResponse {
  id: string;
  email: string | null;
  role: string; // "applicant" | "recruiter" | "admin"
  applicant: unknown | null;
}

// ---- /v1/jobs (recruiter) --------------------------------------

export interface JobRead {
  id: string;
  title: string;
  description: string;
  locations: string[];
  min_exp_years: number;
  max_exp_years: number;
  ctc_min: number | null;
  ctc_max: number | null;
  status: string; // "open" | "closed"
  posted_at: string;
  employer_verified: boolean;
}

export interface RecruiterJobRow extends JobRead {
  applicant_count: number;
  surfaced_match_count: number;
}

export interface RecruiterJobsPage {
  items: RecruiterJobRow[];
  next_cursor: string | null;
}

export interface JobCreate {
  employer_id: string;
  title: string;
  description: string;
  locations: string[];
  min_exp_years: number;
  max_exp_years: number;
  ctc_min?: number | null;
  ctc_max?: number | null;
  status?: "open" | "closed";
}

export interface JobPatch {
  title?: string;
  description?: string;
  locations?: string[];
  min_exp_years?: number;
  max_exp_years?: number;
  ctc_min?: number | null;
  ctc_max?: number | null;
  status?: "open" | "closed";
}

export interface ApplicantOfJobRow {
  application_id: string;
  applicant_id: string;
  display_name: string | null;
  email: string | null;
  status: string;
  applied_at: string;
  match_score: number | null;
  match_explanation: Record<string, string> | null;
}

export interface ApplicantsOfJobPage {
  items: ApplicantOfJobRow[];
  next_cursor: string | null;
}

// ---- /v1/employers ---------------------------------------------

export interface EmployerRead {
  id: string;
  name: string;
  gst: string | null;
  verified_at: string | null;
  created_at: string;
}

export interface MemberRead {
  user_id: string;
  email: string | null;
  display_name: string | null;
  role: string; // "owner" | "member"
  added_at: string;
}

export interface InviteRead {
  id: string;
  employer_id: string;
  email: string;
  role: string;
  status: string; // "pending" | "accepted" | "revoked" | "expired"
  expires_at: string;
  created_at: string;
  invited_by_user_id: string | null;
}
```

- [ ] **Step 2: Trim `frontend/src/sites/console/api/types.ts` to admin-only types**

Replace the entire file with:

```ts
/**
 * Wire types mirroring the FastAPI Pydantic response models verbatim.
 * Source of truth: api/src/jobify_api/routes/{admin,me}.py.
 */

// ---- /v1/me ----------------------------------------------------

export interface MeResponse {
  id: string;
  email: string | null;
  role: string; // "applicant" | "recruiter" | "admin"
  applicant: unknown | null;
}

// ---- /v1/admin -------------------------------------------------

export interface AdminUserRead {
  id: string;
  email: string | null;
  role: string;
  suspended_at: string | null;
  suspension_reason: string | null;
}

export interface AuditLogRead {
  id: string;
  actor_user_id: string | null;
  actor_role: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  context: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogRead[];
  next_cursor: string | null;
}

export interface AuditLogFilters {
  actor_user_id?: string;
  resource_type?: string;
  resource_id?: string;
  action?: string;
  from?: string; // ISO datetime
  to?: string;
  cursor?: string;
  limit?: number;
}

// ---- /v1/admin/employers (PROPOSED — see client.ts) ------------
//
// No backend endpoint exists for an employer verification queue yet (admin has
// only audit-logs + suspend/unsuspend today). These types model the contract the
// console *would* consume once the backend exposes it; in live mode the calls
// 404. The DemoClient implements them fully against seeded data.

export type EmployerVerificationStatus = "pending" | "verified" | "rejected";

export interface EmployerVerificationRow {
  id: string;
  name: string;
  gst: string | null;
  status: EmployerVerificationStatus;
  created_at: string;
  reviewed_at: string | null; // derived: verified_at or rejected_at, whichever is set
  reason: string | null; // rejection_reason, only set while rejected
  // Demo-only enrichment. The real GET /v1/admin/employers response omits these —
  // employers don't collect domain/contact today, and reviewer history lives in
  // audit_logs (admin.employer.verified / .rejected), not a column.
  domain?: string | null;
  contact_email?: string | null;
  reviewer?: string | null;
}

export interface EmployerVerificationPage {
  items: EmployerVerificationRow[];
  next_cursor: string | null;
}
```

- [ ] **Step 3: Verify TypeScript picks up both files (errors expected until later tasks fix consumers)**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -60`
Expected: errors referencing missing exports (`RecruiterJobRow`, `EmployerRead`, etc.) from `console/api/types` in `console/api/client.ts`, `console/api/demo.ts`, and `console/pages/recruiter/*` — this is expected; those consumers are fixed/moved in later tasks. Confirm there are NO errors about `employers/api/types.ts` itself (it should compile standalone with zero errors).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/employers/api/types.ts frontend/src/sites/console/api/types.ts
git commit -m "$(cat <<'EOF'
refactor(frontend): split console/api/types.ts into console (admin) + employers (recruiter)

Part of moving recruiter ops out of /console into /employers — console
should only ever need admin-shaped types once the recruiter pages move.
EOF
)"
```

---

## Task 2: Split `api/client.ts` into `ConsoleClient` (admin) and `EmployerClient` (recruiter)

**Files:**
- Create: `frontend/src/sites/employers/api/client.ts`
- Modify: `frontend/src/sites/console/api/client.ts`

**Interfaces:**
- Consumes: `employers/api/types.ts` and `console/api/types.ts` from Task 1; `BaseHttpClient`, `ApiError`, `errorMessage`, `TokenStore` from `shared/api/transport.ts` (unchanged).
- Produces: `employers/api/client.ts` exports `EmployerClient` (interface) and `HttpClient` (class implementing it) — Task 3/4/8 depend on this exact interface name and method signatures.
- Produces: `console/api/client.ts` (trimmed) keeps exporting `ConsoleClient` and `HttpClient` with only `me()` + the 6 admin methods.

- [ ] **Step 1: Create `frontend/src/sites/employers/api/client.ts`**

```ts
import { BaseHttpClient } from "../../../shared/api/transport";
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";

import type {
  ApplicantsOfJobPage,
  EmployerRead,
  InviteRead,
  JobCreate,
  JobPatch,
  JobRead,
  MeResponse,
  MemberRead,
  RecruiterJobsPage,
} from "./types";

/** One interface, two impls: HttpClient (live API) and DemoClient (fixtures). */
export interface EmployerClient {
  readonly mode: "live" | "demo";

  me(): Promise<MeResponse>;

  listMyJobs(status: "open" | "closed", cursor?: string): Promise<RecruiterJobsPage>;
  createJob(payload: JobCreate): Promise<JobRead>;
  patchJob(jobId: string, payload: JobPatch): Promise<JobRead>;
  deleteJob(jobId: string): Promise<void>;
  listJobApplicants(jobId: string, cursor?: string): Promise<ApplicantsOfJobPage>;

  myEmployers(): Promise<EmployerRead[]>;
  listMembers(employerId: string): Promise<MemberRead[]>;
  addMember(employerId: string, email: string, role: "owner" | "member"): Promise<MemberRead>;
  changeMemberRole(
    employerId: string,
    memberUserId: string,
    role: "owner" | "member",
  ): Promise<MemberRead>;
  removeMember(employerId: string, memberUserId: string): Promise<void>;
  listInvites(employerId: string): Promise<InviteRead[]>;
  createInvite(employerId: string, email: string, role: "owner" | "member"): Promise<InviteRead>;
  revokeInvite(employerId: string, inviteId: string): Promise<void>;
}

export class HttpClient extends BaseHttpClient implements EmployerClient {
  me(): Promise<MeResponse> {
    return this.request("GET", "/v1/me");
  }

  listMyJobs(status: "open" | "closed", cursor?: string): Promise<RecruiterJobsPage> {
    const params = new URLSearchParams({ status });
    if (cursor) params.set("cursor", cursor);
    return this.request("GET", `/v1/jobs/me?${params}`);
  }

  createJob(payload: JobCreate): Promise<JobRead> {
    return this.request("POST", "/v1/jobs", payload);
  }

  patchJob(jobId: string, payload: JobPatch): Promise<JobRead> {
    return this.request("PATCH", `/v1/jobs/${jobId}`, payload);
  }

  deleteJob(jobId: string): Promise<void> {
    return this.request("DELETE", `/v1/jobs/${jobId}`);
  }

  listJobApplicants(jobId: string, cursor?: string): Promise<ApplicantsOfJobPage> {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request("GET", `/v1/jobs/${jobId}/applicants${qs}`);
  }

  myEmployers(): Promise<EmployerRead[]> {
    return this.request("GET", "/v1/employers/me");
  }

  listMembers(employerId: string): Promise<MemberRead[]> {
    return this.request("GET", `/v1/employers/${employerId}/members`);
  }

  addMember(employerId: string, email: string, role: "owner" | "member"): Promise<MemberRead> {
    return this.request("POST", `/v1/employers/${employerId}/members`, { email, role });
  }

  changeMemberRole(
    employerId: string,
    memberUserId: string,
    role: "owner" | "member",
  ): Promise<MemberRead> {
    return this.request("PATCH", `/v1/employers/${employerId}/members/${memberUserId}`, { role });
  }

  removeMember(employerId: string, memberUserId: string): Promise<void> {
    return this.request("DELETE", `/v1/employers/${employerId}/members/${memberUserId}`);
  }

  listInvites(employerId: string): Promise<InviteRead[]> {
    return this.request("GET", `/v1/employers/${employerId}/invites`);
  }

  createInvite(employerId: string, email: string, role: "owner" | "member"): Promise<InviteRead> {
    return this.request("POST", `/v1/employers/${employerId}/invites`, { email, role });
  }

  revokeInvite(employerId: string, inviteId: string): Promise<void> {
    return this.request("DELETE", `/v1/employers/${employerId}/invites/${inviteId}`);
  }
}
```

- [ ] **Step 2: Trim `frontend/src/sites/console/api/client.ts` to admin-only**

Replace the entire file with:

```ts
import { BaseHttpClient } from "../../../shared/api/transport";
export { ApiError, errorMessage, TokenStore } from "../../../shared/api/transport";

import type {
  AdminUserRead,
  AuditLogFilters,
  AuditLogListResponse,
  EmployerVerificationPage,
  EmployerVerificationRow,
  EmployerVerificationStatus,
  MeResponse,
} from "./types";

/** One interface, two impls: HttpClient (live API) and DemoClient (fixtures). */
export interface ConsoleClient {
  readonly mode: "live" | "demo";

  me(): Promise<MeResponse>;

  listAuditLogs(filters: AuditLogFilters): Promise<AuditLogListResponse>;
  suspendUser(userId: string, reason: string): Promise<AdminUserRead>;
  unsuspendUser(userId: string): Promise<AdminUserRead>;

  // Employer verification review (admin) — GET /v1/admin/employers (status filter
  // + cursor), POST .../{id}/verify, POST .../{id}/reject {reason}. The live
  // response is AdminEmployerRead {id,name,gst,status,created_at,reviewed_at,reason};
  // the demo-only domain/contact_email/reviewer fields are absent here.
  listEmployersForVerification(
    status: EmployerVerificationStatus,
    cursor?: string,
  ): Promise<EmployerVerificationPage>;
  verifyEmployer(employerId: string): Promise<EmployerVerificationRow>;
  rejectEmployer(employerId: string, reason: string): Promise<EmployerVerificationRow>;
}

export class HttpClient extends BaseHttpClient implements ConsoleClient {
  me(): Promise<MeResponse> {
    return this.request("GET", "/v1/me");
  }

  listAuditLogs(filters: AuditLogFilters): Promise<AuditLogListResponse> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    return this.request("GET", `/v1/admin/audit-logs${qs ? `?${qs}` : ""}`);
  }

  suspendUser(userId: string, reason: string): Promise<AdminUserRead> {
    return this.request("POST", `/v1/admin/users/${userId}/suspend`, { reason });
  }

  unsuspendUser(userId: string): Promise<AdminUserRead> {
    return this.request("DELETE", `/v1/admin/users/${userId}/suspend`);
  }

  listEmployersForVerification(
    status: EmployerVerificationStatus,
    cursor?: string,
  ): Promise<EmployerVerificationPage> {
    const params = new URLSearchParams({ status });
    if (cursor) params.set("cursor", cursor);
    return this.request("GET", `/v1/admin/employers?${params}`);
  }

  verifyEmployer(employerId: string): Promise<EmployerVerificationRow> {
    return this.request("POST", `/v1/admin/employers/${employerId}/verify`);
  }

  rejectEmployer(employerId: string, reason: string): Promise<EmployerVerificationRow> {
    return this.request("POST", `/v1/admin/employers/${employerId}/reject`, { reason });
  }
}
```

- [ ] **Step 3: Verify (errors expected until demo.ts and pages are fixed/moved)**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -60`
Expected: errors in `console/api/demo.ts` (still implements the old, larger `ConsoleClient`) and `console/pages/recruiter/*`/`console/api/recruiterJobs.ts` (still import recruiter methods from `console/api/client`). No errors expected in `employers/api/client.ts` itself.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/employers/api/client.ts frontend/src/sites/console/api/client.ts
git commit -m "$(cat <<'EOF'
refactor(frontend): split ConsoleClient into admin-only + new EmployerClient

Console keeps me() + the 6 admin methods; every recruiter method (jobs,
applicants, employers, members, invites) moves to the new EmployerClient.
EOF
)"
```

---

## Task 3: Split `api/demo.ts` into console (admin fixtures) and employers (recruiter fixtures)

**Files:**
- Create: `frontend/src/sites/employers/api/demo.ts`
- Modify: `frontend/src/sites/console/api/demo.ts`

**Interfaces:**
- Consumes: `EmployerClient`/`ConsoleClient` from Task 2, types from Task 1.
- Produces: `employers/api/demo.ts` exports `DemoClient` (implements `EmployerClient`, no constructor arg — `me()` always returns `role: "recruiter"`).
- Produces: `console/api/demo.ts` (trimmed) exports `DemoClient` (implements `ConsoleClient`, no constructor arg — `me()` always returns `role: "admin"`). The `DemoRole` type is removed entirely from both — each demo client only ever represents one role now.

Note: while auditing the original file, the `employers` seed array (2 rows: Meridian Analytics, Karkhana Robotics) turned out to be used only by `jobs`/`members`/`invites` (recruiter fixtures) — the `verificationQueue` builds its own independent rows via `mkVerification` and never references it. So `employers` moves to `employers/api/demo.ts` in full, not partially, unlike what the design spec assumed.

- [ ] **Step 1: Create `frontend/src/sites/employers/api/demo.ts`**

```ts
import type { EmployerClient } from "./client";
import { ApiError } from "./client";
import type {
  ApplicantOfJobRow,
  ApplicantsOfJobPage,
  EmployerRead,
  InviteRead,
  JobCreate,
  JobPatch,
  JobRead,
  MeResponse,
  MemberRead,
  RecruiterJobRow,
  RecruiterJobsPage,
} from "./types";

/** Seeded in-memory backend so the employer workspace is fully explorable offline. */

const uuid = (() => {
  let n = 0;
  return () => {
    n += 1;
    const hex = n.toString(16).padStart(12, "0");
    return `00000000-0000-4000-8000-${hex}`;
  };
})();

const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
const daysAgo = (d: number) => hoursAgo(d * 24);

const delay = () => new Promise((resolve) => setTimeout(resolve, 220 + Math.random() * 260));

// ---- seed state -------------------------------------------------

const ME_ID = uuid();

const employers: EmployerRead[] = [
  {
    id: uuid(),
    name: "Meridian Analytics",
    gst: "29ABCDE1234F1Z5",
    verified_at: daysAgo(41),
    created_at: daysAgo(60),
  },
  {
    id: uuid(),
    name: "Karkhana Robotics",
    gst: null,
    verified_at: null,
    created_at: daysAgo(12),
  },
];

interface DemoJob extends RecruiterJobRow {
  deleted: boolean;
  employer_id: string;
}

const mkJob = (
  employerIdx: number,
  title: string,
  status: "open" | "closed",
  postedDaysAgo: number,
  applicants: number,
  surfaced: number,
  ctc: [number, number] | null,
  exp: [number, number],
  locations: string[],
  description: string,
): DemoJob => ({
  id: uuid(),
  employer_id: employers[employerIdx].id,
  title,
  description,
  locations,
  min_exp_years: exp[0],
  max_exp_years: exp[1],
  ctc_min: ctc?.[0] ?? null,
  ctc_max: ctc?.[1] ?? null,
  status,
  posted_at: daysAgo(postedDaysAgo),
  employer_verified: employers[employerIdx].verified_at !== null,
  applicant_count: applicants,
  surfaced_match_count: surfaced,
  deleted: false,
});

const jobs: DemoJob[] = [
  mkJob(
    0,
    "Senior Data Platform Engineer",
    "open",
    3,
    14,
    61,
    [3200000, 4500000],
    [5, 9],
    ["Bengaluru", "Remote (IN)"],
    "Own the lakehouse: Spark + Iceberg pipelines feeding every score we ship. You will inherit a small, sharp platform and a long queue of ideas.",
  ),
  mkJob(
    0,
    "Machine Learning Engineer — Matching",
    "open",
    7,
    22,
    88,
    [2800000, 4000000],
    [3, 7],
    ["Bengaluru"],
    "Embeddings, ranking, and the explanation layer between them. pgvector in production, Gemini at the edges, taste everywhere.",
  ),
  mkJob(
    0,
    "Product Designer, Growth",
    "open",
    11,
    9,
    37,
    [1800000, 2600000],
    [2, 6],
    ["Mumbai", "Hybrid"],
    "Design the surfaces applicants meet first. You sweat empty states, onboarding, and the moment a match explains itself.",
  ),
  mkJob(
    0,
    "Backend Engineer (FastAPI)",
    "closed",
    34,
    41,
    120,
    [2200000, 3200000],
    [2, 5],
    ["Bengaluru"],
    "Async SQLAlchemy, Celery workers, and an audit trail you can stand behind. Filled — keeping the posting for the archive.",
  ),
  mkJob(
    1,
    "Embedded Firmware Engineer",
    "open",
    2,
    5,
    19,
    [1600000, 2400000],
    [1, 4],
    ["Pune"],
    "Bring up motor controllers and write the C that keeps six-axis arms honest. Bench time guaranteed.",
  ),
  mkJob(
    1,
    "Field Applications Intern",
    "closed",
    19,
    17,
    44,
    null,
    [0, 1],
    ["Pune", "On-site"],
    "Six-month internship across deployments. Closed for this cohort.",
  ),
];

interface DemoApplicant extends ApplicantOfJobRow {
  job_id: string;
}

const firstNames = [
  "Aarav",
  "Diya",
  "Ishaan",
  "Meera",
  "Kabir",
  "Anaya",
  "Vihaan",
  "Sara",
  "Reyansh",
  "Zoya",
  "Arjun",
  "Naina",
  "Dev",
  "Tara",
];
const lastNames = [
  "Sharma",
  "Iyer",
  "Khan",
  "Patel",
  "Reddy",
  "Das",
  "Menon",
  "Bose",
  "Kulkarni",
  "Nair",
];

const applicants: DemoApplicant[] = [];
jobs.forEach((job, jobIdx) => {
  const count = Math.min(job.applicant_count, 14);
  for (let i = 0; i < count; i++) {
    const name = `${firstNames[(jobIdx * 5 + i * 3) % firstNames.length]} ${
      lastNames[(jobIdx * 7 + i) % lastNames.length]
    }`;
    const score = Math.round((0.93 - i * 0.045 - jobIdx * 0.01) * 100) / 100;
    applicants.push({
      job_id: job.id,
      application_id: uuid(),
      applicant_id: uuid(),
      display_name: name,
      email: `${name.toLowerCase().replace(" ", ".")}@example.in`,
      status: i % 9 === 7 ? "withdrawn" : "applied",
      applied_at: hoursAgo(4 + i * 9 + jobIdx * 3),
      match_score: score > 0.3 ? score : null,
      match_explanation:
        score > 0.55
          ? {
              fit: `Strong overlap on ${job.title.split(" ")[0].toLowerCase()} fundamentals and ${
                job.locations[0]
              } availability.`,
              caveat:
                i % 3 === 0
                  ? "Compensation expectation sits at the top of the band."
                  : "Notice period is 60 days.",
            }
          : null,
    });
  }
});

const members = new Map<string, MemberRead[]>([
  [
    employers[0].id,
    [
      {
        user_id: ME_ID,
        email: "recruiter@meridian.in",
        display_name: "You",
        role: "owner",
        added_at: daysAgo(60),
      },
      {
        user_id: uuid(),
        email: "priya.k@meridian.in",
        display_name: "Priya Krishnan",
        role: "owner",
        added_at: daysAgo(44),
      },
      {
        user_id: uuid(),
        email: "rahul.t@meridian.in",
        display_name: "Rahul Thakur",
        role: "member",
        added_at: daysAgo(20),
      },
    ],
  ],
  [
    employers[1].id,
    [
      {
        user_id: ME_ID,
        email: "recruiter@meridian.in",
        display_name: "You",
        role: "owner",
        added_at: daysAgo(12),
      },
    ],
  ],
]);

const invites = new Map<string, InviteRead[]>([
  [
    employers[0].id,
    [
      {
        id: uuid(),
        employer_id: employers[0].id,
        email: "anita.d@meridian.in",
        role: "member",
        status: "pending",
        expires_at: hoursAgo(-96),
        created_at: hoursAgo(30),
        invited_by_user_id: ME_ID,
      },
      {
        id: uuid(),
        employer_id: employers[0].id,
        email: "former.lead@meridian.in",
        role: "owner",
        status: "revoked",
        expires_at: daysAgo(-3),
        created_at: daysAgo(9),
        invited_by_user_id: ME_ID,
      },
    ],
  ],
  [employers[1].id, []],
]);

// Mirror the backend JobCreate/JobPatch validation so demo mode rejects the same
// payloads the real API would (otherwise demo silently accepts invalid data and
// hides a missing client-side guard). Only validates fields that are present.
function assertJobConstraints(p: {
  title?: string;
  description?: string;
  locations?: string[];
  min_exp_years?: number;
  max_exp_years?: number;
  ctc_min?: number | null;
  ctc_max?: number | null;
}): void {
  if (p.title !== undefined && (p.title.length < 2 || p.title.length > 200))
    throw new ApiError(422, "title: must be 2–200 characters");
  if (p.description !== undefined && (p.description.length < 10 || p.description.length > 10_000))
    throw new ApiError(422, "description: must be 10–10,000 characters");
  if (p.locations !== undefined && (p.locations.length < 1 || p.locations.length > 20))
    throw new ApiError(422, "locations: must have 1–20 entries");
  if (
    p.min_exp_years !== undefined &&
    p.max_exp_years !== undefined &&
    p.max_exp_years < p.min_exp_years
  )
    throw new ApiError(422, "max_exp_years must be >= min_exp_years");
  if (p.ctc_min != null && p.ctc_max != null && p.ctc_max < p.ctc_min)
    throw new ApiError(422, "ctc_max must be >= ctc_min");
}

// ---- the client -------------------------------------------------

export class DemoClient implements EmployerClient {
  readonly mode = "demo" as const;

  async me(): Promise<MeResponse> {
    await delay();
    return { id: ME_ID, email: "recruiter@meridian.in", role: "recruiter", applicant: null };
  }

  async listMyJobs(status: "open" | "closed", cursor?: string): Promise<RecruiterJobsPage> {
    await delay();
    const rows = jobs
      .filter((job) => !job.deleted && job.status === status)
      .sort((a, b) => b.posted_at.localeCompare(a.posted_at));
    const start = cursor ? Number(cursor) : 0;
    const limit = 20;
    return {
      items: rows.slice(start, start + limit).map(({ deleted: _d, employer_id: _e, ...row }) => row),
      next_cursor: start + limit < rows.length ? String(start + limit) : null,
    };
  }

  async createJob(payload: JobCreate): Promise<JobRead> {
    await delay();
    assertJobConstraints(payload);
    const employer = employers.find((e) => e.id === payload.employer_id);
    if (!employer) throw new ApiError(404, "employer not found");
    const job: DemoJob = {
      id: uuid(),
      employer_id: employer.id,
      title: payload.title,
      description: payload.description,
      locations: payload.locations,
      min_exp_years: payload.min_exp_years,
      max_exp_years: payload.max_exp_years,
      ctc_min: payload.ctc_min ?? null,
      ctc_max: payload.ctc_max ?? null,
      status: payload.status ?? "open",
      posted_at: new Date().toISOString(),
      employer_verified: employer.verified_at !== null,
      applicant_count: 0,
      surfaced_match_count: 0,
      deleted: false,
    };
    jobs.unshift(job);
    const { deleted: _d, employer_id: _e, applicant_count: _a, surfaced_match_count: _s, ...read } = job;
    return read;
  }

  async patchJob(jobId: string, payload: JobPatch): Promise<JobRead> {
    await delay();
    const job = jobs.find((j) => j.id === jobId && !j.deleted);
    if (!job) throw new ApiError(404, "job not found");
    // Validate the merged result so a partial PATCH can't break a cross-field rule.
    assertJobConstraints({ ...job, ...payload });
    Object.assign(job, Object.fromEntries(Object.entries(payload).filter(([, v]) => v !== undefined)));
    const { deleted: _d, employer_id: _e, applicant_count: _a, surfaced_match_count: _s, ...read } = job;
    return read;
  }

  async deleteJob(jobId: string): Promise<void> {
    await delay();
    const job = jobs.find((j) => j.id === jobId && !j.deleted);
    if (!job) throw new ApiError(404, "job not found");
    job.deleted = true;
  }

  async listJobApplicants(jobId: string, cursor?: string): Promise<ApplicantsOfJobPage> {
    await delay();
    const rows = applicants
      .filter((a) => a.job_id === jobId)
      .sort((a, b) => b.applied_at.localeCompare(a.applied_at));
    const start = cursor ? Number(cursor) : 0;
    const limit = 10;
    return {
      items: rows.slice(start, start + limit).map(({ job_id: _j, ...row }) => row),
      next_cursor: start + limit < rows.length ? String(start + limit) : null,
    };
  }

  async myEmployers(): Promise<EmployerRead[]> {
    await delay();
    return employers;
  }

  async listMembers(employerId: string): Promise<MemberRead[]> {
    await delay();
    return members.get(employerId) ?? [];
  }

  async addMember(
    employerId: string,
    email: string,
    role: "owner" | "member",
  ): Promise<MemberRead> {
    await delay();
    const roster = members.get(employerId);
    if (!roster) throw new ApiError(404, "employer not found");
    if (roster.some((m) => m.email === email)) throw new ApiError(409, "already_a_member");
    const member: MemberRead = {
      user_id: uuid(),
      email,
      display_name: null,
      role,
      added_at: new Date().toISOString(),
    };
    roster.push(member);
    return member;
  }

  async changeMemberRole(
    employerId: string,
    memberUserId: string,
    role: "owner" | "member",
  ): Promise<MemberRead> {
    await delay();
    const roster = members.get(employerId) ?? [];
    const member = roster.find((m) => m.user_id === memberUserId);
    if (!member) throw new ApiError(404, "member not found");
    const owners = roster.filter((m) => m.role === "owner");
    if (member.role === "owner" && role === "member" && owners.length <= 1) {
      throw new ApiError(409, "last_owner");
    }
    member.role = role;
    return member;
  }

  async removeMember(employerId: string, memberUserId: string): Promise<void> {
    await delay();
    const roster = members.get(employerId) ?? [];
    const member = roster.find((m) => m.user_id === memberUserId);
    if (!member) throw new ApiError(404, "member not found");
    const owners = roster.filter((m) => m.role === "owner");
    if (member.role === "owner" && owners.length <= 1) throw new ApiError(409, "last_owner");
    members.set(
      employerId,
      roster.filter((m) => m.user_id !== memberUserId),
    );
  }

  async listInvites(employerId: string): Promise<InviteRead[]> {
    await delay();
    return invites.get(employerId) ?? [];
  }

  async createInvite(
    employerId: string,
    email: string,
    role: "owner" | "member",
  ): Promise<InviteRead> {
    await delay();
    if (email.length < 3 || email.length > 254)
      throw new ApiError(422, "email: must be 3–254 characters");
    const list = invites.get(employerId);
    if (!list) throw new ApiError(404, "employer not found");
    const invite: InviteRead = {
      id: uuid(),
      employer_id: employerId,
      email,
      role,
      status: "pending",
      expires_at: new Date(Date.now() + 7 * 86_400_000).toISOString(),
      created_at: new Date().toISOString(),
      invited_by_user_id: ME_ID,
    };
    list.unshift(invite);
    return invite;
  }

  async revokeInvite(employerId: string, inviteId: string): Promise<void> {
    await delay();
    const invite = (invites.get(employerId) ?? []).find((i) => i.id === inviteId);
    if (!invite || invite.status !== "pending") throw new ApiError(404, "invite not found");
    invite.status = "revoked";
  }
}
```

- [ ] **Step 2: Trim `frontend/src/sites/console/api/demo.ts` to admin-only fixtures**

Replace the entire file with:

```ts
import type { ConsoleClient } from "./client";
import { ApiError } from "./client";
import type {
  AdminUserRead,
  AuditLogFilters,
  AuditLogListResponse,
  AuditLogRead,
  EmployerVerificationPage,
  EmployerVerificationRow,
  EmployerVerificationStatus,
  MeResponse,
} from "./types";

/** Seeded in-memory backend so the console is fully explorable offline. */

const uuid = (() => {
  let n = 0;
  return () => {
    n += 1;
    const hex = n.toString(16).padStart(12, "0");
    return `00000000-0000-4000-8000-${hex}`;
  };
})();

const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
const daysAgo = (d: number) => hoursAgo(d * 24);

const delay = () => new Promise((resolve) => setTimeout(resolve, 220 + Math.random() * 260));

// ---- seed state -------------------------------------------------

const ME_ID = uuid();

const suspendedUsers = new Map<string, { reason: string; at: string }>();

const auditActions = [
  ["auth.signed_in", "user"],
  ["resume.uploaded", "resume"],
  ["resume.parsed", "resume"],
  ["application.created", "application"],
  ["application.withdrawn", "application"],
  ["job.created", "job"],
  ["job.applicants_listed", "job"],
  ["consent.updated", "consent"],
  ["user.dsr_export_requested", "user"],
  ["user.dsr_export_completed", "user"],
  ["employer.invite_created", "employer_invite"],
  ["employer.member_added", "employer_user"],
  ["admin.user.suspended", "user"],
  ["admin.user.unsuspended", "user"],
] as const;

const auditLogs: AuditLogRead[] = Array.from({ length: 137 }, (_, i) => {
  const [action, resourceType] = auditActions[(i * 5) % auditActions.length];
  const isAdmin = action.startsWith("admin.");
  const isSystem = action === "resume.parsed";
  return {
    id: uuid(),
    actor_user_id: isSystem ? null : i % 11 === 0 ? ME_ID : uuid(),
    actor_role: isSystem ? "system" : isAdmin ? "admin" : i % 4 === 0 ? "recruiter" : "applicant",
    action,
    resource_type: resourceType,
    resource_id: uuid(),
    context: {
      request_id: uuid(),
      ...(action === "admin.user.suspended"
        ? { reason: "spam job postings", target_user_role: "recruiter" }
        : {}),
      ...(action === "user.dsr_export_completed"
        ? { section_counts: { resumes: 2, applications: 7, matches: 31 } }
        : {}),
      ...(action === "application.created" ? { source: "feed" } : {}),
    },
    created_at: hoursAgo(i * 5 + (i % 7)),
  };
});

// ---- employer verification queue (PROPOSED contract; see client.ts) ---------
//
// Seeded across pending/verified/rejected so the queue is explorable. verify/
// reject mutate these rows AND push an admin audit row, mirroring suspendUser.

const mkVerification = (
  name: string,
  domain: string | null,
  contactEmail: string | null,
  gst: string | null,
  status: EmployerVerificationStatus,
  submittedDaysAgo: number,
  review: { daysAgo: number; reason: string | null } | null,
): EmployerVerificationRow => ({
  id: uuid(),
  name,
  domain,
  contact_email: contactEmail,
  gst,
  status,
  created_at: daysAgo(submittedDaysAgo),
  reviewed_at: review ? daysAgo(review.daysAgo) : null,
  reviewer: review ? "ops@jobify.in" : null,
  reason: review?.reason ?? null,
});

const verificationQueue: EmployerVerificationRow[] = [
  mkVerification("Northwind Logistics", "northwind.in", "talent@northwind.in", "27AAGCN2233R1Z9", "pending", 1, null),
  mkVerification("Tessellate Studio", "tessellate.design", "hello@tessellate.design", null, "pending", 2, null),
  mkVerification("Brightpath Tutoring", "brightpath.co.in", "founder@gmail.com", "29BRGHT9988K1Z2", "pending", 4, null),
  mkVerification("Quantum Foundry", "quantumfoundry.io", "people@quantumfoundry.io", "06QFNDR4521M1Z8", "pending", 6, null),
  mkVerification("Meridian Analytics", "meridian.in", "priya.k@meridian.in", "29ABCDE1234F1Z5", "verified", 41, {
    daysAgo: 40,
    reason: null,
  }),
  mkVerification("Greenleaf Agritech", "greenleaf.farm", "ops@greenleaf.farm", "33GRNLF6677P1Z4", "verified", 28, {
    daysAgo: 27,
    reason: null,
  }),
  mkVerification("Apex Crypto Holdings", null, "fast.cash.now@protonmail.com", null, "rejected", 15, {
    daysAgo: 14,
    reason: "No registered domain and contact email does not match the company; GST absent.",
  }),
  mkVerification("Skylar Mediaworks", "skylar.media", "admin@skylar-different.com", "19SKYLR3344Q1Z1", "rejected", 9, {
    daysAgo: 8,
    reason: "Contact email domain does not match the stated company domain.",
  }),
];

// ---- the client -------------------------------------------------

export class DemoClient implements ConsoleClient {
  readonly mode = "demo" as const;

  async me(): Promise<MeResponse> {
    await delay();
    return { id: ME_ID, email: "ops@jobify.in", role: "admin", applicant: null };
  }

  async listAuditLogs(filters: AuditLogFilters): Promise<AuditLogListResponse> {
    await delay();
    let rows = auditLogs.filter(
      (row) =>
        (!filters.action || row.action === filters.action) &&
        (!filters.actor_user_id || row.actor_user_id === filters.actor_user_id) &&
        (!filters.resource_type || row.resource_type === filters.resource_type) &&
        (!filters.resource_id || row.resource_id === filters.resource_id) &&
        (!filters.from || row.created_at >= filters.from) &&
        (!filters.to || row.created_at <= filters.to),
    );
    rows = [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at));
    const start = filters.cursor ? Number(filters.cursor) : 0;
    const limit = filters.limit ?? 50;
    const page = rows.slice(start, start + limit);
    return {
      items: page,
      next_cursor: start + limit < rows.length ? String(start + limit) : null,
    };
  }

  async suspendUser(userId: string, reason: string): Promise<AdminUserRead> {
    await delay();
    if (reason.length < 1 || reason.length > 255)
      throw new ApiError(422, "reason: must be 1–255 characters");
    if (userId === ME_ID) throw new ApiError(400, "cannot_suspend_self");
    const at = new Date().toISOString();
    suspendedUsers.set(userId, { reason, at });
    auditLogs.unshift({
      id: uuid(),
      actor_user_id: ME_ID,
      actor_role: "admin",
      action: "admin.user.suspended",
      resource_type: "user",
      resource_id: userId,
      context: { request_id: uuid(), reason },
      created_at: at,
    });
    return {
      id: userId,
      email: "subject@example.in",
      role: "applicant",
      suspended_at: at,
      suspension_reason: reason,
    };
  }

  async unsuspendUser(userId: string): Promise<AdminUserRead> {
    await delay();
    const wasSuspended = suspendedUsers.delete(userId);
    if (wasSuspended) {
      auditLogs.unshift({
        id: uuid(),
        actor_user_id: ME_ID,
        actor_role: "admin",
        action: "admin.user.unsuspended",
        resource_type: "user",
        resource_id: userId,
        context: { request_id: uuid() },
        created_at: new Date().toISOString(),
      });
    }
    return {
      id: userId,
      email: "subject@example.in",
      role: "applicant",
      suspended_at: null,
      suspension_reason: null,
    };
  }

  async listEmployersForVerification(
    status: EmployerVerificationStatus,
    cursor?: string,
  ): Promise<EmployerVerificationPage> {
    await delay();
    const rows = verificationQueue
      .filter((row) => row.status === status)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    const start = cursor ? Number(cursor) : 0;
    const limit = 10;
    return {
      items: rows.slice(start, start + limit),
      next_cursor: start + limit < rows.length ? String(start + limit) : null,
    };
  }

  async verifyEmployer(employerId: string): Promise<EmployerVerificationRow> {
    await delay();
    const row = verificationQueue.find((r) => r.id === employerId);
    if (!row) throw new ApiError(404, "employer not found");
    const at = new Date().toISOString();
    row.status = "verified";
    row.reviewed_at = at;
    row.reviewer = "ops@jobify.in";
    row.reason = null;
    auditLogs.unshift({
      id: uuid(),
      actor_user_id: ME_ID,
      actor_role: "admin",
      action: "admin.employer.verified",
      resource_type: "employer",
      resource_id: row.id,
      context: { request_id: uuid(), employer_name: row.name },
      created_at: at,
    });
    return row;
  }

  async rejectEmployer(employerId: string, reason: string): Promise<EmployerVerificationRow> {
    await delay();
    if (reason.length < 1 || reason.length > 255)
      throw new ApiError(422, "reason: must be 1–255 characters");
    const row = verificationQueue.find((r) => r.id === employerId);
    if (!row) throw new ApiError(404, "employer not found");
    const at = new Date().toISOString();
    row.status = "rejected";
    row.reviewed_at = at;
    row.reviewer = "ops@jobify.in";
    row.reason = reason;
    auditLogs.unshift({
      id: uuid(),
      actor_user_id: ME_ID,
      actor_role: "admin",
      action: "admin.employer.rejected",
      resource_type: "employer",
      resource_id: row.id,
      context: { request_id: uuid(), employer_name: row.name, reason },
      created_at: at,
    });
    return row;
  }
}
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -60`
Expected: remaining errors are only in `console/pages/recruiter/*` and `console/api/recruiterJobs.ts` (still present at their old path, still importing recruiter methods) — fixed by the move in Task 8/4.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/employers/api/demo.ts frontend/src/sites/console/api/demo.ts
git commit -m "$(cat <<'EOF'
refactor(frontend): split demo.ts fixtures — recruiter data moves to employers

The `employers` seed array turned out to be used only by the recruiter
fixtures (jobs/members/invites), not the verification queue as assumed —
it moves to employers/api/demo.ts in full. DemoRole is dropped from both:
each demo client now only ever represents the one role its surface serves.
EOF
)"
```

---

## Task 4: Move `api/recruiterJobs.ts` to `employers/api/`

**Files:**
- Create: `frontend/src/sites/employers/api/recruiterJobs.ts` (moved)
- Delete: `frontend/src/sites/console/api/recruiterJobs.ts`

**Interfaces:**
- Consumes: `EmployerClient` from Task 2.
- Produces: `drainJobs(client: EmployerClient, status)`, `findMyJob(client: EmployerClient, jobId)`, `MAX_JOB_PAGES` — Task 8's moved pages import these exact names.

- [ ] **Step 1: Move the file**

```bash
git mv frontend/src/sites/console/api/recruiterJobs.ts frontend/src/sites/employers/api/recruiterJobs.ts
```

- [ ] **Step 2: Update the one type import (`ConsoleClient` → `EmployerClient`)**

In `frontend/src/sites/employers/api/recruiterJobs.ts`, change:

```ts
import type { ConsoleClient } from "./client";
import type { RecruiterJobRow } from "./types";
```

to:

```ts
import type { EmployerClient } from "./client";
import type { RecruiterJobRow } from "./types";
```

Then replace both remaining occurrences of `ConsoleClient` in the file (the `client: ConsoleClient` parameter in `drainJobs` and in `findMyJob`) with `EmployerClient`.

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -60`
Expected: no errors in `employers/api/recruiterJobs.ts`. Remaining errors confined to `console/pages/recruiter/*` (moved in Task 8) — the old `console/api/recruiterJobs.ts` is gone so any lingering import of it elsewhere will now show as a missing-module error, confirming nothing else still depends on the old path.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src/sites/console/api/recruiterJobs.ts frontend/src/sites/employers/api/recruiterJobs.ts
git commit -m "refactor(frontend): move api/recruiterJobs.ts from console to employers"
```

---

## Task 5: Create `employers/paging/usePagedFetch.ts`

**Files:**
- Create: `frontend/src/sites/employers/paging/usePagedFetch.ts`

**Interfaces:**
- Produces: re-exports `usePagedFetch`, `Page`, `PagedFetch` from `shared/hooks/usePagedFetch` — Task 8's Jobs.tsx/Applicants.tsx import `usePagedFetch` from `"../../paging/usePagedFetch"`.

- [ ] **Step 1: Create the file**

```ts
// The employer workspace list screens (jobs, applicants) use the canonical
// cursor-pagination hook from src/shared/hooks. Kept as a thin re-export so
// call sites need no churn.
export { usePagedFetch } from "../../../shared/hooks/usePagedFetch";
export type { Page, PagedFetch } from "../../../shared/hooks/usePagedFetch";
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -20`
Expected: no new errors introduced by this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/paging/usePagedFetch.ts
git commit -m "feat(frontend): add employers/paging/usePagedFetch re-export"
```

---

## Task 6: Split `components/bits.tsx` — trim console's, create employers' with recruiter-only additions

**Files:**
- Create: `frontend/src/sites/employers/components/bits.tsx`
- Modify: `frontend/src/sites/console/components/bits.tsx`

**Interfaces:**
- Produces: `employers/components/bits.tsx` exports `lakh`, `ctcBandText`, `IstClock`, `Field`, `Stamp`, `ShortId`, `ErrorNotice`, `EmptyState`, `ScoreBar` — Task 8's moved pages and Task 10/11/13 import from here.
- Produces: `console/components/bits.tsx` (trimmed) keeps exporting `IstClock`, `Field`, `Stamp`, `ShortId`, `JsonView`, `Drawer`, `ErrorNotice`, `EmptyState` — drops `lakh`/`ctcBandText`/`ScoreBar` (confirmed unused by any remaining console page — only the moved recruiter pages used them).

- [ ] **Step 1: Create `frontend/src/sites/employers/components/bits.tsx`**

```tsx
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { inrLakh, istClock, istDateTime } from "../../../shared/format";
import {
  EmptyState as SharedEmptyState,
  ErrorNotice as SharedErrorNotice,
} from "../../../shared/components/notices";

/** ₹ lakh formatting for a single CTC figure (null → null). Thin re-export of
 *  the shared `inrLakh` (single source in shared/format.ts) for the employer
 *  workspace — Postings list, composer preview, dashboard. */
export const lakh = inrLakh;

/** The "₹xL – ₹yL" / "Undisclosed" compensation band as a plain string. */
export function ctcBandText(min: number | null, max: number | null): string {
  const lo = lakh(min);
  const hi = lakh(max);
  if (!lo && !hi) return "Undisclosed";
  return [lo, hi].filter(Boolean).join(" – ");
}

/** Live IST clock — the masthead heartbeat (Asia/Kolkata). */
export function IstClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return <span className="clock num">{istClock(now)}</span>;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="k">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  );
}

/** Compact relative + absolute timestamp. */
export function Stamp({ iso }: { iso: string }) {
  const date = new Date(iso);
  const deltaMs = Date.now() - date.getTime();
  const minutes = Math.round(Math.abs(deltaMs) / 60_000);
  const rel =
    minutes < 1
      ? "now"
      : minutes < 60
        ? `${minutes}m`
        : minutes < 60 * 48
          ? `${Math.round(minutes / 60)}h`
          : `${Math.round(minutes / 1440)}d`;
  const sign = rel === "now" ? "now" : deltaMs >= 0 ? `${rel} ago` : `in ${rel}`;
  return (
    <span className="num" title={`${date.toISOString()} (UTC)`}>
      <span className="dim">{istDateTime(iso)} IST</span>{" "}
      <span>· {sign}</span>
    </span>
  );
}

export function ShortId({ id, onPick }: { id: string; onPick?: (id: string) => void }) {
  const short = `${id.slice(0, 8)}…${id.slice(-4)}`;
  if (!onPick) {
    return (
      <span className="num" title={id}>
        {short}
      </span>
    );
  }
  return (
    <span
      className="num clickable-id"
      title={`${id} — click to use`}
      onClick={(e) => {
        e.stopPropagation();
        onPick(id);
      }}
    >
      {short}
    </span>
  );
}

export function ErrorNotice({ error }: { error: string | null }) {
  return <SharedErrorNotice error={error} className="notice error" />;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <SharedEmptyState as="div" innerClassName="flavor">
      {children}
    </SharedEmptyState>
  );
}

export function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="dim">—</span>;
  return (
    <span className="scorebar">
      <span className="track">
        <span className="fill" style={{ width: `${Math.round(score * 100)}%` }} />
      </span>
      <span className="num">{score.toFixed(2)}</span>
    </span>
  );
}
```

- [ ] **Step 2: Trim `frontend/src/sites/console/components/bits.tsx`**

Replace the entire file with:

```tsx
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { istClock, istDateTime } from "../../../shared/format";
import {
  EmptyState as SharedEmptyState,
  ErrorNotice as SharedErrorNotice,
} from "../../../shared/components/notices";

/** Live IST clock — the control-room heartbeat in the masthead (Asia/Kolkata). */
export function IstClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return <span className="clock num">{istClock(now)}</span>;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="k">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  );
}

/** Compact relative + absolute timestamp. */
export function Stamp({ iso }: { iso: string }) {
  const date = new Date(iso);
  const deltaMs = Date.now() - date.getTime();
  const minutes = Math.round(Math.abs(deltaMs) / 60_000);
  const rel =
    minutes < 1
      ? "now"
      : minutes < 60
        ? `${minutes}m`
        : minutes < 60 * 48
          ? `${Math.round(minutes / 60)}h`
          : `${Math.round(minutes / 1440)}d`;
  const sign = rel === "now" ? "now" : deltaMs >= 0 ? `${rel} ago` : `in ${rel}`;
  return (
    <span className="num" title={`${date.toISOString()} (UTC)`}>
      <span className="dim">{istDateTime(iso)} IST</span>{" "}
      <span>· {sign}</span>
    </span>
  );
}

export function ShortId({ id, onPick }: { id: string; onPick?: (id: string) => void }) {
  const short = `${id.slice(0, 8)}…${id.slice(-4)}`;
  if (!onPick) {
    return (
      <span className="num" title={id}>
        {short}
      </span>
    );
  }
  return (
    <span
      className="num clickable-id"
      title={`${id} — click to use in user actions`}
      onClick={(e) => {
        e.stopPropagation();
        onPick(id);
      }}
    >
      {short}
    </span>
  );
}

export function JsonView({ value }: { value: unknown }) {
  return <pre className="json-view">{JSON.stringify(value, null, 2)}</pre>;
}

export function Drawer({
  title,
  onClose,
  children,
  foot,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  foot?: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <div className="drawer-veil" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={title}>
        <div className="drawer-head">
          <h2>{title}</h2>
          <button className="btn ghost sm" onClick={onClose}>
            ESC / Close
          </button>
        </div>
        <div className="drawer-body">{children}</div>
        {foot && <div className="drawer-foot">{foot}</div>}
      </aside>
    </>
  );
}

export function ErrorNotice({ error }: { error: string | null }) {
  return <SharedErrorNotice error={error} className="notice error" />;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <SharedEmptyState as="div" innerClassName="flavor">
      {children}
    </SharedEmptyState>
  );
}
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -60`
Expected: remaining errors confined to `console/pages/recruiter/*` (still at the old path — fixed in Task 8).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/employers/components/bits.tsx frontend/src/sites/console/components/bits.tsx
git commit -m "refactor(frontend): split components/bits.tsx — lakh/ctcBandText/ScoreBar move to employers"
```

---

## Task 7: Create `employers/session.tsx` and `employers/env.ts`

**Files:**
- Create: `frontend/src/sites/employers/session.tsx`
- Create: `frontend/src/sites/employers/env.ts`

**Interfaces:**
- Consumes: `createSession` from `shared/session/createSession.tsx` (unchanged), `HttpClient`/`EmployerClient` from Task 2, `DemoClient` from Task 3.
- Produces: `SessionProvider`, `useSessionStore`, `useSession` — every employers page/component from here on imports these from `"../session"`.

- [ ] **Step 1: Create `frontend/src/sites/employers/session.tsx`**

```tsx
import { createSession } from "../../shared/session/createSession";
import { DemoClient } from "./api/demo";
import { HttpClient } from "./api/client";
import type { EmployerClient } from "./api/client";
import type { MeResponse } from "./api/types";

export const { SessionProvider, useSessionStore, useSession } = createSession<EmployerClient, MeResponse>({
  makeLive: (store, onSignOut) => new HttpClient(store, onSignOut),
  makeDemo: () => new DemoClient(),
});
```

- [ ] **Step 2: Create `frontend/src/sites/employers/env.ts`**

```ts
export { API_BASE_URL, GOOGLE_CLIENT_ID } from "../../shared/env";
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -20`
Expected: no errors from these two new files.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/employers/session.tsx frontend/src/sites/employers/env.ts
git commit -m "feat(frontend): add employers/session.tsx (own SessionProvider) and env.ts"
```

---

## Task 8: Move the 5 recruiter pages + jobForm.ts to `employers/pages/dashboard/`, updating internal routes

**Files:**
- Create (moved): `frontend/src/sites/employers/pages/dashboard/{Dashboard,Jobs,JobComposer,Applicants,Team}.tsx`, `frontend/src/sites/employers/pages/dashboard/jobForm.ts`
- Delete: `frontend/src/sites/console/pages/recruiter/` (entire directory, after the move)

**Interfaces:**
- Consumes: `EmployerClient`/`errorMessage`/`ApiError` (Task 2), types (Task 1), `bits` (Task 6), `session` (Task 7), `recruiterJobs.ts` (Task 4), `usePagedFetch` (Task 5).
- Produces: `Dashboard`, `Jobs`, `JobComposer`, `Applicants`, `Team` components — Task 14 (`EmployersRoutes.tsx`) imports these exact names from `"./pages/dashboard/{Name}"`.

All 6 files move at the same relative depth (`pages/recruiter/*.tsx` → `pages/dashboard/*.tsx`, both 2 levels under the surface root), so every existing relative import (`"../../api/client"`, `"../../components/bits"`, `"../../session"`, `"../../paging/usePagedFetch"`, `"./jobForm"`) resolves correctly at the new location with zero import-path edits. Only the internal `/console/recruiter/...` route strings need updating to `/employers/...`.

- [ ] **Step 1: Move all 6 files with git mv**

```bash
mkdir -p frontend/src/sites/employers/pages/dashboard
git mv frontend/src/sites/console/pages/recruiter/Dashboard.tsx frontend/src/sites/employers/pages/dashboard/Dashboard.tsx
git mv frontend/src/sites/console/pages/recruiter/Jobs.tsx frontend/src/sites/employers/pages/dashboard/Jobs.tsx
git mv frontend/src/sites/console/pages/recruiter/JobComposer.tsx frontend/src/sites/employers/pages/dashboard/JobComposer.tsx
git mv frontend/src/sites/console/pages/recruiter/Applicants.tsx frontend/src/sites/employers/pages/dashboard/Applicants.tsx
git mv frontend/src/sites/console/pages/recruiter/Team.tsx frontend/src/sites/employers/pages/dashboard/Team.tsx
git mv frontend/src/sites/console/pages/recruiter/jobForm.ts frontend/src/sites/employers/pages/dashboard/jobForm.ts
```

- [ ] **Step 2: Update route strings in `Dashboard.tsx`** (4 occurrences)

Replace each of these exact strings:
- `to="/console/recruiter/jobs"` (the "All jobs →" link) → `to="/employers/jobs"`
- `` to={`/console/recruiter/jobs/${job.id}/applicants`} `` → `` to={`/employers/jobs/${job.id}/applicants`} ``
- `to="/console/recruiter/jobs"` (the "post the first one" link inside `EmptyState`) → `to="/employers/jobs"`
- `to="/console/recruiter/team"` → `to="/employers/team"`

- [ ] **Step 3: Update route strings in `Jobs.tsx`** (4 occurrences)

Replace each of these exact strings:
- `navigate("/console/recruiter/jobs/new")` → `navigate("/employers/jobs/new")`
- `` to={`/console/recruiter/jobs/${job.id}/applicants`} `` (title link) → `` to={`/employers/jobs/${job.id}/applicants`} ``
- `` to={`/console/recruiter/jobs/${job.id}/applicants`} `` (applicant-count link) → `` to={`/employers/jobs/${job.id}/applicants`} ``
- `` navigate(`/console/recruiter/jobs/${job.id}/edit`, { state: { job } }) `` → `` navigate(`/employers/jobs/${job.id}/edit`, { state: { job } }) ``

- [ ] **Step 4: Update route strings in `JobComposer.tsx`** (4 occurrences, all the literal string `/console/recruiter/jobs`)

- `navigate("/console/recruiter/jobs", { state: { status: form.status } })` (in `save()`, no-change branch) → `navigate("/employers/jobs", { state: { status: form.status } })`
- `navigate("/console/recruiter/jobs", { state: { status: form.status } })` (in `save()`, success branch) → `navigate("/employers/jobs", { state: { status: form.status } })`
- `<Link to="/console/recruiter/jobs" className="jc-back">` → `<Link to="/employers/jobs" className="jc-back">`
- `<Link to="/console/recruiter/jobs" className="btn ghost">` → `<Link to="/employers/jobs" className="btn ghost">`

- [ ] **Step 5: Update route strings in `Applicants.tsx`** (1 occurrence)

- `<Link className="btn ghost sm" to="/console/recruiter/jobs">` → `<Link className="btn ghost sm" to="/employers/jobs">`

- [ ] **Step 6: `Team.tsx` and `jobForm.ts` need no edits**

Confirm no `/console/recruiter` strings exist in either file (verified during planning — `Team.tsx` has no internal navigation, `jobForm.ts` has no route strings at all). No action needed.

- [ ] **Step 7: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -80`
Expected: zero errors. This is the point where the whole recruiter-side type chain (types → client → demo → recruiterJobs → bits → session → pages) should compile clean end-to-end.

Run: `grep -rn "console/recruiter\|/console/recruiter" frontend/src/sites/employers`
Expected: no output (confirms every route string was updated).

- [ ] **Step 8: Commit**

```bash
git add -A frontend/src/sites/console/pages/recruiter frontend/src/sites/employers/pages/dashboard
git commit -m "$(cat <<'EOF'
refactor(frontend): move recruiter pages from console/pages/recruiter to employers/pages/dashboard

Dashboard, Jobs, JobComposer, Applicants, Team, and jobForm move verbatim
except for internal /console/recruiter/* route strings, now /employers/*.
EOF
)"
```

---

## Task 9: Create `employers/styles/dashboard.css` (scoped copy of console.css)

**Files:**
- Create: `frontend/src/sites/employers/styles/dashboard.css`

**Interfaces:**
- Produces: every CSS class the moved recruiter pages + the new Shell/SignIn/Settings (Tasks 10–13) reference (`.panel`, `.chip`, `.tile`, `.table-wrap`, `.jc-*`, `.gate`, `.rail`, `.shell`, `.scorebar`, `.mode-tabs`, `.field`, `.notice`, etc.), scoped under `.surface-employers .dash` instead of `.surface-console`.

**Why a new scope prefix, not just `.surface-employers`:** the marketing site's `site.css` already defines `.surface-employers .btn`, `.masthead`, `.dim`, `.num`, `.rise` for the Chrome/Landing/Verify pages. A blind copy under `.surface-employers` alone would collide (both stylesheets loaded in the same bundle). Wrapping the authenticated recruiter zone's root elements in an additional `.dash` class and scoping every migrated selector under `.surface-employers .dash` gives those rules higher specificity than site.css's 2-class selectors, so they always win inside the dashboard zone — no collision, no site.css edits needed. Task 10/13 add `className="dash shell"` / `className="dash gate"` on the two zone-root components; every page nested inside inherits the scope via the CSS descendant combinator.

- [ ] **Step 1: Copy and rescope the stylesheet**

```bash
cp frontend/src/sites/console/styles/console.css frontend/src/sites/employers/styles/dashboard.css
sed -i '' 's/\.surface-console/.surface-employers .dash/g' frontend/src/sites/employers/styles/dashboard.css
```

- [ ] **Step 2: Verify the rescope caught every occurrence and didn't touch console's original**

```bash
grep -c "surface-console" frontend/src/sites/employers/styles/dashboard.css
```
Expected: `0`

```bash
grep -c "surface-console" frontend/src/sites/console/styles/console.css
```
Expected: same count as before this task (console's own file untouched — `cp` doesn't mutate the source).

- [ ] **Step 3: Add a one-line header comment noting the provenance**

At the top of `frontend/src/sites/employers/styles/dashboard.css`, add:

```css
/* Copied from sites/console/styles/console.css and rescoped .surface-console →
   .surface-employers .dash — see EmployersRoutes.tsx/Shell.tsx for the ".dash"
   wrapper this depends on. Keep visual parity with console's instrument-panel
   language; this is deliberate duplication (each surface owns its CSS), not
   drift to fix. */
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/employers/styles/dashboard.css
git commit -m "feat(frontend): add employers/styles/dashboard.css (rescoped copy of console.css)"
```

(This stylesheet won't be imported by any route yet — Task 14 adds the import. `npm run build` stays clean either way since an unimported CSS file doesn't affect compilation.)

---

## Task 10: Create `employers/auth/GoogleButton.tsx`

**Files:**
- Create: `frontend/src/sites/employers/auth/GoogleButton.tsx`

**Interfaces:**
- Consumes: `GoogleSignInButton` from `shared/auth/GoogleSignInButton.tsx` (unchanged, already supports a `"filled_blue"` theme option).
- Produces: `GoogleButton` component — Task 13's `SignIn.tsx` imports this.

- [ ] **Step 1: Create the file**

```tsx
import { GoogleSignInButton } from "../../../shared/auth/GoogleSignInButton";

/** Employers keeps the brand-blue Google button — the interactive colour used
 *  for primary actions across every surface. */
export function GoogleButton(props: {
  clientId: string;
  onCredential: (idToken: string) => void;
  onLoadError: (message: string) => void;
}) {
  return <GoogleSignInButton {...props} theme="filled_blue" />;
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -20`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/auth/GoogleButton.tsx
git commit -m "feat(frontend): add employers/auth/GoogleButton (brand-blue theme)"
```

---

## Task 11: Create `employers/components/Shell.tsx`

**Files:**
- Create: `frontend/src/sites/employers/components/Shell.tsx`

**Interfaces:**
- Consumes: `useSession`, `useSessionStore` from Task 7's `session.tsx`; `IstClock` from Task 6's `bits.tsx`; `ThemeToggle` from `shared/theme/ThemeToggle.tsx` (unchanged).
- Produces: `Shell` component (renders `<Outlet/>` for nested routes) — Task 14's `EmployersRoutes.tsx` imports this.

- [ ] **Step 1: Create the file**

```tsx
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useSession, useSessionStore } from "../session";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
import { IstClock } from "./bits";

const NAV = [
  { to: "/employers/dashboard", idx: "00", label: "Dashboard", end: true },
  { to: "/employers/jobs", idx: "01", label: "Jobs" },
  { to: "/employers/team", idx: "02", label: "Team & invites" },
];

/** Nav shell for the authenticated recruiter zone (mounted under /employers/*
 *  once signed in). Adapted from console's Shell — single nav section since
 *  this surface only ever serves recruiters, no area-switching needed. The
 *  "dash" class (alongside "shell") scopes dashboard.css above site.css's
 *  same-named classes — see styles/dashboard.css's header comment. */
export function Shell() {
  const { identity, client } = useSession();
  const { signOut } = useSessionStore();
  const { pathname } = useLocation();
  const crumb = pathname.split("/").filter(Boolean).join(" / ");

  return (
    <div className="dash shell">
      <nav className="rail">
        <div className="rail-brand">
          <div className="rail-lockup">
            <img src="/jobify-mark.svg" alt="Jobify" className="rail-mark" />
            <div className="wordmark">
              JOBIFY<em>//</em>EMPLOYERS
            </div>
          </div>
          <div className="k" style={{ marginTop: 4 }}>
            employer workspace
          </div>
          <div style={{ marginTop: 8 }}>
            <ThemeToggle />
          </div>
        </div>

        <div className="rail-section">
          <span className="k">Recruiting</span>
          {NAV.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end ?? false}
              className={({ isActive }) => `rail-link${isActive ? " active" : ""}`}
            >
              <span className="idx num">{link.idx}</span>
              {link.label}
            </NavLink>
          ))}
        </div>

        <div className="rail-foot">
          <div className="row">
            <span className={`led ${client.mode === "live" ? "live" : "amber"}`} />
            <span className="k">{client.mode === "live" ? "live api" : "demo data"}</span>
          </div>
          <div className="dim" style={{ fontSize: 11, wordBreak: "break-all" }}>
            {identity.email ?? identity.id}
            <span className="chip" style={{ marginLeft: 8 }}>
              {identity.role}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <NavLink
              to="/employers/settings"
              className={({ isActive }) => `btn sm ghost${isActive ? " active" : ""}`}
              style={{ flex: 1, justifyContent: "center" }}
            >
              Settings
            </NavLink>
            <button className="btn sm" onClick={signOut} style={{ flex: 1 }}>
              Log out
            </button>
          </div>
        </div>
      </nav>

      <div className="main">
        <header className="masthead">
          <span className="crumbs">
            employers / <b>{crumb || "home"}</b>
          </span>
          <IstClock />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -20`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/components/Shell.tsx
git commit -m "feat(frontend): add employers/components/Shell (recruiter nav)"
```

---

## Task 12: Create `employers/pages/Settings.tsx`

**Files:**
- Create: `frontend/src/sites/employers/pages/Settings.tsx`

**Interfaces:**
- Consumes: `useSession`, `useSessionStore` from Task 7; `ThemeToggle` (unchanged).
- Produces: `Settings` component — Task 14 imports this.

- [ ] **Step 1: Create the file**

```tsx
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
import { useSession, useSessionStore } from "../session";

/** Recruiter account & appearance — identity, theme, session. No résumé/DSR
 *  data here (that's the Flutter applicant app's responsibility), same
 *  rationale as console's admin-only Settings page. */
export function Settings() {
  const { identity, client } = useSession();
  const { signOut } = useSessionStore();
  const isLive = client.mode === "live";

  return (
    <>
      <div className="headline">
        <h1>
          ACCOUNT <span className="ghost">SETTINGS</span>
        </h1>
        <div className="sub">
          <span className="flavor">Your recruiter profile, appearance, and session.</span>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 620, marginBottom: 18 }}>
        <div className="panel-head">
          <span className="k">Recruiter</span>
          <span className="chip">{identity.role}</span>
        </div>
        <div className="panel-body">
          <div className="field-row">
            <div className="field">
              <span className="k">Email</span>
              <div style={{ marginTop: 4 }}>{identity.email ?? "—"}</div>
            </div>
            <div className="field">
              <span className="k">User ID</span>
              <div className="num dim" style={{ marginTop: 4, wordBreak: "break-all" }}>
                {identity.id}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 620, marginBottom: 18 }}>
        <div className="panel-head">
          <span className="k">Appearance</span>
        </div>
        <div className="panel-body" style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <ThemeToggle />
          <span className="dim" style={{ fontSize: 13 }}>
            Light, dark, or match your system — saved to this browser.
          </span>
        </div>
      </div>

      <div className="panel" style={{ maxWidth: 620 }}>
        <div className="panel-head">
          <span className="k">Session</span>
          <span className={`chip ${isLive ? "ok" : ""}`}>
            {isLive ? "live api" : "demo data"}
          </span>
        </div>
        <div className="panel-body" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <span className="dim" style={{ fontSize: 13 }}>
            End this session and return to sign-in.
          </span>
          <button className="btn" onClick={signOut}>
            Log out
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -20`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/pages/Settings.tsx
git commit -m "feat(frontend): add employers/pages/Settings"
```

---

## Task 13: Create `employers/pages/SignIn.tsx`

**Files:**
- Create: `frontend/src/sites/employers/pages/SignIn.tsx`

**Interfaces:**
- Consumes: `ApiError`, `errorMessage` from Task 2's `client.ts`; `GoogleButton` from Task 10; `ErrorNotice`, `Field`, `IstClock` from Task 6; `API_BASE_URL`, `GOOGLE_CLIENT_ID` from Task 7's `env.ts`; `useSessionStore` from Task 7's `session.tsx`.
- Produces: `SignIn` component — Task 14 imports this. On successful sign-in, navigates to `/employers/dashboard` if `identity.role === "recruiter"`, else `/employers/no-access`.

- [ ] **Step 1: Create the file**

```tsx
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import { GoogleButton } from "../auth/GoogleButton";
import { ErrorNotice, Field, IstClock } from "../components/bits";
import { API_BASE_URL, GOOGLE_CLIENT_ID } from "../env";
import { useSessionStore } from "../session";
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

  function landingFor(role: string): string {
    return role === "recruiter" ? "/employers/dashboard" : "/employers/no-access";
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
            recruiters only — new Google users provision as applicants and see the no-access
            page. Reach out to <a href="mailto:hello@jobify.in">hello@jobify.in</a> to get set up.
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
              Explore the full employer workspace against seeded in-memory fixtures — every table
              and action works; nothing leaves the browser.
            </p>
          </div>
        )}

        <button
          className="btn primary rise"
          onClick={connect}
          disabled={busy || (mode === "live" && !token.trim())}
        >
          {busy ? "Connecting…" : mode === "demo" ? "Enter demo workspace" : "Connect"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -20`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/pages/SignIn.tsx
git commit -m "feat(frontend): add employers/pages/SignIn (Google + demo, recruiter-only)"
```

---

## Task 14: Wire it all up in `EmployersRoutes.tsx`

**Files:**
- Modify: `frontend/src/sites/employers/EmployersRoutes.tsx`

**Interfaces:**
- Consumes: `Landing`, `Verify` (unchanged); `SignIn` (Task 13), `Settings` (Task 12), `Shell` (Task 11); `Dashboard`, `Jobs`, `JobComposer`, `Applicants`, `Team` (Task 8); `SessionProvider`, `useSessionStore` (Task 7).
- Produces: `EmployersRoutes()` — no longer exports `CONSOLE_URL` (removed; Task 15 updates its 3 consumers).

- [ ] **Step 1: Replace the entire file**

```tsx
import { Navigate, Outlet, Route } from "react-router-dom";
import { useEffect } from "react";
import type { ReactNode } from "react";
import "./styles/site.css";
import "./styles/dashboard.css";
import { Landing } from "./pages/Landing";
import { Verify } from "./pages/Verify";
import { SignIn } from "./pages/SignIn";
import { Settings } from "./pages/Settings";
import { Shell } from "./components/Shell";
import { Dashboard } from "./pages/dashboard/Dashboard";
import { Jobs } from "./pages/dashboard/Jobs";
import { JobComposer } from "./pages/dashboard/JobComposer";
import { Applicants } from "./pages/dashboard/Applicants";
import { Team } from "./pages/dashboard/Team";
import { SessionProvider, useSessionStore } from "./session";

/** CSS-scope + title wrapper for the employers marketing surface (mounted at "/employers"). */
function EmployersLayout() {
  useEffect(() => {
    document.title = "Jobify for employers — ranked applicants, not a résumé pile";
  }, []);
  return (
    <div className="surface-employers">
      <Outlet />
    </div>
  );
}

function RequireSession({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to="/employers/signin" replace />;
  return <>{children}</>;
}

/** This surface only ever serves recruiters — an applicant or admin who signs
 *  in here lands on /no-access rather than the job desk. Wraps the whole
 *  recruiter-ops route group at once (unlike console, there's only one role
 *  to check here, so no per-route repetition is needed). */
function RequireRecruiter() {
  const { session } = useSessionStore();
  if (session && session.identity.role !== "recruiter") {
    return <Navigate to="/employers/no-access" replace />;
  }
  return <Outlet />;
}

function NoAccess() {
  const { session } = useSessionStore();
  return (
    <div className="content">
      <div className="headline">
        <h1>
          NO <span className="ghost">ACCESS</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            This workspace is for recruiters. Your account
            {session ? ` (role: ${session.identity.role})` : ""} can&apos;t reach the job desk.
          </span>
        </div>
      </div>
    </div>
  );
}

/** Session wrapper for the authenticated recruiter zone (mounted under /employers/*). */
function DashboardLayout() {
  useEffect(() => {
    document.title = "Jobify — employer workspace";
  }, []);
  return (
    <SessionProvider>
      <Outlet />
    </SessionProvider>
  );
}

/** Employers (recruiter marketing + authenticated workspace) routes. Returned into the top <Routes>. */
export function EmployersRoutes() {
  return (
    <Route element={<EmployersLayout />}>
      <Route path="/employers" element={<Landing />} />
      <Route path="/employers/verify" element={<Verify />} />

      <Route element={<DashboardLayout />}>
        <Route path="/employers/signin" element={<SignIn />} />
        <Route
          element={
            <RequireSession>
              <Shell />
            </RequireSession>
          }
        >
          {/* Account & settings — any signed-in recruiter, not role-gated further. */}
          <Route path="/employers/settings" element={<Settings />} />
          <Route path="/employers/no-access" element={<NoAccess />} />
          <Route element={<RequireRecruiter />}>
            <Route path="/employers/dashboard" element={<Dashboard />} />
            <Route path="/employers/jobs" element={<Jobs />} />
            <Route path="/employers/jobs/new" element={<JobComposer />} />
            <Route path="/employers/jobs/:jobId/edit" element={<JobComposer />} />
            <Route path="/employers/jobs/:jobId/applicants" element={<Applicants />} />
            <Route path="/employers/team" element={<Team />} />
          </Route>
        </Route>
      </Route>

      <Route path="/employers/*" element={<Navigate to="/employers" replace />} />
    </Route>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -80`
Expected: errors only in `Chrome.tsx`/`Landing.tsx`/`Verify.tsx` (still importing the now-removed `CONSOLE_URL`) — fixed in Task 15.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/employers/EmployersRoutes.tsx
git commit -m "feat(frontend): wire recruiter sign-in + dashboard routes into EmployersRoutes"
```

---

## Task 15: Update marketing CTA copy/links in `Chrome.tsx`, `Landing.tsx`, `Verify.tsx`

**Files:**
- Modify: `frontend/src/sites/employers/components/Chrome.tsx`
- Modify: `frontend/src/sites/employers/pages/Landing.tsx`
- Modify: `frontend/src/sites/employers/pages/Verify.tsx`

**Interfaces:**
- Consumes: nothing new — all three already import `Link` from `react-router-dom`.
- Produces: no more references to `CONSOLE_URL` anywhere in `employers/`.

- [ ] **Step 1: Edit `Chrome.tsx`**

Remove the import:
```tsx
import { CONSOLE_URL } from "../EmployersRoutes";
```

Replace the masthead CTA:
```tsx
          <a
            className="btn btn-primary btn-sm"
            href={CONSOLE_URL}
            target="_blank"
            rel="noreferrer"
          >
            Open the console <span className="arrow" aria-hidden="true">→</span>
          </a>
```
with:
```tsx
          <Link className="btn btn-primary btn-sm" to="/employers/signin">
            Sign in <span className="arrow" aria-hidden="true">→</span>
          </Link>
```

Replace the footer "Access" column CTA:
```tsx
            <a href={CONSOLE_URL} target="_blank" rel="noreferrer">
              Console sign-in
            </a>
```
with:
```tsx
            <Link to="/employers/signin">Sign in</Link>
```

- [ ] **Step 2: Edit `Landing.tsx`**

Remove the import:
```tsx
import { CONSOLE_URL } from "../EmployersRoutes";
```

Replace the hero CTA:
```tsx
            <a className="btn btn-primary" href={CONSOLE_URL} target="_blank" rel="noreferrer">
              Open the console <span className="arrow" aria-hidden="true">→</span>
            </a>
```
with:
```tsx
            <Link className="btn btn-primary" to="/employers/signin">
              Sign in <span className="arrow" aria-hidden="true">→</span>
            </Link>
```

Replace the Starter plan CTA:
```tsx
              <a className="btn btn-ghost" href={CONSOLE_URL} target="_blank" rel="noreferrer">
                Start free
              </a>
```
with:
```tsx
              <Link className="btn btn-ghost" to="/employers/signin">
                Start free
              </Link>
```

Replace the Team plan CTA:
```tsx
              <a className="btn btn-primary" href={CONSOLE_URL} target="_blank" rel="noreferrer">
                Choose Team <span className="arrow" aria-hidden="true">→</span>
              </a>
```
with:
```tsx
              <Link className="btn btn-primary" to="/employers/signin">
                Choose Team <span className="arrow" aria-hidden="true">→</span>
              </Link>
```

Update the FAQ Q6 copy — replace:
```
                Open the console, create your employer workspace, and post your first role.
```
with:
```
                Sign in, create your employer workspace, and post your first role.
```

Replace the final CTA band:
```tsx
              <a className="btn btn-invert" href={CONSOLE_URL} target="_blank" rel="noreferrer">
                Open the console <span className="arrow" aria-hidden="true">→</span>
              </a>
```
with:
```tsx
              <Link className="btn btn-invert" to="/employers/signin">
                Sign in <span className="arrow" aria-hidden="true">→</span>
              </Link>
```

Update the sentence just above it — replace:
```
              reason on each. The console is one click away.
```
with:
```
              reason on each. Sign-in is one click away.
```

- [ ] **Step 3: Edit `Verify.tsx`**

Remove the import:
```tsx
import { CONSOLE_URL } from "../EmployersRoutes";
```

Update the step copy — replace:
```
                  Sign in to the console and set up your organisation. This makes you the
```
with:
```
                  Sign in and set up your organisation. This makes you the
```

Update the CTA heading — replace:
```
            <h2>Get verified in the console.</h2>
```
with:
```
            <h2>Get verified.</h2>
```

Replace the final CTA:
```tsx
              <a className="btn btn-invert" href={CONSOLE_URL} target="_blank" rel="noreferrer">
                Open the console <span className="arrow" aria-hidden="true">→</span>
              </a>
```
with:
```tsx
              <Link className="btn btn-invert" to="/employers/signin">
                Sign in <span className="arrow" aria-hidden="true">→</span>
              </Link>
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -80`
Expected: zero errors anywhere in `employers/`.

Run: `grep -rn "CONSOLE_URL" frontend/src`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sites/employers/components/Chrome.tsx frontend/src/sites/employers/pages/Landing.tsx frontend/src/sites/employers/pages/Verify.tsx
git commit -m "$(cat <<'EOF'
fix(frontend): point marketing CTAs at /employers/signin instead of the console

"Open the console" was, technically, where a recruiter was supposed to
end up — now that they have their own sign-in, the copy and links say so.
EOF
)"
```

---

## Task 16: Add `console/base.ts` (subdomain-readiness constant)

**Files:**
- Create: `frontend/src/sites/console/base.ts`

**Interfaces:**
- Produces: `CONSOLE_BASE` (string) — Tasks 17–20 build every console route/link from this.

This replaces the spec's original "nested `<Route>` + relative `<Link>`" approach with a simpler, equally effective one: every console path is built from one constant instead of being hardcoded, so serving console from its own subdomain later means changing what this constant resolves to — not restructuring the route tree. Functionally identical goal (one-line change at cutover), lower implementation risk (no route-tree nesting to get wrong).

- [ ] **Step 1: Create the file**

```ts
/** Base path console mounts under. Empty string when served from its own
 *  subdomain (console.jobify.com); "/console" when served as a path prefix
 *  on the shared origin. Every console route/link is built from this so the
 *  eventual subdomain cutover is a hostname check (see App.tsx), not a code
 *  migration. */
export const CONSOLE_BASE = window.location.hostname.startsWith("console.") ? "" : "/console";
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -20`
Expected: no new errors (nothing imports this yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/console/base.ts
git commit -m "feat(frontend): add console/base.ts — CONSOLE_BASE constant for subdomain readiness"
```

---

## Task 17: Simplify `console/area.ts` to admin-only + `CONSOLE_BASE`

**Files:**
- Modify: `frontend/src/sites/console/area.ts`

**Interfaces:**
- Consumes: `CONSOLE_BASE` from Task 16.
- Produces: `Area` (now just `"admin"`), `areasForRole`, `landingFor` — Task 18/19 use these; `landingFor` now returns `${CONSOLE_BASE}/admin/audit` or `${CONSOLE_BASE}/no-access`.

- [ ] **Step 1: Replace the entire file**

```ts
import { CONSOLE_BASE } from "./base";

/** Role → reachable console areas. `users.role` is single-valued server-side.
 *  Console is jobify-internal now — only "admin" ever reaches it; a recruiter
 *  or applicant signing in here lands on /no-access (recruiters have their
 *  own workspace at /employers). */
export type Area = "admin";

const AREAS_FOR_ROLE: Record<string, Area[]> = {
  admin: ["admin"],
};

export function areasForRole(role: string): Area[] {
  return AREAS_FOR_ROLE[role] ?? [];
}

/** Where a freshly-signed-in operator (or a wrong-role redirect) should land. */
export function landingFor(role: string): string {
  return areasForRole(role).length > 0 ? `${CONSOLE_BASE}/admin/audit` : `${CONSOLE_BASE}/no-access`;
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -40`
Expected: errors only where `console/session.tsx`'s re-export of `Area`/`areasForRole`/`landingFor` is consumed by files still using the old shape — none expected yet since this is a compatible narrowing (fewer union members, same function signatures). If any error appears, it will be in `ConsoleRoutes.tsx`/`Shell.tsx` (fixed next tasks).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/console/area.ts
git commit -m "refactor(frontend): simplify console/area.ts to admin-only, build paths from CONSOLE_BASE"
```

---

## Task 18: Simplify `console/components/Shell.tsx` to single-area

**Files:**
- Modify: `frontend/src/sites/console/components/Shell.tsx`

**Interfaces:**
- Consumes: `CONSOLE_BASE` from Task 16; `useSession`, `useSessionStore` from `console/session.tsx` (unchanged).
- Produces: `Shell` component, same export shape as before.

- [ ] **Step 1: Replace the entire file**

```tsx
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useSession, useSessionStore } from "../session";
import { ThemeToggle } from "../../../shared/theme/ThemeToggle";
import { IstClock } from "./bits";
import { CONSOLE_BASE } from "../base";

const NAV = [
  { to: `${CONSOLE_BASE}/admin/analytics`, idx: "00", label: "Analytics" },
  { to: `${CONSOLE_BASE}/admin/audit`, idx: "01", label: "Audit explorer" },
  { to: `${CONSOLE_BASE}/admin/users`, idx: "02", label: "User actions" },
  { to: `${CONSOLE_BASE}/admin/verification`, idx: "03", label: "Verification" },
];

export function Shell() {
  const { identity, client } = useSession();
  const { signOut } = useSessionStore();
  const { pathname } = useLocation();
  const crumb = pathname.split("/").filter(Boolean).join(" / ");

  return (
    <div className="shell">
      <nav className="rail">
        <div className="rail-brand">
          <div className="rail-lockup">
            {/* J-person mark only — the wordmark's letter counters would read as
                light fills on this dark rail; the solid mark stays crisp. */}
            <img src="/jobify-mark.svg" alt="Jobify" className="rail-mark" />
            <div className="wordmark">
              JOBIFY<em>//</em>CONSOLE
            </div>
          </div>
          <div className="k" style={{ marginTop: 4 }}>
            internal operations
          </div>
          <div style={{ marginTop: 8 }}>
            <ThemeToggle />
          </div>
        </div>

        <div className="rail-section">
          <span className="k">Moderation</span>
          {NAV.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => `rail-link${isActive ? " active" : ""}`}
            >
              <span className="idx num">{link.idx}</span>
              {link.label}
            </NavLink>
          ))}
        </div>

        <div className="rail-foot">
          <div className="row">
            <span className={`led ${client.mode === "live" ? "live" : "amber"}`} />
            <span className="k">{client.mode === "live" ? "live api" : "demo data"}</span>
          </div>
          <div className="dim" style={{ fontSize: 11, wordBreak: "break-all" }}>
            {identity.email ?? identity.id}
            <span className="chip" style={{ marginLeft: 8 }}>
              {identity.role}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <NavLink
              to={`${CONSOLE_BASE}/settings`}
              className={({ isActive }) => `btn sm ghost${isActive ? " active" : ""}`}
              style={{ flex: 1, justifyContent: "center" }}
            >
              Settings
            </NavLink>
            <button className="btn sm" onClick={signOut} style={{ flex: 1 }}>
              Log out
            </button>
          </div>
        </div>
      </nav>

      <div className="main">
        <header className="masthead">
          <span className="crumbs">
            console / <b>{crumb || "home"}</b>
          </span>
          <IstClock />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -40`
Expected: remaining errors confined to `ConsoleRoutes.tsx` (fixed next) and `pages/SignIn.tsx` (fixed in Task 19).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/console/components/Shell.tsx
git commit -m "refactor(frontend): simplify console Shell to single admin nav section, use CONSOLE_BASE"
```

---

## Task 19: Simplify `console/pages/SignIn.tsx` to admin-only copy

**Files:**
- Modify: `frontend/src/sites/console/pages/SignIn.tsx`

**Interfaces:**
- Consumes: `landingFor` from Task 17's `area.ts` (via `console/session.tsx`'s re-export, unchanged path).
- Produces: `SignIn` component — drops the `demoRole` admin/recruiter picker (console demo mode is now always admin).

- [ ] **Step 1: Replace the entire file**

```tsx
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
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -40`
Expected: remaining errors confined to `ConsoleRoutes.tsx` (fixed next task).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/console/pages/SignIn.tsx
git commit -m "refactor(frontend): admin-only copy in console SignIn, drop recruiter demo picker"
```

---

## Task 20: Simplify `console/ConsoleRoutes.tsx` — remove recruiter routes, use `CONSOLE_BASE`

**Files:**
- Modify: `frontend/src/sites/console/ConsoleRoutes.tsx`

**Interfaces:**
- Consumes: `CONSOLE_BASE` (Task 16), `Shell` (Task 18), `SignIn` (Task 19), `Settings`/`Analytics`/`AuditExplorer`/`UserActions`/`Verification` (unchanged), `areasForRole`/`SessionProvider`/`useSessionStore` from `console/session.tsx`.
- Produces: `ConsoleRoutes()` — every route path built from `CONSOLE_BASE`; recruiter routes and imports fully removed.

- [ ] **Step 1: Replace the entire file**

```tsx
import { Navigate, Outlet, Route } from "react-router-dom";
import { useEffect } from "react";
import type { ReactNode } from "react";
import "./styles/console.css";
import { Shell } from "./components/Shell";
import { Analytics } from "./pages/admin/Analytics";
import { AuditExplorer } from "./pages/admin/AuditExplorer";
import { UserActions } from "./pages/admin/UserActions";
import { Verification } from "./pages/admin/Verification";
import { Settings } from "./pages/Settings";
import { SignIn } from "./pages/SignIn";
import { CONSOLE_BASE } from "./base";
import { areasForRole, SessionProvider, useSessionStore } from "./session";

function RequireSession({ children }: { children: ReactNode }) {
  const { session } = useSessionStore();
  if (!session) return <Navigate to={`${CONSOLE_BASE}/signin`} replace />;
  return <>{children}</>;
}

/** Gate the admin subtree on role. Console is jobify-internal now — a
 *  recruiter or applicant who signs in here sees /no-access, never a
 *  redirect to /employers (recruiters have their own workspace already). */
function RequireAdmin() {
  const { session } = useSessionStore();
  if (session && areasForRole(session.identity.role).length === 0) {
    return <Navigate to={`${CONSOLE_BASE}/no-access`} replace />;
  }
  return <Outlet />;
}

function NoAccess() {
  const { session } = useSessionStore();
  return (
    <div className="content">
      <div className="headline">
        <h1>
          NO <span className="ghost">ACCESS</span>
        </h1>
        <div className="sub">
          <span className="flavor">
            This console is for jobify staff only. Your account
            {session ? ` (role: ${session.identity.role})` : ""} can&apos;t reach it.
          </span>
        </div>
      </div>
    </div>
  );
}

/** Session + CSS-scope wrapper for the console surface. */
function ConsoleLayout() {
  useEffect(() => {
    document.title = "JOBIFY // CONSOLE";
  }, []);
  return (
    <SessionProvider>
      <div className="atmosphere" />
      <div className="surface-console">
        <Outlet />
      </div>
    </SessionProvider>
  );
}

/** Console (jobify-internal admin ops) routes. Returned into the top <Routes>.
 *  Every path is built from CONSOLE_BASE so the whole subtree can remount at a
 *  different base (empty string, once served from console.jobify.com) with
 *  no other code changes — see base.ts. */
export function ConsoleRoutes() {
  return (
    <Route element={<ConsoleLayout />}>
      <Route path={`${CONSOLE_BASE}/signin`} element={<SignIn />} />
      <Route
        element={
          <RequireSession>
            <Shell />
          </RequireSession>
        }
      >
        {/* Account & settings — any signed-in admin, not further gated. */}
        <Route path={`${CONSOLE_BASE}/settings`} element={<Settings />} />
        <Route path={`${CONSOLE_BASE}/no-access`} element={<NoAccess />} />
        <Route element={<RequireAdmin />}>
          <Route path={`${CONSOLE_BASE}/admin/analytics`} element={<Analytics />} />
          <Route path={`${CONSOLE_BASE}/admin/audit`} element={<AuditExplorer />} />
          <Route path={`${CONSOLE_BASE}/admin/users`} element={<UserActions />} />
          <Route path={`${CONSOLE_BASE}/admin/verification`} element={<Verification />} />
        </Route>
      </Route>
      <Route path={`${CONSOLE_BASE}/*`} element={<Navigate to={`${CONSOLE_BASE}/signin`} replace />} />
    </Route>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1 | head -60`
Expected: remaining errors confined to `pages/admin/UserActions.tsx` (still has 2 hardcoded `/console/admin/audit` links — fixed next task). No errors about missing recruiter page imports (they were removed from this file's imports in this step).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sites/console/ConsoleRoutes.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): remove recruiter routes from ConsoleRoutes, build paths from CONSOLE_BASE

Console is jobify-internal (admin-only) now. Recruiter routes/pages live
at /employers instead (see EmployersRoutes.tsx).
EOF
)"
```

---

## Task 21: Update `console/pages/admin/UserActions.tsx` to use `CONSOLE_BASE`

**Files:**
- Modify: `frontend/src/sites/console/pages/admin/UserActions.tsx`

**Interfaces:**
- Consumes: `CONSOLE_BASE` from Task 16.

This is the last of the "3 files with hardcoded `/console/...` strings" the spec flagged for subdomain readiness (`ConsoleRoutes.tsx` and `Shell.tsx` done in Tasks 18/20).

- [ ] **Step 1: Add the import**

Add to the top of the file, alongside the existing imports:

```tsx
import { CONSOLE_BASE } from "../../base";
```

- [ ] **Step 2: Replace both hardcoded links**

Replace:
```tsx
          <Link to="/console/admin/audit">audit trail</Link>
```
with:
```tsx
          <Link to={`${CONSOLE_BASE}/admin/audit`}>audit trail</Link>
```

Replace:
```tsx
              <Link className="btn ghost sm" to={`/console/admin/audit?actor=${result.id}`}>
```
with:
```tsx
              <Link className="btn ghost sm" to={`${CONSOLE_BASE}/admin/audit?actor=${result.id}`}>
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors across the entire project.

Run: `grep -rn '"/console' frontend/src`
Expected: no output (confirms no hardcoded `/console/...` string literals remain anywhere).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/console/pages/admin/UserActions.tsx
git commit -m "refactor(frontend): use CONSOLE_BASE in UserActions links (subdomain readiness)"
```

---

## Task 22: Add the `console.*` hostname branch to `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `EmployersRoutes` (Task 14), `ConsoleRoutes` (Task 20).

- [ ] **Step 1: Replace the entire file**

```tsx
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { EmployersRoutes } from "./sites/employers/EmployersRoutes";
import { ConsoleRoutes } from "./sites/console/ConsoleRoutes";

// console.jobify.com serves ONLY the console subtree, mounted at the root path
// (CONSOLE_BASE resolves to "" there — see sites/console/base.ts). Every other
// hostname serves the employers surfaces, with /console/* still reachable as a
// path prefix during the transition before DNS cutover.
const isConsoleHost = window.location.hostname.startsWith("console.");

export function App() {
  return (
    <HashRouter>
      {/* HashRouter: static bundle, no server rewrites, tokens stay out of paths. */}
      <Routes>
        {isConsoleHost ? (
          <>
            {ConsoleRoutes()}
            <Route path="/" element={<Navigate to="/signin" replace />} />
          </>
        ) : (
          <>
            {EmployersRoutes()}
            {ConsoleRoutes()}
            {/* Applicant-facing web surface removed — the Flutter app is the applicant client.
                This app now serves employers (marketing + recruiter workspace) and console
                (jobify-internal admin ops) only. */}
            <Route path="/" element={<Navigate to="/employers" replace />} />
          </>
        )}
      </Routes>
    </HashRouter>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`
Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): mount console at root on a console.* hostname"
```

---

## Task 23: Update `frontend/README.md` and `frontend/CLAUDE.md`

**Files:**
- Modify: `frontend/README.md`
- Modify: `frontend/CLAUDE.md`

- [ ] **Step 1: Update `frontend/README.md`**

In the "Entry points" section, update the console row's dev entry URL from `http://localhost:5173/#/console/signin` to note it now hosts admin-only ops, and add a note about the employers workspace. Update the surface descriptions:

Replace:
```
| **console** (internal admin + recruiter ops) | `http://localhost:5173/#/console/signin` | `src/sites/console/ConsoleRoutes.tsx` | `/console` |
```
with:
```
| **console** (jobify-internal admin ops) | `http://localhost:5173/#/console/signin` | `src/sites/console/ConsoleRoutes.tsx` | `/console` |
```

Replace the bullet:
```
- **console** — entered at `/console/signin`; after sign-in, role-aware routing sends admins to `/console/admin/audit` and recruiters to `/console/recruiter`.
```
with:
```
- **console** — entered at `/console/signin`; jobify-internal admin ops only (audit trail, employer verification, user actions).
- **employers** (in addition to the marketing pages) — an authenticated recruiter workspace entered at `/employers/signin`; signed-in recruiters land on `/employers/dashboard` (jobs, applicants, team & invites, settings).
```

- [ ] **Step 2: Update `frontend/CLAUDE.md`**

Update the header description (line 3) — replace:
```
Load-bearing invariants for the web app: two route-prefixed surfaces under one HashRouter — `/employers` (recruiter marketing, `src/sites/employers`), `/console` (admin + recruiter ops, `src/sites/console`); shared transport/session/auth/env in `src/shared`. `/` redirects to `/employers`. Auto-loaded when working under `frontend/`. Dev/build/env reference is in `frontend/README.md`.
```
with:
```
Load-bearing invariants for the web app: two route-prefixed surfaces under one HashRouter — `/employers` (recruiter marketing + authenticated recruiter workspace, `src/sites/employers`), `/console` (jobify-internal admin ops only, `src/sites/console`); shared transport/session/auth/env in `src/shared`. `/` redirects to `/employers`. Auto-loaded when working under `frontend/`. Dev/build/env reference is in `frontend/README.md`.
```

Replace the removal note (line 5) — add a second sentence noting the 2026-07 recruiter-ops move:
```
**The applicant web surface (`src/sites/web`) was removed 2026-07** — the Flutter app (`app/`) is the applicant client. If a future task needs an applicant browser surface again, it's recoverable from git history, not to be rebuilt from scratch speculatively.

**Recruiter ops moved from `/console` to `/employers` (2026-07)** — console is jobify-internal (admin) only now; a recruiter should never reach it. Recruiter pages live at `src/sites/employers/pages/dashboard/`, with their own `session.tsx`/`api/client.ts`/`api/demo.ts` independent from console's. Console's routes/links are built from `CONSOLE_BASE` (`src/sites/console/base.ts`) rather than hardcoded `/console/...` strings, so it's ready to move to its own subdomain later.
```

- [ ] **Step 3: Commit**

```bash
git add frontend/README.md frontend/CLAUDE.md
git commit -m "docs(frontend): document the console/employers split and CONSOLE_BASE"
```

---

## Task 24: Final full build + manual smoke test

**Files:** none (verification only)

- [ ] **Step 1: Full typecheck + build**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...` with no TypeScript errors, no Vite warnings about unresolved imports.

- [ ] **Step 2: Sweep for stray references**

```bash
grep -rn "console/recruiter\|CONSOLE_URL\|DemoRole" frontend/src
```
Expected: no output.

```bash
grep -rn '"/console/' frontend/src/sites/console
```
Expected: no output (everything routes through `CONSOLE_BASE` now).

- [ ] **Step 3: Manual smoke test — start the dev server**

Run: `cd frontend && npm run dev` (leave running; use a separate terminal/tab for the checks below, or run in background and curl).

- [ ] **Step 4: Employers recruiter workspace (demo mode)**

Open `http://localhost:5173/#/employers/signin` in a browser. Confirm:
- The gate renders with "EMPLOYER WORKSPACE" branding (not "OPERATIONS CONSOLE").
- Click "Enter demo workspace" (Demo data mode, no token needed) → lands on `/employers/dashboard`.
- Dashboard shows tiles (open postings, closed, applicants, surfaced matches) and the "most active open postings" / "your employers" tables populated from the seeded fixtures.
- Nav to Jobs (`/employers/jobs`) — table renders, "+ New posting" opens the composer at `/employers/jobs/new` with a live preview panel.
- Nav to Team (`/employers/team`) — roster + invites render.
- Settings (`/employers/settings`) — shows recruiter email/role, theme toggle, log-out button works and returns to `/employers/signin`.

- [ ] **Step 5: Console admin ops (demo mode)**

Open `http://localhost:5173/#/console/signin`. Confirm:
- The gate renders with "OPERATIONS CONSOLE" branding and admin-only copy ("jobify staff only").
- No "recruiter" demo-role toggle is present (only Demo data / Live API mode tabs).
- Click "Enter demo console" → lands on `/console/admin/audit`.
- The rail nav shows only "Moderation" (Analytics, Audit explorer, User actions, Verification) — no "Recruiting" section.
- Nav to User actions, Analytics, Verification — all render as before.

- [ ] **Step 6: Cross-surface no-access check**

While signed into the console demo session, manually navigate the browser to `http://localhost:5173/#/employers/dashboard`. Confirm this does NOT show recruiter data (the employers surface has its own independent session — the console session doesn't carry over) — it should show the employers `SignIn` gate, since no employers-surface session exists yet.

- [ ] **Step 7: Marketing site CTAs**

Open `http://localhost:5173/#/employers`. Confirm:
- Masthead top-right button reads "Sign in" (not "Open the console") and clicking it navigates to `/employers/signin` in the same tab (no new tab — it's an in-app `<Link>` now, not `target="_blank"`).
- Footer "Access" column shows "Sign in" linking to the same place.
- Scroll to pricing — Starter "Start free" and Team "Choose Team" buttons both link to `/employers/signin`.
- Bottom CTA band "Sign in" button works.
- Visit `/employers/verify` — bottom CTA "Sign in" button works, heading reads "Get verified." (no "in the console").

- [ ] **Step 8: Hostname-readiness code check (no real subdomain exists yet, so this is a reasoning check, not a live browser test)**

Re-read `frontend/src/App.tsx` and `frontend/src/sites/console/base.ts` side by side and confirm by inspection:
- `isConsoleHost` is `false` for every hostname used in local dev (`localhost`, `127.0.0.1`) — so today's behavior (both `EmployersRoutes` and `ConsoleRoutes` mounted, `/` → `/employers`) is unchanged, which Steps 4–7 already exercised live.
- If `isConsoleHost` were `true` (i.e. hostname starts with `console.`), `CONSOLE_BASE` would independently resolve to `""` (same hostname check, in `base.ts`), so `ConsoleRoutes()`'s paths become `/signin`, `/admin/audit`, etc., and `App.tsx`'s `<Route path="/">` redirects to `/signin` — consistent, no dangling `/console` prefix anywhere in that branch.
- Optional deeper check if you want to exercise this live: add a temporary line to `/etc/hosts` (`127.0.0.1 console.jobify.local`), confirm Vite's dev server accepts arbitrary hosts (`vite.config.ts` — add `server.host: true` temporarily if needed), visit `http://console.jobify.local:5173/#/`, confirm it lands on the console sign-in with no `/console` prefix in the URL, then revert both changes. This is optional infra-simulation, not required to consider this task done.

- [ ] **Step 9: Stop the dev server, report results**

If every check in Steps 4–7 passes, the migration is functionally complete. If anything fails, treat it as a bug in the relevant task above (not a new task) — fix inline and re-run the affected smoke-test steps before committing.

- [ ] **Step 10: No commit for this task** (verification-only; nothing to stage).
