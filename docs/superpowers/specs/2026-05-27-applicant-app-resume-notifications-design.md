# Complete Applicant App — Resume + Notifications UI — Design

**Date:** 2026-05-27
**Status:** Approved (design); pending spec review
**Owner area:** `api/` (one small endpoint) + `app/` (Flutter)

## Goal

Wire the two existing-but-unsurfaced applicant backends into the app, replacing
the Profile screen's two "Coming soon" rows:
1. **Resume** — upload / view parse status / replace a single current resume.
2. **Notifications** — a paginated inbox with mark-as-read and tap-through to the
   related job.

Out of scope: recruiter/admin features, multi-resume management, resume delete,
parsed-resume data viewer, unread-count badges, push/email delivery.

## Background — exact backend contracts (verified against code)

### Resume (`api/src/kpa/routes/resumes.py`, prefix `/v1/applicants/me`)
- `POST /resumes` — multipart `file: UploadFile` → `201 ResumeRead`. Validates
  content-type (`KPA_ALLOWED_RESUME_CONTENT_TYPES`: pdf/doc/docx → 415) and size
  (`KPA_MAX_UPLOAD_BYTES`, 10 MiB → 413). Dispatches parse fire-and-forget.
- `GET /resumes/{id}` → `ResumeRead`. Uniform 404.
- **No list endpoint exists** — added by this slice (below).
- `ResumeRead`: `{id: UUID, applicant_id: UUID, original_filename: str,
  content_type: str, size_bytes: int, parse_status: ResumeParseStatus,
  created_at: datetime}`. `ResumeParseStatus` ∈ {pending, parsing, parsed, failed}
  (confirm exact values in `db/models.py:ResumeParseStatus`).
- Parsing is async; status transitions `pending → parsing → parsed | failed`.

### Notifications (`api/src/kpa/routes/notifications.py`, prefix `/v1`)
- `GET /notifications` → `NotificationListResponse {items: [{notification:
  NotificationRead}], next_cursor: str | None}`. Cursor-paginated
  (`?cursor=&limit=`), weak ETag + `If-None-Match` (304). **Excludes `failed`
  rows.**
- `POST /notifications/{id}/read` → `200 NotificationRead`. Idempotent (already-
  read returns existing `read_at`). 404 `notification_not_found` for missing/other-
  user. (Confirm the exact path/verb in the route file before wiring.)
- `NotificationRead`: `{id: UUID, kind: str, channel: str, status: str, payload:
  dict[str, object], send_after: datetime, sent_at: datetime | None, read_at:
  datetime | None, created_at: datetime}`. `payload` carries event data, e.g. the
  apply trigger writes `{job_id, job_title, employer_name, application_id, ...}`
  (confirm keys against the writer in `routes/applications.py`).

## Part 1 — Resume

### Backend: new list endpoint
`GET /v1/applicants/me/resumes` → `list[ResumeRead]`, ordered `created_at DESC`,
`deleted_at IS NULL`, scoped to the authenticated applicant via the existing
`_require_applicant` ladder (401 → 403 `not_an_applicant` → 500 applicant_missing).
Added to `routes/resumes.py` (same router/prefix). Empty list when none.

### App
- **`ResumeDto`** (`lib/data/resume/resume_dto.dart`, `@JsonSerializable`):
  `id`, `applicantId` (`applicant_id`), `originalFilename` (`original_filename`),
  `contentType` (`content_type`), `sizeBytes` (`size_bytes`), `parseStatus`
  (`parse_status`, enum `ResumeParseStatus` with `@JsonKey(unknownEnumValue:
  ResumeParseStatus.unknown)`), `createdAt` (`created_at`).
- **`ResumeParseStatus`** enum (`lib/data/resume/resume_parse_status.dart`):
  `pending, parsing, parsed, failed, unknown` with `@JsonValue` matching the wire
  strings.
- **`ResumeApi`** (`lib/data/resume/resume_api.dart`):
  - `Future<List<ResumeDto>> list()` → `GET /v1/applicants/me/resumes`.
  - `Future<ResumeDto> upload({required List<int> bytes, required String
    filename, required String contentType})` → multipart `POST
    /v1/applicants/me/resumes` via `dio.post(path, data: FormData(... MultipartFile
    .fromBytes(bytes, filename: filename, contentType: MediaType.parse(...))))`.
    (Bytes, not path — works on web + mobile.)
- **`ResumeRepository`** (interface + impl, `data/resume/`): `current()` →
  `list().firstOrNull`; `upload(...)` → `ResumeDto`. Impl wraps `DioException`
  via `mapDioException`. `resumeRepositoryProvider` (`@Riverpod(keepAlive:true)`).
- **`ResumeController`** (`presentation/resume/resume_controller.dart`,
  `@riverpod`): `build()` → `current()` (`AsyncValue<ResumeDto?>`). `Future<bool>
  uploadFromPicked({bytes, filename, contentType})` → repo.upload → on success
  `ref.invalidateSelf()` + return true; on error set error state + false.
- **`ResumeScreen`** (`presentation/resume/resume_screen.dart`) at
  `/profile/resume`:
  - `AsyncValueWidget<ResumeDto?>`; data null → empty state ("No resume yet")
    with an Upload button; data present → card with filename, "Uploaded
    {date}", and a **status chip** (`pending`/`parsing` = neutral "Processing…",
    `parsed` = success "Ready", `failed` = error "Couldn't parse — try again",
    `unknown` = neutral). Plus a "Replace résumé" button.
  - Upload flow: `file_picker` `FilePicker.platform.pickFiles(type: custom,
    allowedExtensions: ['pdf','doc','docx'], withData: true)` → derive
    content-type from extension (map pdf→application/pdf, doc→application/msword,
    docx→…wordprocessingml.document) → `controller.uploadFromPicked(...)`.
  - After a successful upload (row is `pending`/`parsing`), schedule a couple of
    delayed `ref.invalidate(resumeControllerProvider)` refreshes (e.g. at 2s and
    5s) to reflect `parsed`/`failed`; also `RefreshIndicator` pull-to-refresh.
  - Error mapping: `ApiException` 415 → "Unsupported file type (PDF, DOC, DOCX)",
    413 → "File too large (max 10 MB)", else generic; `NetworkException` →
    "Couldn't reach KPA."
