# KPA — Implementation Spec v0.2

**Source of truth for product scope:** `~/Downloads/KPA_Enhanced_BRD_v1_1.pdf` (BRD/PRD v1.1, dated 2026-05-15).
**This document:** how we build it. Owner: Ahamed. Status: MVP-first draft.

> Frontend decision (overrides BRD): **Flutter for mobile + web from a single Dart codebase.** Next.js is out of scope. A separate static/SSR surface for SEO-sensitive pages is an open decision (see §14).

> **MVP-first sequencing (v0.2 change):** the goal of the next several plans is a *working MVP*, not the production-grade runtime described in §11. Until launch, dev runs locally on Homebrew Postgres + `uvicorn`; Docker, EKS, Helm, ArgoCD, ECR, and Terraform are explicitly **deferred**. §11 now describes both the MVP runtime and the post-MVP scale path; §13 sequences toward the MVP shape first. Pick the deploy target in P5, not earlier.

---

## 1. Scope

In scope for MVP:
- Applicant: signup, resume upload + parse, profile, job feed with match scores, match explanations, notifications, application tracking, saved jobs.
- Recruiter: signup, job post create/edit, candidate inbox per job, match scores per candidate, basic analytics.
- Admin: source monitoring, moderation queue, match QA, audit log viewer, consent/export/delete tooling.
- Cross-cutting: DPDP-aligned consent and data subject flows, OAuth2 auth, MFA for admins.

