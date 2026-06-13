import { ApiError } from "./client";
import type { JobifyClient } from "./client";
import type {
  AcceptResult,
  ApplicationListResponse,
  ApplicationRead,
  ConsentRead,
  EmployerRead,
  FeedItem,
  FeedResponse,
  JobDetailResponse,
  JobRead,
  MeResponse,
  MyInviteRead,
  NotificationListResponse,
  NotificationRead,
  SavedJobListResponse,
  SavedJobRead,
} from "./types";

/** Seeded in-memory backend so the applicant experience runs fully offline. */

const uuid = (() => {
  let n = 0;
  return () => `00000000-0000-4000-9000-${(++n).toString(16).padStart(12, "0")}`;
})();

const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();
const delay = () => new Promise((r) => setTimeout(r, 200 + Math.random() * 220));

const APPLICANT_ID = uuid();

interface Seed {
  employer: EmployerRead;
  job: JobRead;
  match: { total: number; vector: number; structured: number; fit: string; caveat: string };
}

function mk(
  employerName: string,
  verified: boolean,
  title: string,
  postedDaysAgo: number,
  total: number,
  vector: number,
  structured: number,
  ctc: [number, number] | null,
  exp: [number, number],
  locations: string[],
  fit: string,
  caveat: string,
  description: string,
): Seed {
  return {
    employer: { id: uuid(), name: employerName, verified },
    job: {
      id: uuid(),
      title,
      description,
      locations,
      min_exp_years: exp[0],
      max_exp_years: exp[1],
      ctc_min: ctc?.[0] ?? null,
      ctc_max: ctc?.[1] ?? null,
      status: "open",
      posted_at: daysAgo(postedDaysAgo),
      employer_verified: verified,
    },
    match: { total, vector, structured, fit, caveat },
  };
}

const SEEDS: Seed[] = [
  mk(
    "Meridian Analytics",
    true,
    "Senior Data Platform Engineer",
    2,
    0.91,
    0.88,
    0.95,
    [3_200_000, 4_500_000],
    [5, 9],
    ["Bengaluru", "Remote (IN)"],
    "Your Spark + Iceberg lakehouse work maps almost exactly onto how this team feeds its scoring pipelines.",
    "The band tops out a little below your stated expectation.",
    "We run the lakehouse that feeds every score Jobify ships.\n\nYou'll own Spark + Iceberg pipelines end to end, inherit a small and sharp platform, and work through a long queue of ideas with real autonomy. We care about correctness, observability, and the taste to know which abstraction to reach for.\n\nYou should be comfortable owning data contracts, partitioning strategy, and the difference between a 2-second query and a 2-second wait for a connection.",
  ),
  mk(
    "Karkhana Robotics",
    false,
    "Machine Learning Engineer — Matching",
    5,
    0.86,
    0.9,
    0.79,
    [2_800_000, 4_000_000],
    [3, 7],
    ["Bengaluru"],
    "Embeddings, ranking, and the explanation layer between them — the exact trio you've shipped twice before.",
    "This employer hasn't completed verification yet.",
    "Embeddings, ranking, and the explanation that sits between them.\n\npgvector in production, Gemini at the edges, and taste everywhere. You'll own the model that decides which roles surface and why — including the short, honest 'why this fits' line every applicant reads.\n\nWe'd rather ship a calibrated 0.86 with a caveat than a confident 0.99 we can't defend.",
  ),
  mk(
    "Lumen Health",
    true,
    "Backend Engineer (FastAPI)",
    8,
    0.83,
    0.81,
    0.86,
    [2_200_000, 3_200_000],
    [2, 5],
    ["Bengaluru", "Hybrid"],
    "Async SQLAlchemy and an audit trail you can stand behind — squarely in your wheelhouse.",
    "Healthcare data means a heavier compliance surface than you've described before.",
    "Async SQLAlchemy, Celery workers, and an audit trail you can stand behind.\n\nWe build clinical-adjacent tooling, so every write is audited and every export is consented. If you've ever wired an outbox, reasoned about idempotency, or chased a connection-pool ghost at 2am, you'll feel at home.",
  ),
  mk(
    "Tincan Studio",
    true,
    "Product Designer, Growth",
    11,
    0.78,
    0.72,
    0.85,
    [1_800_000, 2_600_000],
    [2, 6],
    ["Mumbai", "Hybrid"],
    "You sweat empty states and onboarding — which is most of what this role actually is.",
    "Heavier quantitative experimentation than your portfolio currently shows.",
    "Design the surfaces applicants meet first.\n\nYou'll own empty states, onboarding, and the moment a match explains itself. We measure carefully, but we design from taste first and validate second. Bring a point of view about how software should feel.",
  ),
  mk(
    "Ferrous Labs",
    false,
    "Embedded Firmware Engineer",
    3,
    0.74,
    0.7,
    0.79,
    [1_600_000, 2_400_000],
    [1, 4],
    ["Pune"],
    "Motor-controller bring-up and honest C — close to your last two roles.",
    "More on-site bench time than a remote-leaning candidate may want.",
    "Bring up motor controllers and write the C that keeps six-axis arms honest.\n\nBench time guaranteed. You'll work close to the metal, with oscilloscopes and real deadlines, on robots that move in the physical world.",
  ),
  mk(
    "Northwind Fintech",
    true,
    "Staff Engineer, Payments",
    6,
    0.7,
    0.66,
    0.76,
    [4_000_000, 6_000_000],
    [7, 12],
    ["Bengaluru", "Remote (IN)"],
    "Your ledger and idempotency depth is exactly what a payments core needs.",
    "Reach role — the seniority bar sits a notch above your current title.",
    "Own the ledger.\n\nDouble-entry correctness, idempotent retries, and reconciliation you can prove. This is a staff role: you'll set technical direction for payments and mentor a small team. We index hard on rigor.",
  ),
];

