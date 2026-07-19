# Application stages — closing the apply loop for applicants

**Date:** 2026-07-19 · **Status:** approved · **Origin:** "make the app more
useful for the applicant" brainstorm; attacks the BRD problem statement
"Low application visibility" directly.

## Why

Today an application is a black hole: `ApplicationStatus` is only
`applied`/`withdrawn`, recruiter hiring stages were deferred at P3.0 and never
shipped, so recruiters can view candidates but not move them through a
pipeline — and the applicant never learns anything after tapping Apply. This
slice gives recruiters a stage pipeline and applicants a visible, notified
progress timeline.

Decisions locked with Ahamed 2026-07-19:

1. **Scope split:** this spec = the apply loop only. Feed filters/search is
   slice B with its own spec → plan cycle afterwards.
2. **Rejection UX = honest + notified.** The applicant's timeline shows "Not
   selected" and a notification is sent, same as positive changes. Copy stays
   neutral: "The employer moved forward with other candidates."

## Storage decision

**Chosen: approach A — `applications.stage` column + `application_stage_events`
history table.** Current-state queries (recruiter candidate list, applicant
applications list) read the cheap column; the events table powers the
applicant's timeline — the emotional payoff of the slice ("Shortlisted Jul 12 →
Interview Jul 18"), which a bare current-stage chip cannot deliver.
Rejected alternatives: column-only (loses the journey view), event-sourced
derivation (lateral-join cost on every list for no user-visible gain).

## Data model

Migration 0026:

- `applications.stage` — varchar(16) + CHECK
  `stage IN ('applied','shortlisted','interview','offer','hired','rejected')`,
  NOT NULL, server default `'applied'`; backfill existing rows to `'applied'`
  (the default covers it — no data migration needed beyond the column add).
  New `ApplicationStage` StrEnum at the boundary (no native PG enum — house
  precedent).
- New table `application_stage_events`: `id` (UuidPK), `application_id` FK →
  `applications.id` (`ondelete=CASCADE`), `from_stage` varchar(16) NOT NULL,
  `to_stage` varchar(16) NOT NULL (both CHECK-constrained to the same
  vocabulary), `actor_user_id` FK → `users.id` (`ondelete=SET NULL`, nullable —
  survives DSR like audit rows), `created_at`/`updated_at`/`deleted_at` per
  house soft-delete convention (rows are append-only in practice; live reads
  still filter `deleted_at IS NULL`). Index
  `(application_id, created_at DESC) WHERE deleted_at IS NULL`.

**Relationship to `status`:** `status` stays the applicant-owned lifecycle
(`applied`/`withdrawn`); `stage` is the recruiter-owned pipeline. A withdrawal
freezes the stage (no reset). Re-apply after withdraw (which reuses the row)
resets `stage` to `'applied'` and writes a stage event `(<old> → applied,
actor = the applicant's user)` so the timeline reflects the restart.

**DSR:** both are application-linked, not directly PII-bearing.
`application_stage_events` joins the **export-only** class (exported under the
user's applications history; KEPT on delete, like `applications` — anonymized
by the applicant tombstone, `actor_user_id` nulled by FK). Update
`_EXPORT_ONLY_TABLES` + export builder + the coverage/top-level pins.

## Transition rules

- Recruiter may set any stage in
  `{shortlisted, interview, offer, hired, rejected}` — free movement between
  them (mis-click corrections beat forward-only purity). `applied` is not a
  recruiter-settable target (only re-apply resets to it).
- Same-stage PATCH = 200 no-op: no event, no notification, no audit row.
- Guards, in the house error-ladder order: 401 → 403 (not a recruiter) →
  404 uniform (application not found / not owned by a job of the caller's
  employer — single JOIN via `EmployerUser`, never leak existence) →
  409 `application_withdrawn` (status = withdrawn) → 422 (bad stage value,
  Pydantic `Literal`).
- Every real transition, in ONE transaction: structlog
  (`recruiter.application-stage-changed`) → `audit_log()` (new reserved slug
  `application.stage_changed`, actor = recruiter) → stage event row →
  notification outbox row. Consistent with the "structlog FIRST, audit_log
  SECOND, then side-effect" rule.