Explicitly **out** of MVP:
- Recruiter billing / paid plans (BRD lists it but acceptance criteria do not gate on it — defer to v1.1).
- WhatsApp notifications (channel adapter scaffolded but live integration deferred — see §6.4).
- Programmatic job aggregation from third-party boards (pending legal review per BRD Next Step #1 — see §14).

---

## 2. Architecture overview

```
                          ┌────────────────────────────┐
                          │  Flutter app (iOS/Android/ │
                          │  web; one Dart codebase)   │
                          └─────────────┬──────────────┘
                                        │ HTTPS / JSON
                                        ▼
                          ┌────────────────────────────┐
                          │  CDN  →  Load balancer     │
                          │  (post-MVP; see §11)       │
                          └─────────────┬──────────────┘
                                        ▼
                          ┌────────────────────────────┐
                          │  FastAPI — REST API        │
                          │  Async (uvicorn workers)   │
                          └──┬───────┬─────────┬───────┘
                             │       │         │
              ┌──────────────┘       │         └──────────────┐
              ▼                      ▼                        ▼
      ┌──────────────┐       ┌──────────────┐         ┌──────────────┐
      │  Postgres    │       │  Redis       │         │  Object      │
      │  + pgvector  │       │  cache +     │         │  storage     │
      │              │       │  broker      │         │  (S3 / local)│
      └──────────────┘       └──────┬───────┘         └──────────────┘
                                    │
                                    ▼
                          ┌────────────────────────────┐
                          │  Celery workers            │
                          │  - parse  - ingest         │
                          │  - embed  - score          │
                          │  - notify - export/delete  │
                          └─────────────┬──────────────┘
                                        ▼
                          ┌────────────────────────────┐
                          │  External: LLM provider,   │
                          │  email (SES), push (FCM/   │
                          │  APNs), WhatsApp (later)   │
                          └────────────────────────────┘
```

**Sync vs async boundary:** the API is synchronous-feeling — anything that takes more than ~200 ms (resume parse, scoring, LLM calls, ingestion) is offloaded to Celery and surfaced via polling endpoints + push notifications. The Flutter client uses optimistic UI + status streams (see §3.5).

---

## 3. Frontend — Flutter (mobile + web, single codebase)

### 3.1 Project layout

```
app/
  lib/
    main.dart                   # entry, env bootstrap, error zone
    app.dart                    # MaterialApp.router, theming, locale
    core/
      config/                   # env, feature flags, build flavors
      network/                  # Dio client, interceptors, error mapping
      auth/                     # token store, refresh, MFA flows
      result/                   # Result<T,E> + failure model
      analytics/                # event sink (abstract; impl per flavor)
    features/
      onboarding/               # signup, resume upload, consent
      profile/                  # applicant profile editor
      feed/                     # match feed, filters, why-this-fits
      job_detail/
      applications/             # tracking
      saved/
      recruiter_jobs/
      recruiter_inbox/
      admin/                    # gated by role claim
      notifications/            # in-app + system push handling
    shared/
      ui/                       # design system: tokens, atoms, components
      widgets/                  # cross-feature widgets
    routing/                    # go_router config, guards, deep links
  test/                         # widget + golden + unit
  integration_test/             # e2e flows on device/web
```

Three build flavors: `dev`, `staging`, `prod`. Web build is gated behind same flavor (`flutter build web --dart-define=FLAVOR=...`).

### 3.2 State management

`flutter_riverpod` for app state. Rationale: testable without `BuildContext`, supports async providers natively (matches our polling/streaming needs), and the codegen variant (`riverpod_generator`) gives compile-time-safe DI without a heavy runtime container. Alternative considered: `bloc` — heavier ceremony for this app's data-fetch heavy shape.

### 3.3 Routing

`go_router` with role-based guards. Same routes work on mobile and web (deep links + URL bar). The recruiter and admin shells are separate top-level routes (not just tabs) so we can split-bundle if web app size becomes a concern.

### 3.4 API client

`dio` with interceptors:
- Auth: attach access token; on 401, attempt refresh, queue and retry pending requests.
- Trace: send `X-Request-Id` (uuid v4 per request) — server echoes it; used for support tickets.
- Telemetry: timing per endpoint, emit to analytics sink.
- Retry: idempotent GETs only, exponential backoff capped at 3 attempts.

OpenAPI codegen from FastAPI's `/openapi.json` produces typed Dart clients. CI fails if generated client diverges from spec.

### 3.5 Async UX patterns

For long-running server work (resume parse, first match batch):
- POST returns `202 Accepted` with `{ job_id, status_url }`.
- Client subscribes to `GET /jobs/{job_id}/status` via polling (1 s → backoff to 5 s) for foreground operations.
- Background completion arrives via FCM push (mobile) / web push (web), which the client uses to invalidate the appropriate Riverpod providers.

### 3.6 Web specifics

- Flutter web uses CanvasKit on desktop, HTML renderer on mobile-web (size-tuned).
- Service worker enabled for offline-resilient asset cache; data is not cached offline in MVP.
- Lighthouse target: TTI < 4 s on 4G; bundle split per top-level route via deferred imports.
- **SEO is *not* served by the Flutter web app.** Public job and employer pages need a separate pre-rendered surface — see §14.

### 3.7 Internationalization

`flutter_localizations` + ARB files. MVP languages: English + Hindi. Numbers/dates via `intl`. Right-to-left not needed.

---

## 4. Backend — FastAPI

### 4.1 Module layout

```
api/
  pyproject.toml                # uv-managed; ruff, mypy, pytest
  src/kpa/
    main.py                     # FastAPI app factory
    settings.py                 # pydantic-settings; env-driven
    deps.py                     # request-scoped deps (db, current user)
    middleware/                 # request_id, logging, error handler
    auth/                       # OAuth2 token verify, role claims, MFA
    domain/
      applicants/
      employers/
      jobs/
      resumes/
      matches/
      applications/
      notifications/
      audit/
      consent/
    db/
      models.py                 # SQLAlchemy 2.x declarative
      session.py                # async engine, R/W routing
      migrations/               # alembic
    workers/
      celery_app.py
      tasks/parse.py
      tasks/ingest.py
      tasks/embed.py
      tasks/score.py
      tasks/notify.py
      tasks/dsr.py              # data subject requests (export/delete)
    integrations/
      llm/                      # interface + provider impls (see §7)
      embeddings/
      email_ses.py
      push_fcm.py
      whatsapp_stub.py
      storage_s3.py
    observability/               # logging, metrics, tracing
  tests/
    unit/
    integration/
    contract/                    # OpenAPI snapshot tests
```

### 4.2 Conventions

- Python 3.12. `uv` for env + dep management. `ruff` (lint+format), `mypy --strict` on `src/kpa/domain/**`.
- SQLAlchemy 2.x async sessions; never block in request handlers.
- Pydantic v2 for I/O models. **Never** reuse SQLAlchemy models as response schemas — separate `*Read` / `*Create` / `*Update` Pydantic models per resource.
- All handlers `async def`. CPU-bound work goes to Celery, never to the request thread.
- Settings via env only (12-factor). `pydantic-settings` validates at startup; the app refuses to boot on missing required vars.

### 4.3 Logging (carries over from the user's global standards)

- Plain-text logback-style format via `structlog` rendered as key=value (compatible with Fluent Bit → Elasticsearch). No JSON in pod stdout unless Fluent Bit is reconfigured.
- MDC equivalents bound per request: `request_id`, `trace_id`, `user_id`, `tenant_id` (here = employer_id for recruiter routes), `path`, `method`.
- PII masking helper for email/phone/aadhaar; resumes never logged in raw form.
- No method entry/exit logs. `[PERF]` prefix for timing logs.

---

## 5. Data model (v0.1 sketch)

Postgres 16 on RDS. pgvector ≥ 0.7. One database, one schema (`kpa`). Soft delete via `deleted_at TIMESTAMPTZ NULL`; partial indexes `WHERE deleted_at IS NULL` on hot read paths.

Core tables (abridged — full DDL in alembic migrations):

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Auth principal | id, email, phone, role(applicant/recruiter/admin), mfa_enabled, created_at |
| `applicants` | Applicant profile | user_id, full_name, locations[], notice_period_days, current_ctc, expected_ctc, years_experience |
| `employers` | Employer org | id, name, gst, verified_at |
| `recruiters` | Recruiter user ↔ employer | user_id, employer_id, role |
| `resumes` | Uploaded resume + parse | id, applicant_id, s3_key, parse_status, parsed_json, parse_f1_estimate |
| `applicant_embeddings` | One embedding per resume version | applicant_id, resume_id, embedding vector(1536), model, created_at |
| `jobs` | Job posting | id, employer_id, title, description, locations[], min_exp, max_exp, ctc_min, ctc_max, status, posted_at |
| `job_embeddings` | One per job version | job_id, embedding vector(1536), model |
| `matches` | Applicant × Job score | applicant_id, job_id, vector_score, structured_score, total_score, explanation, surfaced_at |
| `applications` | Applicant-initiated | applicant_id, job_id, status, stage, source, created_at |
| `notifications` | Outbox | id, user_id, channel, payload, status, attempts, send_after |
| `consents` | Per scope: discovery, marketing, share-with-recruiter | user_id, scope, granted_at, revoked_at |
| `dsr_requests` | DPDP export/delete | user_id, kind(export/delete), status, artifact_s3_key |
| `audit_logs` | Append-only | actor_user_id, action, target_type, target_id, before_hash, after_hash, ts |
| `ingest_sources` | Approved source registry | id, name, kind(direct/api/feed), enabled, last_run_at |
| `ingest_runs` | One row per crawl/fetch | source_id, started_at, items_seen, items_kept, error_count |

<!-- Dim 1536 chosen per design doc `docs/superpowers/specs/2026-05-19-embedding-worker-design.md` (Gemini embedding-2's medium recommended dim). -->

Indexes worth calling out:
- `applicant_embeddings(vector)` and `job_embeddings(vector)`: HNSW (`vector_cosine_ops`), `m=16`, `ef_construction=64`. Recall/latency tuned in load test before launch.
- `matches(applicant_id, total_score DESC) WHERE deleted_at IS NULL` for the feed query.
- `jobs(status, posted_at DESC)` for the public listing.
- `notifications(status, send_after)` for the outbox poller.

R/W split: a single primary + one read replica via `AbstractRoutingDataSource`-equivalent (SQLAlchemy `bind` selection in `Session`). Read-only endpoints (`GET /feed`, `GET /jobs`) hit the replica; everything else hits primary. Engine swap is keyed off a `read_only: bool` annotation on the FastAPI dependency.

---

## 6. Core pipelines

### 6.1 Resume parse + embed

1. Client uploads to a presigned S3 URL → POSTs `{s3_key}` to `/applicants/me/resumes`.
2. API creates `resumes` row (status=`queued`) and dispatches `parse_resume.delay(resume_id)`.
3. Worker:
   - Pulls the file from S3.
   - Extracts text (PDF: `pypdf` → fallback `pdfminer.six`; DOCX: `python-docx`).
   - Calls the parser (see §7) to produce `parsed_json` matching a strict schema (name, contacts, experience[], education[], skills[], certifications[]).
   - Writes `parsed_json`, sets status=`parsed`.
4. After persisting `parsed_json` and setting `parse_status=parsed`, dispatches `embed_applicant.delay(applicant_id)` from Txn 3 (fire-and-forget under broad except — parse is durable if the broker is down). The embedding worker computes the vector asynchronously via the Gemini provider and upserts into `applicant_embeddings`.
5. Client polls `/resumes/{id}` and is also pushed via FCM when state changes.

Target: parse → first matches surfaced in **≤ 10 min** (BRD MVP criterion). p50 budget: parse 8 s, embed 1 s, score initial 10 jobs 4 s.

### 6.2 Job ingestion

Two paths:
- **Direct posting** (recruiter UI): trivial — write row + dispatch `embed_job`.
- **Approved sources** (post legal sign-off — see §14): Celery beat schedules `ingest_source.delay(source_id)` per source. Worker fetches, normalizes to the `jobs` schema, dedupes via `(employer_name_norm, title_norm, locations, posted_at_day)`, embeds, indexes. Failed fetches are recorded in `ingest_runs` and surfaced in the admin source monitor.

Each source has a `kind` and an adapter class implementing `fetch() -> Iterable[RawJob]` and `normalize(raw) -> Job`. Source-specific quirks are isolated in the adapter, not the core pipeline.

### 6.3 Matching

Hybrid scoring; deliberately **not** pure vector similarity, because the BRD's failure mode is "noisy matching":

- **Vector score (0–1):** cosine(applicant_embedding, job_embedding).
- **Structured score (0–1):** weighted sum over rule fits — location (must-match unless remote), years of experience within band, CTC overlap, notice period, must-have skills present, dealbreakers absent.
- **Total score:** `0.6 * vector + 0.4 * structured` (initial weights; promoted to a config table once we have feedback labels).
- **Threshold for surfacing:** total ≥ 0.55 (configurable). Below threshold, the match is stored but not pushed to the feed.

Explanation generation: for each surfaced match, the worker calls the LLM (see §7) with `{applicant_summary, job_summary, structured_score_breakdown}` and asks for a 1–2 sentence "why this fits" + a 1 sentence "what might not fit." Stored in `matches.explanation`. LLM call is rate-limited per applicant per day; falls back to a deterministic templated string if LLM is unavailable.

Re-scoring triggers: new job posted (score against all candidates above location/skill prefilter), applicant profile updated, weekly full re-score (Celery beat).

### 6.4 Notifications

Outbox pattern: writers insert into `notifications`; a Celery beat task sweeps `status='pending' AND send_after <= now()` and dispatches to channel adapters. Idempotency via `notifications.id` as the dedupe key.

Channels (MVP):
- **Push:** FCM for Android + web; APNs via FCM relay for iOS.
- **Email:** SES (template-based; transactional only in MVP).
- **WhatsApp:** adapter scaffolded, integration deferred until vendor selected.

Per-user notification preferences stored in `consents` (scope=`channel:push|email|whatsapp`) and enforced at dispatch time.

---

## 7. AI/ML strategy

> BRD Next Step #3: "Finalize LLM strategy" is **unresolved**. The implementation treats LLM and embedding providers as pluggable to keep the decision deferrable.

`integrations/llm/` exposes one interface:

```python
class LLMProvider(Protocol):
    async def complete(self, *, system: str, user: str,
                       max_tokens: int, temperature: float) -> Completion: ...
    async def parse_resume(self, text: str) -> ResumeParse: ...
    async def explain_match(self, ctx: MatchContext) -> MatchExplanation: ...
```

Provider impls (`anthropic`, `bedrock`, `openai`) are selected by env. Each domain call (parse, explain) goes through a small prompt module versioned in-repo so we can A/B prompts without changing call sites.

`integrations/embeddings/` is parallel: `EmbeddingProvider.encode(text, task, title) -> vec`. The `EmbeddingProvider.encode()` interface accepts an `EmbeddingTask` enum (`DOCUMENT` / `QUERY`) plus an optional `title` to keep call sites provider-agnostic. Dimension is config-driven via `KPA_EMBEDDING_DIM` (default 1536); the `vector(1536)` in §5 reflects this default and must be migrated if the dimension changes.

> **Note on Gemini provider:** `gemini-embedding-2` does not accept the `task_type` parameter that older Google embedding models used. Task is encoded by prompt prefix in the provider impl (`title: … | text: …` for document side; `task: search result | query: …` for query side).

Cost & latency guardrails:
- Resume parse: capped at ~6 k input tokens (text is pre-truncated by section); cached on `sha256(text)` so re-parses of the same resume are free.
- Match explanation: cached on `(applicant_embedding_version, job_embedding_version)`.
- All LLM calls go through a retrying client with circuit-breaker; matching never blocks on LLM availability (uses templated fallback).

Evaluation:
- Resume parse F1 ≥ 0.90 is the MVP gate. Requires a labeled gold dataset (BRD Next Step #4). Evaluation runs in CI on every prompt or provider change.
- Match relevance ≥ 75% (BRD). Measured via thumbs up/down on surfaced matches; we need ≥ N=500 ratings before believing the number. Until then, we'll ship a synthetic eval based on recruiter "shortlist vs ignore" actions.

---

## 8. Background jobs (Celery)

- Broker: Redis (ElastiCache). Result backend: Redis (short TTL — most jobs surface state via DB row, not result).
- Queues:
  - `parse` — resume parsing (slow, LLM-bound).
  - `ingest` — source fetchers (slow, external).
  - `embed` — embedding calls (fast, batched).
  - `score` — match computation (CPU + vector queries).
  - `notify` — channel dispatch (fast, external).
  - `dsr` — DPDP export/delete (slow, sensitive).
- Concurrency: one worker pool per queue type with separate replica counts in HPA, so a slow ingest run does not starve notifications.
- Retries: tenacity-style exponential with jitter, max 5 attempts. Final failure goes to a dead-letter table inspected by admin.
- Scheduling: Celery beat in its own deployment (single replica + leader lock) for: ingest sweeps, outbox flush, weekly re-score, DSR sweeps, embedding model rotation checks.

---

## 9. Auth & security

### 9.1 Identity

- OAuth2 password flow is disabled. Supported providers:
  - Applicants: Google, Apple, phone+OTP.
  - Recruiters: email+password with mandatory verification (issued by employer admin) OR Google with allowed domain list per employer.
  - Admins: email+password + **mandatory TOTP MFA**.
- Tokens: JWT access (10 min) + opaque refresh (30 d, rotating, stored hashed). Refresh reuse triggers full revocation for that user.
- Role claim: `role ∈ {applicant, recruiter, admin}`. Recruiter tokens also carry `employer_id`. Admin actions checked with role + scope claims (`audit:read`, `moderation:write`, etc.).

### 9.2 DPDP compliance (BRD: explicit gate)

- **Consent management:** per-scope consents (`discovery`, `marketing`, `share-with-recruiter-X`, channel toggles). UI surfaces a "consents" screen with grant/revoke. All grant/revoke events written to `audit_logs` AND `consents`.
- **Notice:** the privacy notice version is stamped on every grant; if notice version changes, prior consents are re-prompted on next session.
- **Data export:** `POST /me/dsr/export` creates a `dsr_requests` row; worker produces a JSON+PDF bundle, stores in S3 under a short-lived presigned URL, emails the link.
- **Data deletion:** `POST /me/dsr/delete` creates a deletion request with a 7-day reversal window. After window: cascade soft-delete + hard-delete from S3 (resumes, exports) + anonymize audit records (keep action/timestamp, drop actor PII). Embeddings are deleted with the resume row.
- **Data residency:** all storage in AWS ap-south-1. LLM provider selection (§7) must respect this — Bedrock ap-south-1 or a provider with a DPA + India region commitment.

### 9.3 General

- All HTTP egress through a single allowlist (no arbitrary outbound from workers).
- Secrets in AWS Secrets Manager + Parameter Store; pulled at pod start. Never in repo, never in env files committed to git.
- File uploads: presigned PUT, content-type whitelist (`application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`), 10 MB max, virus-scanned via ClamAV sidecar before parse.
- Rate limiting: per-user and per-IP via Redis token bucket. Stricter buckets for `/auth/*` and `/me/dsr/*`.
- CORS: explicit allowlist of Flutter web origins per environment.

---

## 10. API design

- REST + JSON. Versioned via path: `/v1/...`. Breaking changes bump major.
- Pagination: cursor-based (`?cursor=...&limit=...`); no offset pagination on hot paths.
- Errors: RFC 7807 problem-detail JSON; every error carries `request_id`.
- All resources expose ETag + `If-None-Match` for cacheable GETs.
- OpenAPI 3.1 served at `/openapi.json`; the Flutter client codegen consumes this in CI.

Indicative endpoint surface (not exhaustive):

```
POST   /v1/auth/oauth/google        # Google ID token → access + refresh (client-driven)
POST   /v1/auth/refresh
POST   /v1/auth/logout

GET    /v1/me
PATCH  /v1/me
GET    /v1/me/consents
POST   /v1/me/consents
POST   /v1/me/dsr/export
POST   /v1/me/dsr/delete

POST   /v1/applicants/me/resumes               # init upload → presigned URL
PATCH  /v1/applicants/me/resumes/{id}          # mark uploaded; triggers parse
GET    /v1/applicants/me/resumes/{id}          # status + parsed view

GET    /v1/feed                                # ranked matches
GET    /v1/jobs/{id}
POST   /v1/jobs/{id}/save
POST   /v1/jobs/{id}/apply
GET    /v1/applications                        # mine
PATCH  /v1/applications/{id}/status            # applicant-side tracking

# recruiter
POST   /v1/employers/{eid}/jobs
PATCH  /v1/employers/{eid}/jobs/{id}
GET    /v1/employers/{eid}/jobs/{id}/candidates  # match-ranked
PATCH  /v1/employers/{eid}/jobs/{id}/candidates/{aid}/stage

# admin
GET    /v1/admin/sources
POST   /v1/admin/sources/{id}/run
GET    /v1/admin/moderation
GET    /v1/admin/audit
```

> *The original `/oauth/{provider}/callback` naming assumed a backend-redirect flow. The applicant Google sign-in plan landed with a client-driven ID-token exchange (see the design doc) and renamed the endpoint accordingly. The `{provider}` namespace is preserved for the Apple Sign-In plan.*

p95 latency budget per BRD: ≤ 400 ms for GETs on the read replica. Hot endpoints (`/v1/feed`, `/v1/jobs/{id}`) get a Redis cache with explicit invalidation on writes.

---

## 11. Infrastructure

The MVP path is deliberately small — local first, with one minimal hosted footprint at launch. Heavier infrastructure (EKS, Helm, GitOps, IaC) is **deferred** until the product is validated.

### 11.1 MVP runtime

- **Local dev:**
  - Python service: `uv run uvicorn kpa.main:app --reload` (no container required).
  - Postgres 16: Homebrew (`brew install postgresql@16`, `brew services start postgresql@16`). One local cluster, two databases: `kpa` (dev) and `kpa_test` (integration tests). pgvector via `CREATE EXTENSION vector;` once we hit P1.
  - Redis: introduced at P1 by the resume parse worker plan (was originally planned for P3; advanced because §6.1 needs async parse). Local Redis via Homebrew (`brew install redis && brew services start redis`). The Celery broker + result backend both point at it.
  - Object storage: local filesystem under `./var/uploads/` during dev; an S3 bucket can be slotted in via `integrations/storage_s3.py` once the parse pipeline lands.
  - Secrets: a git-ignored `.env` file loaded by `uv run --env-file=.env ...`. No AWS at this stage.
- **CI:** GitHub Actions runs ruff + mypy + pytest (unit + integration) against a Postgres service container provided by the workflow (the *one* container in the loop, owned by CI, not the developer). The repo itself ships no Dockerfile/compose file.
- **Deployment target for MVP launch:** **TBD — picked at P5 (§13).** Candidates considered: Fly.io (region: BOM/SIN, DPDP-friendly), Render (region: SIN), a small EC2 box. The choice is intentionally late so we keep options open until we know real traffic shape, latency requirements, and budget. Whatever we pick must be in/near `ap-south-1` to honour the DPDP residency commitment (§9.2).

### 11.2 Post-MVP scale path (informational, not active work)

Once MVP traffic and product-market fit are established, the following sections are the planned evolution — **do not build these for MVP**:

- AWS region `ap-south-1` (Mumbai), per BRD.
- Compute: EKS, one cluster per env (`dev`, `staging`, `prod`). Node groups: `api-pool`, `worker-pool`. Karpenter for ingest-spike scale-out.
- Postgres: RDS Postgres 16 with one read replica. Multi-AZ in prod.
- Redis: ElastiCache replication group; separate logical DBs for cache / broker / rate-limit.
- Object storage: S3 buckets per purpose (`kpa-resumes-{env}`, `kpa-exports-{env}`, `kpa-static-{env}`). Lifecycle: resumes versioned + 90-day Glacier transition; exports 7-day expiry.
- CDN: CloudFront in front of the static Flutter web bundle and S3-served public assets.
- Secrets: AWS Secrets Manager (rotating where supported) + Parameter Store.
- IaC: Terraform for AWS resources; Helm charts for app deployment. ArgoCD on `infra/` for GitOps.
- CI/CD evolution: GitHub Actions extended with container build → push to ECR → ArgoCD sync.

Code-level abstractions (the storage interface, the LLM provider interface, the engine factory in `db/session.py`) are designed so the swap from MVP runtime to this footprint is a configuration change, not a rewrite.

---

## 12. Observability

- **Logs:** plain-text structured (`key=value`) to stdout → Fluent Bit → Elasticsearch → Kibana. Required fields: `ts, level, logger, request_id, trace_id, user_id, employer_id, path, method, msg`.
- **Metrics:** Prometheus, scraped from `/metrics` on API + workers. Key SLIs: API p50/p95/p99, error rate per endpoint, Celery queue depth + age, embedding/LLM provider latency, match throughput, notification success rate.
- **Tracing:** OpenTelemetry → an APM backend (vendor TBD — Elastic APM or self-hosted Tempo). Spans cover HTTP, DB, Redis, Celery hop, external HTTP.
- **Dashboards:** one Grafana board per concern: API health, pipeline health (parse/ingest/match), notifications, DSR throughput. PagerDuty alerts wired to SLO burn-rate, not raw thresholds.

---

## 13. MVP build sequence

Phases are sized for sequencing, not for a fixed calendar. Each phase ends with a demoable slice.

**P0 — Foundations (1–2 weeks)**
- Repo scaffolds (Flutter app, FastAPI service). **No** Terraform/Helm/Docker yet — local dev only.
- Local Postgres via Homebrew; Alembic migrations; first models (`users`, `applicants`).
- Auth (Google + Apple + phone-OTP), `GET /me`.
- CI green (ruff + mypy + pytest unit + pytest integration against a CI-provided Postgres), OpenAPI codegen in place.

**P1 — Resume parse + embed (2 weeks)**
- Local-filesystem upload first; S3 presigned upload behind the same `storage` interface, switched on by env. Parse worker landed (Celery + Redis, library/regex parser); embedding worker + status push remain.
- Gold dataset + parse F1 eval in CI (gate: ≥ 0.85 before P2; ≥ 0.90 before launch).

**P2 — Jobs + matching (3 weeks)**
<!-- P2.0 (jobs + seeding) shipped 2026-05-20 via docs/superpowers/plans/2026-05-20-p2.0-jobs-and-seeding.md. Recruiter HTTP CRUD remains deferred; jobs land via the seed CLI for the applicant-only P2/P3 cut. -->
<!-- P2.1 (job embedding worker) shipped 2026-05-20 via docs/superpowers/plans/2026-05-20-p2.1-job-embedding-worker.md. job_embeddings table + embed_job Celery task + dispatch from the seed CLI. -->
<!-- P2.2 (matches + scoring) shipped 2026-05-20 via docs/superpowers/plans/2026-05-20-p2.2-matches-and-scoring.md. matches table + score_applicant + score_job + structured (location/exp/CTC) + vector cosine. Threshold + vector weight env-driven; per-rule weights deferred until labeled data. -->
<!-- P2.3 (feed + job detail endpoints) shipped 2026-05-20 via docs/superpowers/plans/2026-05-20-p2.3-feed-and-job-detail.md. /v1/feed paginated by cursor, /v1/jobs/{id} with uniform 404. ETag + If-None-Match throughout. -->
<!-- P2.4 (match explanations, templated fallback) shipped 2026-05-20 via docs/superpowers/plans/2026-05-20-p2.4-match-explanations.md. matches.explanation JSONB; templated_explanation pure function; LLM provider swap pending BRD §14 #1. -->
- Recruiter direct posting, job embedding, hybrid scoring, feed endpoint, "why this fits" explanation (LLM behind interface, with templated fallback).
- Flutter feed + job detail + apply.

**P3 — Notifications + applications (1–2 weeks)**
<!-- P3.0 (applications + saved jobs) shipped 2026-05-20 via the P3.0 design + commits in feat/p3.0-applications-and-saved-jobs. applications + saved_jobs tables, apply/withdraw/save/unsave/list endpoints. Recruiter-side hiring stages deferred. -->
<!-- P3.1 (notifications outbox + email stub) shipped 2026-05-20 via feat/p3.1-notifications-outbox. notifications table + sweep_notifications Celery task + LoggingEmailChannel stub + /v1/notifications inbox + apply trigger. SES adapter deferred until deploy target picked. -->
- Outbox + push + email; application tracking; saved jobs.
- Notification-side Celery queues (`notify`, `dsr`) added — Redis + Celery already in the stack from the P1 parse worker plan.

**P4 — DPDP + admin (2 weeks)**
- Consent screens; DSR export/delete pipelines; admin moderation + audit log viewer; MFA for admins.

**P5 — Hardening + launch (2 weeks)**
- **Pick the deploy target** (§11.1) and ship a single non-prod environment behind a real domain. This is the first point at which a container image, hosted DB, and managed Redis are required.
- Load testing to BRD targets, security review (P0/P1 → zero), Lighthouse pass on Flutter web, RBAC review, runbooks.

Approved-source ingestion (§6.2) is **off the critical path** for MVP and starts only after legal review concludes.

---

## 14. Open decisions (require product/legal input before they block)

| # | Decision | Owner | Blocks |
|---|---|---|---|
| 1 | LLM provider (Anthropic / Bedrock / OpenAI / hybrid) and region | Ahamed | P2 launch (parsing + explanation quality); cost model |
| 2 | Embedding provider + dimension (1024 default is a placeholder) | Ahamed | DB schema (vector dim is fixed at table create) |
| 3 | Approved third-party job sources + legal posture on scraping | Ahamed + legal | Programmatic ingestion (§6.2); MVP excludes until resolved |
| 4 | SEO surface for public job pages (separate Next.js? pre-render service? Flutter web only?) | Ahamed | Marketing/SEO; if needed, adds a service to §2 |
| 5 | WhatsApp BSP selection (Meta cloud API vs Gupshup vs Karix) | Ahamed | WhatsApp notification channel; MVP scaffolds adapter |
| 6 | Recruiter billing model + provider (Stripe India / Razorpay) | Ahamed | Out of MVP; affects v1.1 schema |
| 7 | Match score weights (currently 0.6/0.4) — calibrate against labeled data | ML lead (TBD) | Match relevance SLA |
| 8 | Mobile push: direct APNs vs APNs via FCM relay | Ahamed | iOS notification reliability |
| 9 | Audit log retention period under DPDP | Legal | `audit_logs` partitioning + lifecycle |
| 10 | Whether parsed resume JSON is retained after deletion in anonymized form for matching quality eval | Legal + Ahamed | DSR delete pipeline behavior |

---

## 15. Risks

- **Resume parse F1 ≥ 0.90 is aggressive.** Indian resumes are heterogeneous (PDF of scanned image, mixed-script names, inconsistent date formats). Mitigation: gold dataset + LLM-assisted parsing + section-level fallback; ship with parse confidence surfaced to the applicant for low-confidence fields.
- **"First match in 10 min" depends on LLM latency.** If parsing relies on an LLM, a single provider outage breaks the SLA. Mitigation: provider abstraction (§7), templated/regex fallback for parsing critical fields (name, phone, email, skills) even when LLM is down.
- **DPDP delete cascading across embeddings, notifications, audit, exports** is easy to miss in one place. Mitigation: a single `delete_user(user_id)` orchestrator with a checklist test that asserts no PII remains in any indexed table.
- **Flutter web bundle size** can push past the 4 s TTI budget on 4G. Mitigation: route-level deferred imports, CanvasKit only on desktop, asset CDN, fonts subset.
- **pgvector at scale.** Once `applicant_embeddings` × `job_embeddings` is in the millions, ANN recall vs latency needs tuning; a vector DB swap (Qdrant/Weaviate) may become necessary. Mitigation: the embedding provider interface (§7) and a thin vector-store interface keep this swap localized.

---

*End of v0.1. Revisit after Open Decisions §14 #1–#4 are answered.*
