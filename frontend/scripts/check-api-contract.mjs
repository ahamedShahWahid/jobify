import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const snapshotPath = fileURLToPath(
  new URL("../../tests/unit/openapi_snapshot.json", import.meta.url),
);
const schemas = JSON.parse(readFileSync(snapshotPath, "utf8")).components.schemas;

const clientContract = {
  AuditAnalyticsRead: [
    "action_counts", "activity", "distinct_actors", "last_24h", "role_counts",
    "span_end", "span_start", "system_events", "total_events",
  ],
  AdminEmployerRead: [
    "created_at", "gst", "id", "name", "reason", "reviewed_at", "status",
  ],
  CountBucketRead: ["count", "key"],
  DayBucketRead: ["count", "day"],
  JobRead: [
    "ctc_max", "ctc_min", "description", "employer_verified", "id",
    "locations", "max_exp_years", "min_exp_years", "posted_at", "status", "title",
  ],
  RecruiterJobRow: [
    "applicant_count", "ctc_max", "ctc_min", "description", "employer_verified",
    "id", "locations", "max_exp_years", "min_exp_years", "posted_at", "status",
    "surfaced_match_count", "title",
  ],
  ApplicantOfJobRow: [
    "applicant_id", "application_id", "applied_at", "display_name", "email",
    "match_explanation", "match_score", "status",
  ],
  ApplicantsOfJobPage: ["items", "next_cursor"],
  MemberRead: ["added_at", "display_name", "email", "role", "user_id"],
  InviteRead: [
    "created_at", "email", "employer_id", "expires_at", "id",
    "invited_by_user_id", "role", "status",
  ],
};

for (const [schemaName, expected] of Object.entries(clientContract)) {
  const schema = schemas[schemaName];
  if (!schema) throw new Error(`OpenAPI schema missing: ${schemaName}`);
  const actual = Object.keys(schema.properties ?? {}).sort();
  const wanted = [...expected].sort();
  if (JSON.stringify(actual) !== JSON.stringify(wanted)) {
    throw new Error(
      `${schemaName} drifted.\nExpected: ${wanted.join(", ")}\nActual:   ${actual.join(", ")}`,
    );
  }
}

console.log("OpenAPI contract matches the React clients.");
