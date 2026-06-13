# Recruiter Phase 2 — Dashboard + Job Management (R3) — Implementation Plan

> **For agentic workers:** Executed via subagent-driven-development in cohesive batches (data → controllers → screens → routing), each batch reviewed. TDD within each batch.

**Goal:** Give a recruiter a working dashboard, a paginated "My Jobs" list, post/edit/close-job forms, a per-job applicants list, and applicant résumé download — all against the already-shipped backend.

**Architecture:** New `lib/data/jobs/recruiter_*` data layer (flat `RecruiterJobDto` mirroring `RecruiterJobRow`, `ApplicantOfJobDto` mirroring `ApplicantOfJobRow`), a `RecruiterJobsRepository`, paginated controllers reusing `PagedState<T>`/`loadNextPage`, and recruiter screens that replace the Phase-1 placeholders. Routes nest under the recruiter shell branches.

**Tech Stack:** Flutter, Riverpod 4.x codegen, go_router, dio, json_serializable. Backend unchanged.

**Source spec:** `docs/superpowers/specs/2026-06-06-recruiter-employer-experience-design.md` (R3 §4).

## Real backend contracts (verified — mirror EXACTLY)

- `GET /v1/jobs/me?status=&limit=&cursor=` → `RecruiterJobsPage = {items: [RecruiterJobRow], next_cursor: str|null}`. `RecruiterJobRow` is a FLAT `JobRead` + extras: `{id, title, description, locations: [str], min_exp_years: int, max_exp_years: int, ctc_min: float|null, ctc_max: float|null, status: "open"|"closed", posted_at: datetime, employer_verified: bool, applicant_count: int, surfaced_match_count: int}`. No `status` query → open-only; `?status=closed` → open+closed.
- `POST /v1/jobs` body `JobCreate = {employer_id, title(2..200), description(10..10000), locations([1..20]), min_exp_years(0..50), max_exp_years(0..50), ctc_min?(>=0), ctc_max?(>=0), status:"open"|"closed"="open"}` → 201 `JobRead`. Validators: `max_exp_years >= min_exp_years`; if both ctc present `ctc_max >= ctc_min`. 422 on violation.
- `PATCH /v1/jobs/{id}` body `JobPatch` (all fields optional, same bounds + `status:"open"|"closed"`) → 200 `JobRead`. 404 uniform on unknown/wrong-employer/soft-deleted.
- `DELETE /v1/jobs/{id}` → 204. Second delete → 404.
- `GET /v1/jobs/{id}/applicants?limit=&cursor=` → `ApplicantsOfJobPage = {items: [ApplicantOfJobRow], next_cursor}`. `ApplicantOfJobRow = {application_id, applicant_id, display_name: str|null, email: str|null, status: str, applied_at: datetime, match_score: float|null, match_explanation: {str:str}|null}`. (match_explanation has keys `fit`/`caveat`.)
- `GET /v1/employers/me` → `[EmployerRead]` (already have `EmployerDto` + `EmployerRepository.listMyEmployers()`).
- `GET /v1/applications/{application_id}/resume` → raw bytes, `media_type` = the résumé content-type, header `Content-Disposition: attachment; filename="..."`. 404 uniform.

## Existing pieces to REUSE (do not reinvent)
- `lib/presentation/paging/paged_state.dart` (`PagedState<T>`), `paging.dart` (`loadNextPage`).
- `feed_controller.dart` — canonical paginated `@riverpod` controller (build first page, `refresh`, `loadMore`).
- `applications_screen.dart` — canonical paginated list screen (ScrollController + `loadMore`, `AsyncValueWidget`, `KpaEmptyState`, `KpaLoadingView`, `RefreshIndicator`, `ListView.separated`).
- `ctc_format.dart` — `formatCtc(String?)` formats a wire STRING. **Recruiter ctc is float|null**, so add `formatCtcNum(double?)` alongside it (same `_inr` formatter) rather than stringifying.
- `KpaScoreBadge`, `KpaSpacing`, `KpaEmptyState`, `KpaErrorView`, `AsyncValueWidget`.
- `MockInterceptor` (`test/helpers/mock_interceptor.dart`) + `ApiException` (slug from `detail`).
- Phase-1 recruiter shell: `kpa_recruiter_shell_scaffold.dart`, 4 placeholder screens under `lib/presentation/recruiter/`, `Routes.recruiter*`, router's recruiter `StatefulShellRoute`.

