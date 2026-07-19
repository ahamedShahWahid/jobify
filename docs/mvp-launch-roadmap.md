# MVP Launch Roadmap — pending work vs BRD (approved 2026-07-19)

Gap analysis of `docs/prd/KPA_Enhanced_BRD_v1_1.pdf` + `IMPLEMENTATION_SPEC.md`
against the shipped codebase, sequenced toward MVP launch. Approved by Ahamed
2026-07-19. Supersedes nothing — the BRD stays the scope source of truth; this
doc records **what remains and in what order**.

**Sequencing logic:** two acceptance criteria (match relevance ≥ 75 %, p95
≤ 400 ms) can only be *measured*, not rushed — one needs user feedback
accumulating over calendar time, the other a deployed environment. Clock-starter
items go first; the deploy long-pole starts mid-sequence; externally-gated items
run as parallel tracks off the critical path.

## Already shipped (BRD features verified in code)

- Applicant loop: resume upload → parse (library/regex) → embed (Gemini) →
  hybrid match → feed with scores → apply / track / save, via durable outbox.
- Match explanations (templated + LLM explainer), resume review + job
  preferences, profile edit.
- Recruiter: jobs CRUD, candidate inbox + stages, team invites, self-serve
  employer sign-up (Google auth — same service as applicants).
- Admin: suspend/unsuspend, audit-log viewer, analytics, employer verification.
- DPDP: consents, DSR export + delete with contract-pin tests.
- Notifications substrate: outbox + beat sweep, SES + logging email channels.
- Hardening: rate limiting, protected /metrics, OpenAPI snapshot pin, S3 storage.

## Critical path

| # | Slice | Size | Acceptance criterion served |
|---|-------|------|-----------------------------|
| 1 | **Match feedback capture + admin Match QA** — thumbs up/down on surfaced matches, admin QA view. New table ⇒ wire into DSR export/delete + contract-pin test. | S–M | Match relevance ≥ 75 % (starts the data clock — highest cost of delay) |
| 2 | **Push notifications (FCM)** — device-token table (⇒ DSR wiring), FCM channel adapter beside SES, Flutter integration. | M–L | Core BRD applicant feature ("notifies the applicant when high-quality matches appear") |
| 3 | **LLM resume parsing** — Gemini impl behind the existing parser Protocol (`integrations/parser`), library parser as fallback, gold-dataset growth, F1 gate 0.85 → 0.90. | M | Parse F1 ≥ 0.90 |
| 4 | **P5 launch phase** — pick deploy target (ap-south-1-adjacent: Fly BOM / Render SIN / EC2), containerize, hosted non-prod, load test, security review, Lighthouse pass. | L | p95 ≤ 400 ms · zero P0/P1 · re-verify 10-min first match |
| 5 | **Hindi i18n** (spec §3.7) — not acceptance-gated; candidate to slip post-launch. | M–L | — |

## Deferred (decided 2026-07-19)

- **Admin TOTP MFA** — deferred. BRD names it under Security & Compliance, so
  the step-4 security review must log it as an accepted-risk exception, not a
  P1, or the "zero P0/P1" gate contradicts itself.
- **Apple Sign-In + phone-OTP** — deferred; **Google is the sole auth provider
  for both applicant and recruiter** (already true in code). ⚠️ App Store
  guideline 4.8 requires Sign in with Apple alongside Google — iOS submission
  is blocked until Apple Sign-In ships; launch web + Android first.
- **WhatsApp channel** — until BSP selected (spec §14 #5).
- **Recruiter billing** — v1.1 (spec §1).
- **Job ingestion + admin source monitoring** — gated on legal review (BRD Next
  Step #1); parallel track when it clears.

## Acceptance-criteria coverage

| BRD criterion | Covered by |
|---|---|
| First match ≤ 10 min | shipped — re-verify under load (step 4) |
| Parse F1 ≥ 0.90 | step 3 |
| Match relevance ≥ 75 % | step 1 + calendar time (~500 ratings) |
| p95 ≤ 400 ms | step 4 |
| Consent/export/delete functional | done |
| Zero open P0/P1 | step 4 (with MFA logged as accepted risk) |
