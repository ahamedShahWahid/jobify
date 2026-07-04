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