---

## Batch A — Data layer

**Files (create):** `lib/data/jobs/recruiter_job_dto.dart`, `lib/data/jobs/applicant_of_job_dto.dart`, `lib/data/jobs/recruiter_jobs_api.dart`, `lib/data/jobs/recruiter_jobs_repository.dart`, `lib/data/jobs/recruiter_jobs_repository_impl.dart`. **Tests:** `test/unit/data/jobs/recruiter_job_dto_test.dart`, `applicant_of_job_dto_test.dart`, `recruiter_jobs_repository_impl_test.dart`.

### A1: DTOs
`RecruiterJobDto` — plain `@JsonSerializable`, FLAT shape with `@JsonKey(name:)` for snake_case: fields `id, title, description, locations(List<String>), minExpYears(int, 'min_exp_years'), maxExpYears(int,'max_exp_years'), ctcMin(double?,'ctc_min'), ctcMax(double?,'ctc_max'), status(String), postedAt(DateTime,'posted_at'), employerVerified(bool,'employer_verified'), applicantCount(int,'applicant_count'), surfacedMatchCount(int,'surfaced_match_count')`. `RecruiterJobsPageDto = {items: List<RecruiterJobDto>, nextCursor(String?, 'next_cursor')}`.

`ApplicantOfJobDto` — `{applicationId('application_id'), applicantId('applicant_id'), displayName(String?,'display_name'), email(String?), status(String), appliedAt(DateTime,'applied_at'), matchScore(double?,'match_score'), matchExplanation(Map<String,String>?,'match_explanation')}`. `ApplicantsOfJobPageDto = {items, nextCursor('next_cursor')}`.

Tests: parse a full row (verify snake_case mapping, null ctc/score/explanation, the `applicant_count`/`surfaced_match_count` ints) and a minimal row (nulls).

### A2: API + repository
`RecruiterJobsApi(Dio)`:
- `listMyJobs({String? status, String? cursor, int limit=20}) → GET /v1/jobs/me` (query: `limit`, `status` if non-null, `cursor` if non-null) → `RecruiterJobsPageDto`.
- `createJob(Map<String,dynamic> body) → POST /v1/jobs` → `RecruiterJobDto` (note: response is flat `JobRead` without counts — parse into `RecruiterJobDto` is fine; counts default to 0. Actually `JobRead` has no count fields, so create/patch return a `JobRead`. Parse those into a separate lightweight read or reuse `RecruiterJobDto` with `applicant_count`/`surfaced_match_count` defaulting to 0 via `@JsonKey(defaultValue: 0)`). Use `@JsonKey(defaultValue: 0)` on the two count fields so create/patch JobRead responses parse.
- `patchJob(String id, Map<String,dynamic> body) → PATCH /v1/jobs/{id}` → `RecruiterJobDto`.
- `deleteJob(String id) → DELETE /v1/jobs/{id}` (204, no body).
- `listApplicants(String jobId, {String? cursor, int limit=20}) → GET /v1/jobs/{id}/applicants` → `ApplicantsOfJobPageDto`.
- `downloadResume(String applicationId) → GET /v1/applications/{id}/resume` with `Options(responseType: ResponseType.bytes)`; return a small record `({Uint8List bytes, String filename, String contentType})` parsing the `content-disposition` filename + `content-type` header (fallback filename `resume`).

`RecruiterJobsRepository` interface + `...Impl` (mirror `me_repository_impl.dart`: try/catch `on DioException → mapDioException`, `@Riverpod(keepAlive:true) recruiterJobsRepository`). Methods mirror the API, typed with the DTOs.

Test (`recruiter_jobs_repository_impl_test.dart`, MockInterceptor): listMyJobs 200 parses page; createJob 422 surfaces ApiException; listApplicants 200 parses; downloadResume returns bytes+filename. (Adapt to MockInterceptor's real API as in Phase 1's employers test.)

**Commit:** `feat(app): recruiter jobs data layer (DTOs, API, repository)`

---

## Batch B — Controllers

**Files (create):** `lib/presentation/recruiter/recruiter_jobs_controller.dart`, `recruiter_dashboard_controller.dart`, `recruiter_applicants_controller.dart`, `job_form_controller.dart`, `active_employer_provider.dart`. **Tests:** matching `test/unit/presentation/recruiter/*_test.dart`.