const FEED: FeedItem[] = SEEDS.map((s) => ({
  employer: s.employer,
  job: s.job,
  match: {
    id: uuid(),
    total_score: s.match.total,
    vector_score: s.match.vector,
    structured_score: s.match.structured,
    components: {
      title: Math.min(1, s.match.structured + 0.04),
      skills: s.match.vector,
      location: s.job.locations.some((l) => l.includes("Remote")) ? 0.95 : 0.7,
      experience: s.match.structured,
    },
    surfaced_at: s.job.posted_at,
    explanation: { fit: s.match.fit, caveat: s.match.caveat },
  },
}));

const byJobId = new Map(FEED.map((f) => [f.job.id, f]));

// mutable applicant state
const applications = new Map<string, ApplicationRead>(); // job_id → application
const savedJobs = new Map<string, SavedJobRead>(); // job_id → saved

// consent state — seeded from the backend ConsentScope defaults (db/models.py).
const CONSENT_DEFAULTS: ReadonlyArray<readonly [string, boolean]> = [
  ["email_transactional", true],
  ["email_marketing", false],
  ["in_app_notifications", true],
  ["whatsapp_notifications", false],
  ["sms_notifications", false],
  ["profile_visibility_recruiters", false],
  ["third_party_sharing_recruiters", false],
];
const consents = new Map<string, ConsentRead>(
  CONSENT_DEFAULTS.map(([scope, granted]) => [
    scope,
    { scope, granted, updated_at: daysAgo(7) },
  ]),
);

// --- in-app inbox -----------------------------------------------------------
// Seeded against the FEED employers so the cards read as real history. Newest
// first; one unread (read_at null), the rest already opened. The invite
// notification's payload.invite_id points at the live INVITE seed below, so the
// inbox card and the /invites screen agree.
const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();

const INVITE_ID = uuid();
const NW = SEEDS[5].employer; // Northwind Fintech (verified)
const MERIDIAN = SEEDS[0]; // Senior Data Platform Engineer
const LUMEN = SEEDS[2]; // Backend Engineer (FastAPI)