- **Profile "Resume" row**: replace the disabled "Coming soon" `ListTile` with a
  tappable one → `context.go('/profile/resume')`, static subtitle "Manage your
  résumé". (Deliberately does NOT watch `resumeControllerProvider` — that would
  fire a resume fetch on every Profile load; the status lives on the Resume
  screen.)
- **Dependency:** add `file_picker` to `app/pubspec.yaml` (+ `http_parser` for
  `MediaType`, which dio re-exports — confirm import path).

## Part 2 — Notifications

### App
- **`NotificationDto`** (`lib/data/notifications/notification_dto.dart`,
  `@JsonSerializable`): `id`, `kind`, `channel`, `status`, `payload`
  (`Map<String, dynamic>`), `sendAfter` (`send_after`), `sentAt` (`sent_at`),
  `readAt` (`read_at`), `createdAt` (`created_at`). `NotificationsPageDto`
  `{items: List<NotificationListItemDto>, nextCursor (next_cursor)}`;
  `NotificationListItemDto {notification: NotificationDto}`.
- **`NotificationApi`** / **`NotificationsRepository`** (`data/notifications/`):
  `fetchPage({String? cursor, int limit = 20})` → `GET /v1/notifications?cursor=
  &limit=` → `NotificationsPageDto`; `markRead(String id)` → `POST
  /v1/notifications/{id}/read` → `NotificationDto`. Impl maps `DioException`.
- **`NotificationsController`** (`presentation/notifications/`): reuse the shared
  `PagedState<NotificationDto>` + `loadNextPage` helpers (see
  `lib/presentation/paging/`); `typedef NotificationsState =
  PagedState<NotificationDto>`. `markRead(id)` calls repo then updates the loaded
  item in place — replace it in `PagedState.items` with the returned (read)
  `NotificationDto`, NOT via invalidate (invalidate would refetch page 1 and
  reset scroll/loaded pages). Must never wipe the loaded list.
- **`NotificationsScreen`** (`presentation/notifications/notifications_screen.dart`)
  at `/profile/notifications`: paginated `ListView` (scroll-to-load like the other
  list screens). Each row: friendly title via a `notificationTitle(NotificationDto)`
  pure mapper (`kind` + `payload` → text; `application_received` → "Application
  received for {job_title} at {employer_name}"; default = humanized `kind`), a
  relative timestamp (module-static `DateFormat`), and an **unread dot** when
  `readAt == null`. Empty state ("No notifications yet"). On tap: `markRead(id)`,
  then if `payload['job_id']` is a non-empty String, navigate to that job's detail.
- **Profile "Notifications" row**: replace the "Coming soon" `ListTile` →
  `context.go('/profile/notifications')`.

### Routing
Extend the **profile** `StatefulShellBranch` in `presentation/routing/router.dart`
(currently `/profile` + `/profile/edit`):
```
GoRoute(/profile)
  routes:
    edit
    resume
    notifications
      routes: [ jobs/:id → JobDetailScreen(jobId) ]   # notification → job, in the profile stack
```
Add `Routes.resume = '/profile/resume'`, `Routes.notifications = '/profile/notifications'`.
Notification tap navigates with `context.go('/profile/notifications/jobs/$jobId')`.

## Testing

### Backend (integration, real Postgres)
- `test_resumes_list.py`: newest-first order; only the caller's live rows
  (another applicant's resume not returned; soft-deleted excluded); empty list
  for an applicant with none; 403 for a recruiter token; 401 unauth.

### App
- **Resume**: `resume_repository_impl_test.dart` (list parse; upload sends
  multipart to the right path and parses the response — assert via
  `MockInterceptor`); `resume_controller_test.dart` (upload success refreshes /
  error surfaces); `resume_screen_test.dart` (empty state, status-chip per
  status, upload button calls controller with picked bytes — inject a fake
  picker result rather than the real platform picker).
- **Notifications**: `notifications_repository_impl_test.dart` (list parse incl.
  `payload`/`next_cursor`; `markRead` posts to the right path); controller test
  (loadMore preserves items on page-N error; markRead flips `readAt` without
  wiping list); `notifications_screen_test.dart` (renders friendly titles +
  unread dots; tap marks read and navigates when `job_id` present).
- Reuse `test/helpers/MockInterceptor` (+ its `lastDataFor`) and the fake-repo
  pattern. Add the two new repos to `test/helpers/fake_repositories.dart` if any
  shared widget/integration test needs them.

## Risks / follow-ups
- **Status freshness**: relying on delayed auto-refresh + pull-to-refresh rather
  than a websocket/long-poll. Acceptable for MVP; a parse usually completes in
  seconds. If it feels laggy, a follow-up can add a bounded poll loop.
- **`file_picker` web**: must use `withData: true` so `bytes` is populated
  (web has no file path). Verified approach; mobile also returns bytes with that
  flag.
- **Notification `payload` is untyped** (`dict[str, object]` → `Map<String,
  dynamic>`); the title mapper must null-guard every key it reads.
- **No unread badge** on the Profile row (no count endpoint). Deferred.