### B1: `RecruiterJobsController` (paginated)
Mirror `feed_controller.dart`. `typedef RecruiterJobsState = PagedState<RecruiterJobDto>`. `build()` fetches `listMyJobs(status: _statusFilter)`. Hold a status filter (open-only vs include-closed) — implement as a family param OR a field toggled via a method `setIncludeClosed(bool)` that invalidates. Simplest: family `@riverpod ... RecruiterJobsController build(bool includeClosed)`. Use family param `includeClosed`; status passed as `includeClosed ? 'closed' : null`. `refresh()` + `loadMore()` like feed.

### B2: `RecruiterDashboardController`
`build()` fetches `listMyJobs(status:'closed', limit:100)` (one page; MVP-documented approximation for >100 jobs) and returns a summary record/class `RecruiterDashboardSummary{openJobs:int, totalApplicants:int, totalSurfacedMatches:int, recentJobs: List<RecruiterJobDto>}` computed from items (openJobs = count status=='open'; totals = sum of counts; recentJobs = first 5). `refresh()` invalidates self.

### B3: `RecruiterApplicantsController` (family by jobId, paginated)
`@riverpod class RecruiterApplicantsController` family `(String jobId)`. `typedef = PagedState<ApplicantOfJobDto>`. build fetches `listApplicants(jobId)`; `loadMore`/`refresh`.

### B4: `JobFormController`
`@riverpod class JobFormController extends ...`, `build() => null` (AsyncValue<RecruiterJobDto?>). Methods: `create({required String employerId, required JobFormData data})` → `recruiterJobsRepository.createJob({...})` then on success invalidate `recruiterJobsControllerProvider` + dashboard; `update({required String jobId, required JobFormPatch patch})` → `patchJob`; `close(String jobId)` → `patchJob(status:'closed')`; `delete(String jobId)` → `deleteJob`. Use `AsyncValue.guard`. Define a small `JobFormData` value object (title, description, locations, minExp, maxExp, ctcMin?, ctcMax?, status) in the same file. Client-side validation of band ordering lives in the screen's Form validators, but also guard here.

### B5: `activeEmployerProvider`
`@Riverpod(keepAlive:true) class ActiveEmployer` holding the selected `EmployerDto?`; a `Future<List<EmployerDto>> recruiterEmployers` provider wrapping `employerRepository.listMyEmployers()`. Default active = first. Used by the job form (employer_id) and (Phase 4) the team tab.

Tests: B1 happy path (build loads page, loadMore appends); B2 summary math (openJobs/totals/recent from a fake repo returning known rows); B4 create success invalidates + error path doesn't; use Fake `RecruiterJobsRepository`.

**Commit:** `feat(app): recruiter controllers (jobs list, dashboard, applicants, job form)`

---

## Batch C — Screens

**Files (create):** `lib/presentation/recruiter/recruiter_job_card.dart`, and REPLACE the placeholder bodies of `recruiter_dashboard_screen.dart`, `recruiter_jobs_screen.dart`, `recruiter_employer_screen.dart` (leave Employer as a light placeholder noting "Team management — Phase 4"), `recruiter_profile_screen.dart` (minimal: name/email + Sign out + Privacy link, reuse `signOutControllerProvider` + `Routes.privacy`); create `recruiter_job_detail_screen.dart`, `job_form_screen.dart`, `job_applicants_screen.dart`. **Tests:** `test/widget/recruiter_*_test.dart`.

### C1: `RecruiterJobCard`
A `Card` showing title, status chip (open/closed), `applicantCount` + `surfacedMatchCount` (icons), exp band + CTC band (via `formatCtcNum`). Tap → `onTap` callback.

### C2: My Jobs screen
Mirror `applications_screen.dart`: ScrollController + loadMore, `AsyncValueWidget<RecruiterJobsState>`, empty state ("No jobs yet — post your first role" with a "Post a job" FilledButton → `/recruiter/jobs/new`), a SegmentedButton/Switch toggle for "Show closed" that flips the family param (watch `recruiterJobsControllerProvider(includeClosed)`), an AppBar action "+" → `/recruiter/jobs/new`. Rows = `RecruiterJobCard` → tap navigates to `/recruiter/jobs/{id}`.

