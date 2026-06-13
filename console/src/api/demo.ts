import type { ConsoleClient } from "./client";
import { ApiError } from "./client";
import type {
  AdminUserRead,
  ApplicantOfJobRow,
  ApplicantsOfJobPage,
  AuditLogFilters,
  AuditLogListResponse,
  AuditLogRead,
  EmployerRead,
  EmployerVerificationPage,
  EmployerVerificationRow,
  EmployerVerificationStatus,
  InviteRead,
  JobCreate,
  JobPatch,
  JobRead,
  MeResponse,
  MemberRead,
  RecruiterJobRow,
  RecruiterJobsPage,
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

const members = new Map<string, MemberRead[]>([
  [
    employers[0].id,
    [
      {
        user_id: ME_ID,
        email: "ops@jobify.in",
        display_name: "Console Operator",
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
        email: "ops@jobify.in",
        display_name: "Console Operator",
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
  if (
    p.ctc_min != null &&
    p.ctc_max != null &&
    p.ctc_max < p.ctc_min
  )
    throw new ApiError(422, "ctc_max must be >= ctc_min");
}

// ---- the client -------------------------------------------------

export type DemoRole = "admin" | "recruiter";

export class DemoClient implements ConsoleClient {
  readonly mode = "demo" as const;

  // The seeded operator (ME_ID) is both an admin and an employer owner; the role
  // returned here decides which area the role-guards admit, so the demo can
  // explore either side without contradicting the backend's single-role model.
  constructor(private readonly role: DemoRole = "admin") {}

  async me(): Promise<MeResponse> {
    await delay();
    return { id: ME_ID, email: "ops@jobify.in", role: this.role, applicant: null };
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