const notifications: NotificationRead[] = [
  {
    id: uuid(),
    kind: "employer_invite",
    channel: "in_app",
    status: "sent",
    payload: {
      employer_name: NW.name,
      role: "member",
      invite_id: INVITE_ID,
      employer_id: NW.id,
    },
    send_after: hoursAgo(3),
    sent_at: hoursAgo(3),
    read_at: null,
    created_at: hoursAgo(3),
  },
  {
    id: uuid(),
    kind: "application_received",
    channel: "email",
    status: "sent",
    payload: {
      job_title: MERIDIAN.job.title,
      employer_name: MERIDIAN.employer.name,
      application_id: uuid(),
      job_id: MERIDIAN.job.id,
    },
    send_after: hoursAgo(28),
    sent_at: hoursAgo(28),
    read_at: hoursAgo(26),
    created_at: hoursAgo(28),
  },
  {
    id: uuid(),
    kind: "application_received",
    channel: "email",
    status: "sent",
    payload: {
      job_title: LUMEN.job.title,
      employer_name: LUMEN.employer.name,
      application_id: uuid(),
      job_id: LUMEN.job.id,
    },
    send_after: hoursAgo(74),
    sent_at: hoursAgo(74),
    read_at: hoursAgo(70),
    created_at: hoursAgo(74),
  },
];

// --- employer invites (invitee side) ----------------------------------------
const invites = new Map<string, MyInviteRead>([
  [
    INVITE_ID,
    {
      id: INVITE_ID,
      employer_id: NW.id,
      employer_name: NW.name,
      role: "member",
      expires_at: new Date(Date.now() + 6 * 86_400_000).toISOString(),
      created_at: hoursAgo(3),
    },
  ],
]);

export class DemoClient implements JobifyClient {
  readonly mode = "demo" as const;

  async me(): Promise<MeResponse> {
    await delay();
    return {
      id: APPLICANT_ID,
      email: "you@example.in",
      role: "applicant",
      applicant: {
        id: APPLICANT_ID,
        full_name: "You",
        locations: ["Bengaluru"],
        notice_period_days: 60,
        current_ctc: "2800000",
        expected_ctc: "4000000",
        years_experience: "6",
      },
    };
  }

  async feed(cursor?: string): Promise<FeedResponse> {
    await delay();
    const start = cursor ? Number(cursor) : 0;
    const limit = 4;
    const items = FEED.slice(start, start + limit);
    return { items, next_cursor: start + limit < FEED.length ? String(start + limit) : null };
  }

  async job(jobId: string): Promise<JobDetailResponse> {
    await delay();
    const item = byJobId.get(jobId);
    if (!item) throw new ApiError(404, "job not found");
    return {
      job: item.job,
      employer: item.employer,
      match: item.match,
      application: applications.get(jobId) ?? null,
      saved_job: savedJobs.get(jobId) ?? null,
    };
  }

  async apply(jobId: string): Promise<ApplicationRead> {
    await delay();
    if (!byJobId.has(jobId)) throw new ApiError(404, "job_not_found");
    const now = new Date().toISOString();
    const existing = applications.get(jobId);
    const app: ApplicationRead = {
      id: existing?.id ?? uuid(),
      job_id: jobId,
      status: "applied",
      source: "web",
      created_at: existing?.created_at ?? now,
      updated_at: now,
    };
    applications.set(jobId, app);
    return app;
  }

  async withdraw(applicationId: string): Promise<ApplicationRead> {
    await delay();
    const entry = [...applications.values()].find((a) => a.id === applicationId);
    if (!entry) throw new ApiError(404, "application_not_found");
    const updated = { ...entry, status: "withdrawn", updated_at: new Date().toISOString() };
    applications.set(entry.job_id, updated);
    return updated;
  }

  async save(jobId: string): Promise<SavedJobRead> {
    await delay();
    if (!byJobId.has(jobId)) throw new ApiError(404, "job_not_found");
    const now = new Date().toISOString();
    const saved: SavedJobRead = {
      id: savedJobs.get(jobId)?.id ?? uuid(),
      job_id: jobId,
      created_at: savedJobs.get(jobId)?.created_at ?? now,
      updated_at: now,
    };
    savedJobs.set(jobId, saved);
    return saved;
  }

  async unsave(jobId: string): Promise<void> {
    await delay();
    savedJobs.delete(jobId);
  }

  async applications(): Promise<ApplicationListResponse> {
    await delay();
    const items = [...applications.values()]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map((application) => {
        const item = byJobId.get(application.job_id)!;
        return { application, job: item.job, employer: item.employer };
      });
    return { items, next_cursor: null };
  }

  async saved(): Promise<SavedJobListResponse> {
    await delay();
    const items = [...savedJobs.values()]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map((saved_job) => {
        const item = byJobId.get(saved_job.job_id)!;
        return { saved_job, job: item.job, employer: item.employer };
      });
    return { items, next_cursor: null };
  }

