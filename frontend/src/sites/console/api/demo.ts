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