### C3: Dashboard screen
Watch `recruiterDashboardControllerProvider`. Header: three summary cards (Open jobs / Applicants / Surfaced matches). Below: "Recent jobs" list (recentJobs) with a "View all" → switch to Jobs tab (or push `/recruiter/jobs`). Empty (no jobs) → CTA "Post your first job". `RefreshIndicator`.

### C4: Recruiter Job Detail screen (`/recruiter/jobs/:id`)
Receives `jobId`. Reads the job from `recruiterJobsControllerProvider(true)` items by id if present, else (deep-link) fetch via a single-job read — MVP: if not in the list, show a minimal "open My Jobs" fallback OR add a `getJob(id)` that filters listMyJobs. Simplest MVP: pass the `RecruiterJobDto` via `extra` when navigating from the card; for deep-links where it's absent, fetch the closed list and find it. Show full detail (title, description, bands, counts) + action buttons: **Edit** → `/recruiter/jobs/:id/edit`, **View applicants** → `/recruiter/jobs/:id/applicants`, **Close** (if open) → `JobFormController.close` with a confirm dialog, **Delete** → confirm dialog → `JobFormController.delete` then pop.

### C5: Job Form screen (`/recruiter/jobs/new` + `/recruiter/jobs/:id/edit`)
A `ConsumerStatefulWidget` form: title, description (multiline), locations (chips input like `edit_profile_screen.dart`), min/max exp (number fields), ctc min/max (number fields, optional), status (only on edit). Validators mirror backend bounds incl. `max>=min` for exp and ctc. employer_id from `activeEmployerProvider` (if multiple employers, a dropdown). Submit → `JobFormController.create`/`update`. On success pop (list auto-invalidated). 422 → snackbar. New-mode title "Post a job"; edit-mode prefilled from the passed `RecruiterJobDto`.

### C6: Job Applicants screen (`/recruiter/jobs/:id/applicants`)
Paginated list (`recruiterApplicantsControllerProvider(jobId)`). Each row: display_name (fallback email), applied_at, `KpaScoreBadge` for match_score (if present), match_explanation['fit'] subtitle, a **Download résumé** button → `recruiterJobsRepository.downloadResume(applicationId)`. Résumé download MVP: on web trigger a browser download (web-only conditional helper `lib/presentation/recruiter/resume_download/` with stub+web impl, mirroring the google_web_sign_in conditional-import pattern); on mobile show a snackbar "Résumé download is available on the web app" (documented deferral, like DSR-export's clipboard deferral). Empty state: "No applicants yet."

Widget tests (use `ThemeData.light(useMaterial3:true)`, fake repositories): My Jobs renders rows + empty + toggle; dashboard renders summary numbers; job form validates bands + submits; applicants list renders a row with score + download button; recruiter profile shows Sign out.

**Commit:** `feat(app): recruiter screens (dashboard, jobs, job form, applicants, detail)`

---

## Batch D — Routing + integration

**Files (modify):** `lib/presentation/routing/routes.dart` (add `recruiterJobNew='/recruiter/jobs/new'`, and the nested patterns are relative), `lib/presentation/routing/router.dart`.

- In the recruiter `StatefulShellRoute`, replace the 4 placeholder builders with the real screens. Under the **Jobs** branch (`/recruiter/jobs`), add nested routes: `new` → JobFormScreen(create), `:id` → RecruiterJobDetailScreen, `:id/edit` → JobFormScreen(edit), `:id/applicants` → JobApplicantsScreen. Pass the `RecruiterJobDto` via `GoRouterState.extra` where navigating from a card; screens handle null `extra` (deep-link) gracefully.
- Dashboard branch → RecruiterDashboardScreen; Employer branch → placeholder (Phase 4); Profile branch → RecruiterProfileScreen.
- Ensure `flutter analyze` clean and `flutter test` FULL suite green.

**Commit:** `feat(app): wire recruiter shell routes to real screens`

---

## Definition of Done
- A recruiter sees a dashboard with live counts, a paginated My Jobs list (toggle closed), can post/edit/close/delete a job, view a job's applicants with match scores, and download a résumé (web) / see the deferral note (mobile).
- `flutter test` + `flutter analyze` green. No regression to applicant flows.