  async getConsents(): Promise<ConsentRead[]> {
    await delay();
    return [...consents.values()].sort((a, b) => a.scope.localeCompare(b.scope));
  }

  async setConsent(scope: string, granted: boolean): Promise<ConsentRead> {
    await delay();
    if (!consents.has(scope)) throw new ApiError(422, "unknown consent scope");
    const row: ConsentRead = { scope, granted, updated_at: new Date().toISOString() };
    consents.set(scope, row);
    return row;
  }

  async dsrExport(): Promise<unknown> {
    await delay();
    const me = await this.me();
    return {
      version: "1",
      exported_at: new Date().toISOString(),
      exported_for_user_id: me.id,
      user: { id: me.id, email: me.email, role: me.role, created_at: daysAgo(120) },
      applicant: me.applicant,
      resumes: [
        {
          id: uuid(),
          status: "parsed",
          original_filename: "resume.pdf",
          content_type: "application/pdf",
          created_at: daysAgo(118),
        },
      ],
      applications: [...applications.values()].map((a) => ({ ...a })),
      saved_jobs: [...savedJobs.values()].map((s) => ({ ...s })),
      matches: FEED.slice(0, 3).map((f) => ({
        id: f.match.id,
        job_id: f.job.id,
        total_score: f.match.total_score,
        surfaced_at: f.match.surfaced_at,
      })),
      user_consents: [...consents.values()].map((c) => ({ ...c })),
      audit_history: [
        { action: "auth.signed_in", created_at: daysAgo(2) },
        { action: "user.dsr_export_requested", created_at: new Date().toISOString() },
      ],
      redactions: [
        {
          table: "refresh_tokens",
          reason: "Session secrets are never exported — they would let a holder impersonate you.",
        },
      ],
      notes: ["This is a demo envelope. The live API returns every row tied to your account."],
    };
  }

  async dsrDelete(): Promise<unknown> {
    await delay();
    return {
      section_counts: {
        applications: applications.size,
        saved_jobs: savedJobs.size,
        resumes: 1,
        matches: 3,
        user_consents: consents.size,
        oauth_identities: 1,
        notifications: notifications.length,
      },
      warnings: [],
    };
  }

  async notifications(cursor?: string): Promise<NotificationListResponse> {
    await delay();
    const start = cursor ? Number(cursor) : 0;
    const limit = 10;
    const ordered = [...notifications].sort((a, b) => b.created_at.localeCompare(a.created_at));
    const items = ordered.slice(start, start + limit).map((notification) => ({ notification }));
    const next = start + limit < ordered.length ? String(start + limit) : null;
    return { items, next_cursor: next };
  }

  async markNotificationRead(notificationId: string): Promise<NotificationRead> {
    await delay();
    const row = notifications.find((n) => n.id === notificationId);
    if (!row) throw new ApiError(404, "notification not found");
    // Idempotent — keep the first read_at if already opened (mirrors the backend).
    row.read_at = row.read_at ?? new Date().toISOString();
    return { ...row };
  }

  async myInvites(): Promise<MyInviteRead[]> {
    await delay();
    const now = Date.now();
    return [...invites.values()]
      .filter((i) => new Date(i.expires_at).getTime() > now) // lazy expiry, like the API
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  async acceptInvite(inviteId: string): Promise<AcceptResult> {
    await delay();
    const invite = invites.get(inviteId);
    // A non-pending invite uniform-404s in the API; here a consumed invite is
    // simply gone from the map.
    if (!invite) throw new ApiError(404, "not found");
    if (new Date(invite.expires_at).getTime() <= Date.now()) {
      invites.delete(inviteId);
      throw new ApiError(410, "invite_expired");
    }
    invites.delete(inviteId);
    return { employer_id: invite.employer_id, role: invite.role, status: "accepted" };
  }

  async declineInvite(inviteId: string): Promise<AcceptResult> {
    await delay();
    const invite = invites.get(inviteId);
    if (!invite) throw new ApiError(404, "not found");
    invites.delete(inviteId);
    return { employer_id: invite.employer_id, role: invite.role, status: "revoked" };
  }
}