## Notifications

- Outbox `Notification` kind `application_stage_changed`, recipient = the
  applicant's user, payload `{application_id, job_id, job_title,
  employer_name, stage}`. Written in the transition transaction; dispatched by
  the existing `sweep_notifications` beat task; consent-gated at dispatch as
  today (email channel now — FCM push inherits automatically when roadmap
  slice 2 lands).
- Sent for EVERY transition including `rejected` (decision #2). Copy per
  stage; `rejected` uses the neutral line above. `hired` copy is celebratory.
- The applicant notifications inbox renders the new kind (Flutter).

## API

- **`PATCH /v1/jobs/{job_id}/applications/{application_id}/stage`**
  body `{"stage": "shortlisted"|"interview"|"offer"|"hired"|"rejected"}` →
  200 with the updated recruiter-side application row (incl. `stage`).
  Recruiter-only (membership via the existing `EmployerUser` join helpers).
- **Applicant reads gain `stage`:** `ApplicationRead` (applications list),
  `JobDetailApplicationRead` (job detail). Wire-shape pins + Flutter DTOs
  updated in lockstep.
- **`GET /v1/applications/{application_id}/timeline`** (applicant, owner-only,
  uniform 404) → `{items: [{from_stage, to_stage, created_at}]}` ordered
  ascending. Actor identity is NOT exposed to the applicant.
- **Recruiter candidate list** (`GET /v1/jobs/{id}/applicants`) rows gain
  `stage`.
- OpenAPI snapshot regenerated; `frontend/scripts/check-api-contract.mjs`
  pinned for the employers-surface shapes it consumes.

## Clients

- **Flutter applicant:** stage chip on `ApplicationsScreen` rows (colour
  semantics: neutral for applied/shortlisted/interview, positive for
  offer/hired, muted for rejected — follow the design system; rejected is
  "Not selected"); job detail's application section shows the timeline
  (fetched from the new endpoint when the application section renders — its
  own provider, UI gated on the full `AsyncValue` per house rules; error state
  degrades to the current-stage chip alone);
  notifications inbox renders `application_stage_changed` entries. New
  `ApplicationStage` wire enum with `unknown` sentinel (never serializes) +
  fixture round-trip pin.
- **Flutter recruiter:** stage action menu (popup) per candidate row in
  `job_applicants_screen.dart`, showing current stage and the 5 targets;
  optimistic update with error snackbar + revert.
- **Web employers:** stage badge + dropdown per row in
  `pages/dashboard/Applicants.tsx`; TS types extended; `DemoClient` fixtures
  updated (build fails until it implements the new method — by design).

## Error handling

- Withdrawn application → 409 with a distinct slug so both recruiter UIs show
  "Candidate withdrew" rather than a generic failure.
- Stage PATCH races (two recruiters): last-write-wins on the column; both
  events recorded — acceptable, the timeline stays truthful.
- Notification write failures roll back the whole transition (single txn) —
  no silent stage change without a queued notification.
- Timeline endpoint owner check: applicant resolved from token, never URL.

## Testing

- **Integration:** transition matrix (each guard + no-op + free movement),
  withdrawn 409, re-apply stage reset + event, notification row content +
  consent gating via the existing sweep tests' pattern, timeline order +
  owner-only 404, recruiter list carries `stage`, DSR export includes events /
  delete keeps them, wire-shape pins.
- **Flutter:** widget tests for the applicant stage chip + timeline render +
  recruiter stage menu (fakes extended); DTO fixture pins incl. enum
  round-trip.
- **Frontend:** `npm run build` + contract-pin script.
- CI verbatim commands per root `CLAUDE.md`.

## Out of scope

- Feed filters/search (slice B, next spec).
- Time-in-stage analytics, stage SLAs, applicant "nudge recruiter" actions.
- Interview scheduling, offer letters, messaging.
- Push channel (roadmap slice 2 — this slice's notifications ride email now).
