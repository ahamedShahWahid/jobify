# Applicant App — Resume + Notifications UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Profile screen's two "Coming soon" rows with working Resume (upload/status/replace) and Notifications (paginated inbox + mark-read + tap-to-job) features, wiring the existing backends plus one new resume-list endpoint.

**Architecture:** Backend gains `GET /v1/applicants/me/resumes` (list). App gains two feature folders (`data/resume` + `presentation/resume`, `data/notifications` + `presentation/notifications`) following the existing repo→controller→screen + `PagedState` patterns; two new screens nested in the Profile tab's `StatefulShellBranch`.

**Tech Stack:** FastAPI + async SQLAlchemy; Flutter + Riverpod 3 runtime / riverpod_annotation codegen + dio (multipart) + go_router + json_serializable + `file_picker` (new) + intl.

Spec: `docs/superpowers/specs/2026-05-27-applicant-app-resume-notifications-design.md`

---

## File Structure

**Backend:** `api/src/kpa/routes/resumes.py` (+1 endpoint); `api/tests/integration/test_resumes_list.py` (new).

**App — Resume:**
- `lib/data/resume/resume_parse_status.dart`, `resume_dto.dart` (+`.g`), `resume_api.dart`, `resume_repository.dart`, `resume_repository_impl.dart` (+`.g`).
- `lib/presentation/resume/resume_controller.dart` (+`.g`), `resume_screen.dart`.

**App — Notifications:**
- `lib/data/notifications/notification_dto.dart` (+`.g`), `notification_api.dart`, `notifications_repository.dart`, `notifications_repository_impl.dart` (+`.g`).
- `lib/presentation/notifications/notifications_controller.dart` (+`.g`), `notification_title.dart`, `notifications_screen.dart`.

**App — shared:** `lib/presentation/routing/routes.dart` (+2 consts), `lib/presentation/routing/router.dart` (profile branch), `lib/presentation/profile/profile_screen.dart` (2 rows), `app/pubspec.yaml` (`file_picker`).

---

## Task 1: Backend — `GET /v1/applicants/me/resumes` list endpoint

**Files:**
- Modify: `api/src/kpa/routes/resumes.py`
- Test: `api/tests/integration/test_resumes_list.py`

All commands from `api/`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/integration/test_resumes_list.py`:

```python
"""Integration tests for GET /v1/applicants/me/resumes (list)."""

from __future__ import annotations

import httpx
import pytest

from kpa.auth.google_verifier import GoogleClaims

pytestmark = pytest.mark.integration


def _claims(sub: str = "g-resume-1", email: str = "alice@example.com") -> GoogleClaims:
    return GoogleClaims(
        sub=sub,
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email=email,
        email_verified=True,
        name="Alice",
    )


async def _signin(client: httpx.AsyncClient, google_verifier, claims) -> dict:
    google_verifier.canned["tok"] = claims
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert resp.status_code == 200
    return resp.json()


async def _upload(client: httpx.AsyncClient, access: str, name: str) -> dict:
    resp = await client.post(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {access}"},
        files={"file": (name, b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_list_empty(async_client: httpx.AsyncClient, google_verifier) -> None:
    signin = await _signin(async_client, google_verifier, _claims())
    resp = await async_client.get(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {signin['access_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_newest_first_and_scoped(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier, _claims())
    access = signin["access_token"]
    first = await _upload(async_client, access, "one.pdf")
    second = await _upload(async_client, access, "two.pdf")

    resp = await async_client.get(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [r["original_filename"] for r in body] == ["two.pdf", "one.pdf"]
    assert {r["id"] for r in body} == {first["id"], second["id"]}


async def test_list_recruiter_403(async_client: httpx.AsyncClient, session) -> None:
    from kpa.auth.tokens import mint_access_token
    from kpa.db.models import User, UserRole

    user = User(email="rec-resume@example.com", role=UserRole.RECRUITER)
    session.add(user)
    await session.flush()
    token = mint_access_token(
        user_id=user.id, role=user.role.value, secret="x" * 32, ttl_seconds=600
    )
    resp = await async_client.get(
        "/v1/applicants/me/resumes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"
```

NOTE: confirm the recruiter-user/`mint_access_token` pattern against `tests/integration/test_resumes_auth.py` (column kwargs, `_JWT_SECRET`, ttl) and the multipart upload helper against `test_resumes_upload.py`; copy their exact working forms if these differ. Confirm the upload field name is `file` from the `POST /resumes` handler signature in `resumes.py`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest -v -m integration tests/integration/test_resumes_list.py`
Expected: FAIL — `GET /resumes` returns 404/405.

- [ ] **Step 3: Add the list endpoint**

In `api/src/kpa/routes/resumes.py`, add this handler (place it just before the existing `@router.get("/resumes/{resume_id}", ...)` handler so the static path is declared first):

```python
@router.get("/resumes", response_model=list[ResumeRead])
async def list_resumes(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[ResumeRead]:
    """List the authenticated applicant's resumes, newest first."""
    applicant = await _require_applicant(user, session)
    rows = (
        (
            await session.execute(
                select(Resume)
                .where(
                    Resume.applicant_id == applicant.id,
                    Resume.deleted_at.is_(None),
                )
                .order_by(Resume.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ResumeRead.model_validate(r) for r in rows]
```

(`select`, `Resume`, `ResumeRead`, `_require_applicant`, `current_user`, `get_session` are all already imported/defined in this module — verify before adding new imports.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest -v -m integration tests/integration/test_resumes_list.py`
Expected: PASS (3 tests).

- [ ] **Step 5: Lint + type-check**

Run: `uv run ruff check src/ tests/ && uv run mypy`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/kpa/routes/resumes.py tests/integration/test_resumes_list.py
git commit -m "feat(api): GET /v1/applicants/me/resumes list endpoint"
```

---

## Task 2: App — ResumeParseStatus + ResumeDto

**Files:**
- Create: `app/lib/data/resume/resume_parse_status.dart`, `app/lib/data/resume/resume_dto.dart`
- Test: `app/test/unit/data/resume/resume_dto_test.dart`

All commands from `app/`.

- [ ] **Step 1: Create the enum**

`app/lib/data/resume/resume_parse_status.dart`:

```dart
import 'package:json_annotation/json_annotation.dart';

/// Mirrors the backend ResumeParseStatus StrEnum. `unknown` is the forward-compat
/// sentinel for a wire value the client doesn't recognise.
enum ResumeParseStatus {
  @JsonValue('pending')
  pending,
  @JsonValue('parsing')
  parsing,
  @JsonValue('parsed')
  parsed,
  @JsonValue('failed')
  failed,
  unknown,
}
```

- [ ] **Step 2: Create the DTO**

`app/lib/data/resume/resume_dto.dart`:

```dart
import 'package:json_annotation/json_annotation.dart';

import 'package:kpa_app/data/resume/resume_parse_status.dart';

part 'resume_dto.g.dart';

/// Mirrors api `ResumeRead` (routes/resumes.py).
@JsonSerializable(createToJson: false)
class ResumeDto {
  const ResumeDto({
    required this.id,
    required this.applicantId,
    required this.originalFilename,
    required this.contentType,
    required this.sizeBytes,
    required this.parseStatus,
    required this.createdAt,
  });

  factory ResumeDto.fromJson(Map<String, dynamic> json) =>
      _$ResumeDtoFromJson(json);

  final String id;
  @JsonKey(name: 'applicant_id')
  final String applicantId;
  @JsonKey(name: 'original_filename')
  final String originalFilename;
  @JsonKey(name: 'content_type')
  final String contentType;
  @JsonKey(name: 'size_bytes')
  final int sizeBytes;
  @JsonKey(name: 'parse_status', unknownEnumValue: ResumeParseStatus.unknown)
  final ResumeParseStatus parseStatus;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
}
```

- [ ] **Step 3: Generate code**

Run: `dart run build_runner build --delete-conflicting-outputs`
Expected: writes `resume_dto.g.dart`.

- [ ] **Step 4: Write + run the test**

`app/test/unit/data/resume/resume_dto_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';

void main() {
  test('parses the ResumeRead wire shape', () {
    final dto = ResumeDto.fromJson(const {
      'id': 'r1',
      'applicant_id': 'a1',
      'original_filename': 'cv.pdf',
      'content_type': 'application/pdf',
      'size_bytes': 1234,
      'parse_status': 'parsed',
      'created_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.id, 'r1');
    expect(dto.applicantId, 'a1');
    expect(dto.originalFilename, 'cv.pdf');
    expect(dto.sizeBytes, 1234);
    expect(dto.parseStatus, ResumeParseStatus.parsed);
  });

  test('unknown parse_status → sentinel', () {
    final dto = ResumeDto.fromJson(const {
      'id': 'r1',
      'applicant_id': 'a1',
      'original_filename': 'cv.pdf',
      'content_type': 'application/pdf',
      'size_bytes': 1,
      'parse_status': 'martian',
      'created_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.parseStatus, ResumeParseStatus.unknown);
  });
}
```

Run: `flutter test test/unit/data/resume/resume_dto_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/data/resume/resume_parse_status.dart lib/data/resume/resume_dto.dart lib/data/resume/resume_dto.g.dart test/unit/data/resume/resume_dto_test.dart
git commit -m "feat(app): ResumeDto + ResumeParseStatus"
```

---

## Task 3: App — ResumeApi + ResumeRepository (+ file_picker dep)

**Files:**
- Modify: `app/pubspec.yaml`
- Create: `app/lib/data/resume/resume_api.dart`, `resume_repository.dart`, `resume_repository_impl.dart`
- Test: `app/test/unit/data/resume/resume_repository_impl_test.dart`

- [ ] **Step 1: Add the file_picker dependency**

In `app/pubspec.yaml`, under `dependencies:` (in the "Misc" group), add:

```yaml
  file_picker: ^8.1.4
```

Run: `flutter pub get`
Expected: resolves (if `^8.1.4` conflicts with the Flutter SDK, run `flutter pub add file_picker` and accept the resolved version).

- [ ] **Step 2: Write the failing test**

`app/test/unit/data/resume/resume_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/resume/resume_api.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _resumeJson(String id, String name, String status) => {
      'id': id,
      'applicant_id': 'a1',
      'original_filename': name,
      'content_type': 'application/pdf',
      'size_bytes': 10,
      'parse_status': status,
      'created_at': '2026-05-01T00:00:00Z',
    };

void main() {
  test('current(): returns first of GET list (newest), or null when empty',
      () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.onList('GET', '/v1/applicants/me/resumes', 200, [
      _resumeJson('r2', 'two.pdf', 'parsed'),
      _resumeJson('r1', 'one.pdf', 'failed'),
    ]);
    final repo = ResumeRepositoryImpl(ResumeApi(dio));
    final current = await repo.current();
    expect(current?.id, 'r2');
    expect(current?.parseStatus, ResumeParseStatus.parsed);
  });

  test('upload(): POSTs multipart to /resumes and parses ResumeDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('POST', '/v1/applicants/me/resumes', 201,
        _resumeJson('r9', 'new.pdf', 'pending'));
    final repo = ResumeRepositoryImpl(ResumeApi(dio));
    final dto = await repo.upload(
      bytes: [1, 2, 3],
      filename: 'new.pdf',
      contentType: 'application/pdf',
    );
    expect(dto.id, 'r9');
    expect(dto.parseStatus, ResumeParseStatus.pending);
    final req = mock.lastRequestFor('POST', '/v1/applicants/me/resumes');
    expect(req?.data, isA<FormData>());
  });
}
```

This test needs two `MockInterceptor` helpers that don't exist yet: `onList` (scripts a JSON-array response) and `lastRequestFor` (returns the captured `RequestOptions`). Add them in Step 3.

- [ ] **Step 3: Extend MockInterceptor**

In `app/test/helpers/mock_interceptor.dart`, add a list-body route map + accessor. Add these members to the `MockInterceptor` class and handle list routes in `onRequest`:

```dart
  final Map<String, _ScriptedListResponse> _listRoutes = {};

  void onList(String method, String path, int status, List<dynamic> body) {
    _listRoutes['$method:$path'] = _ScriptedListResponse(status, body);
  }

  RequestOptions? lastRequestFor(String method, String path) {
    for (final r in requests.reversed) {
      if (r.method == method && r.path == path) return r;
    }
    return null;
  }
```

In `onRequest`, after `requests.add(options);` and computing `key`, before the existing map lookup, handle list routes:

```dart
    final listResp = _listRoutes[key];
    if (listResp != null) {
      handler.resolve(Response(
        requestOptions: options,
        statusCode: listResp.status,
        data: listResp.body,
      ));
      return;
    }
```

And add the class at the bottom:

```dart
class _ScriptedListResponse {
  _ScriptedListResponse(this.status, this.body);
  final int status;
  final List<dynamic> body;
}
```

- [ ] **Step 4: Run to verify it fails**

Run: `flutter test test/unit/data/resume/resume_repository_impl_test.dart`
Expected: FAIL — `ResumeApi`/`ResumeRepositoryImpl` undefined.

- [ ] **Step 5: Create the API client**

`app/lib/data/resume/resume_api.dart`:

```dart
import 'package:dio/dio.dart';

import 'package:kpa_app/data/resume/resume_dto.dart';

class ResumeApi {
  ResumeApi(this._dio);
  final Dio _dio;

  Future<List<ResumeDto>> list() async {
    final res = await _dio.get<List<dynamic>>('/v1/applicants/me/resumes');
    return (res.data ?? <dynamic>[])
        .map((e) => ResumeDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: DioMediaType.parse(contentType),
      ),
    });
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/applicants/me/resumes',
      data: form,
    );
    return ResumeDto.fromJson(res.data!);
  }
}
```

NOTE: `DioMediaType` is dio 5.x's re-export of `http_parser`'s `MediaType`. If the symbol isn't found in the installed dio, `import 'package:http_parser/http_parser.dart';` and use `MediaType.parse(contentType)` instead (add `http_parser` to pubspec only if it isn't already transitively importable). The multipart field name is `file` — confirm against the `POST /resumes` handler.

- [ ] **Step 6: Create the repository (interface + impl)**

`app/lib/data/resume/resume_repository.dart`:

```dart
import 'package:kpa_app/data/resume/resume_dto.dart';

abstract interface class ResumeRepository {
  /// The applicant's latest resume, or null if none uploaded.
  Future<ResumeDto?> current();

  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  });
}
```

`app/lib/data/resume/resume_repository_impl.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/resume/resume_api.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_repository.dart';

part 'resume_repository_impl.g.dart';

class ResumeRepositoryImpl implements ResumeRepository {
  ResumeRepositoryImpl(this._api);
  final ResumeApi _api;

  @override
  Future<ResumeDto?> current() async {
    try {
      final list = await _api.list();
      return list.isEmpty ? null : list.first;
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    try {
      return await _api.upload(
        bytes: bytes,
        filename: filename,
        contentType: contentType,
      );
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
ResumeRepository resumeRepository(Ref ref) =>
    ResumeRepositoryImpl(ResumeApi(ref.read(dioProvider)));
```

- [ ] **Step 7: Generate + run tests**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/data/resume/`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add pubspec.yaml pubspec.lock lib/data/resume/resume_api.dart lib/data/resume/resume_repository.dart lib/data/resume/resume_repository_impl.dart lib/data/resume/resume_repository_impl.g.dart test/helpers/mock_interceptor.dart test/unit/data/resume/resume_repository_impl_test.dart
git commit -m "feat(app): ResumeApi + ResumeRepository (+ file_picker dep)"
```

---

## Task 4: App — ResumeController

**Files:**
- Create: `app/lib/presentation/resume/resume_controller.dart`
- Test: `app/test/unit/presentation/resume/resume_controller_test.dart`

- [ ] **Step 1: Create the controller**

`app/lib/presentation/resume/resume_controller.dart`:

```dart
import 'dart:async';

import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'resume_controller.g.dart';

@riverpod
class ResumeController extends _$ResumeController {
  @override
  Future<ResumeDto?> build() async =>
      ref.read(resumeRepositoryProvider).current();

  /// Upload picked file bytes. Returns true on success; the new (pending)
  /// resume becomes the state so the UI shows it immediately. The screen
  /// schedules follow-up refreshes to reflect the async parse result.
  Future<bool> uploadFromPicked({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    state = const AsyncValue.loading();
    final result = await AsyncValue.guard(
      () => ref.read(resumeRepositoryProvider).upload(
            bytes: bytes,
            filename: filename,
            contentType: contentType,
          ),
    );
    if (result.hasError) {
      state = AsyncValue.error(result.error!, result.stackTrace!);
      return false;
    }
    state = AsyncValue.data(result.value);
    return true;
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
```

- [ ] **Step 2: Generate code**

Run: `dart run build_runner build --delete-conflicting-outputs`
Confirm the generated provider name is `resumeControllerProvider` (read `resume_controller.g.dart`).

- [ ] **Step 3: Write + run the test**

`app/test/unit/presentation/resume/resume_controller_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/data/resume/resume_repository.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';
import 'package:kpa_app/presentation/resume/resume_controller.dart';

ResumeDto _dto(String id, ResumeParseStatus s) => ResumeDto(
      id: id,
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: s,
      createdAt: DateTime(2026),
    );

class _Repo implements ResumeRepository {
  _Repo({this.initial, this.fail = false});
  ResumeDto? initial;
  final bool fail;
  @override
  Future<ResumeDto?> current() async => initial;
  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    if (fail) throw const ApiException(statusCode: 413, slug: 'too_large');
    return _dto('new', ResumeParseStatus.pending);
  }
}

void main() {
  test('build loads current resume', () async {
    final c = ProviderContainer(overrides: [
      resumeRepositoryProvider
          .overrideWithValue(_Repo(initial: _dto('r1', ResumeParseStatus.parsed))),
    ]);
    addTearDown(c.dispose);
    final v = await c.read(resumeControllerProvider.future);
    expect(v?.id, 'r1');
  });

  test('upload success sets the new resume as state', () async {
    final c = ProviderContainer(overrides: [
      resumeRepositoryProvider.overrideWithValue(_Repo()),
    ]);
    addTearDown(c.dispose);
    await c.read(resumeControllerProvider.future);
    final ok = await c.read(resumeControllerProvider.notifier).uploadFromPicked(
      bytes: const [1],
      filename: 'cv.pdf',
      contentType: 'application/pdf',
    );
    expect(ok, isTrue);
    expect(c.read(resumeControllerProvider).value?.parseStatus,
        ResumeParseStatus.pending);
  });

  test('upload error returns false + error state', () async {
    final c = ProviderContainer(overrides: [
      resumeRepositoryProvider.overrideWithValue(_Repo(fail: true)),
    ]);
    addTearDown(c.dispose);
    await c.read(resumeControllerProvider.future);
    final ok = await c.read(resumeControllerProvider.notifier).uploadFromPicked(
      bytes: const [1],
      filename: 'cv.pdf',
      contentType: 'application/pdf',
    );
    expect(ok, isFalse);
    expect(c.read(resumeControllerProvider).hasError, isTrue);
  });
}
```

Run: `flutter test test/unit/presentation/resume/resume_controller_test.dart`
Expected: PASS. Confirm `ApiException(statusCode:..., slug:...)` matches `lib/core/error/exceptions.dart`; adjust if needed.

- [ ] **Step 4: Commit**

```bash
git add lib/presentation/resume/resume_controller.dart lib/presentation/resume/resume_controller.g.dart test/unit/presentation/resume/resume_controller_test.dart
git commit -m "feat(app): ResumeController"
```

---

## Task 5: App — ResumeScreen + route + Profile row

**Files:**
- Create: `app/lib/presentation/resume/resume_screen.dart`
- Modify: `app/lib/presentation/routing/routes.dart`, `app/lib/presentation/routing/router.dart`, `app/lib/presentation/profile/profile_screen.dart`
- Test: `app/test/widget/resume_screen_test.dart`

- [ ] **Step 1: Add the route constant**

In `app/lib/presentation/routing/routes.dart`, inside `Routes`:

```dart
  static const resume = '/profile/resume';
```

- [ ] **Step 2: Register the nested route**

In `app/lib/presentation/routing/router.dart`, add the import:

```dart
import 'package:kpa_app/presentation/resume/resume_screen.dart';
```

And in the profile `GoRoute`'s `routes:` list (currently just `edit`), add:

```dart
                  GoRoute(
                    path: 'resume',
                    builder: (_, __) => const ResumeScreen(),
                  ),
```

- [ ] **Step 3: Create the screen**

`app/lib/presentation/resume/resume_screen.dart`:

```dart
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/presentation/resume/resume_controller.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';

final _dateFormat = DateFormat.yMMMMd();

const _extToContentType = <String, String>{
  'pdf': 'application/pdf',
  'doc': 'application/msword',
  'docx':
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

class ResumeScreen extends ConsumerStatefulWidget {
  const ResumeScreen({super.key});
  @override
  ConsumerState<ResumeScreen> createState() => _ResumeScreenState();
}

class _ResumeScreenState extends ConsumerState<ResumeScreen> {
  Future<void> _pickAndUpload() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'doc', 'docx'],
      withData: true,
    );
    if (result == null || result.files.isEmpty) return; // cancelled
    final file = result.files.single;
    final bytes = file.bytes;
    final ext = (file.extension ?? '').toLowerCase();
    final contentType = _extToContentType[ext];
    if (bytes == null || contentType == null) {
      _snack('Unsupported file type (PDF, DOC, DOCX).');
      return;
    }
    final ok = await ref.read(resumeControllerProvider.notifier).uploadFromPicked(
          bytes: bytes,
          filename: file.name,
          contentType: contentType,
        );
    if (!mounted) return;
    if (ok) {
      // Parsing is async; nudge the status a couple of times.
      Future.delayed(const Duration(seconds: 2), _refreshIfMounted);
      Future.delayed(const Duration(seconds: 5), _refreshIfMounted);
    } else {
      _snack(_errorText(ref.read(resumeControllerProvider).error));
    }
  }

  void _refreshIfMounted() {
    if (mounted) ref.read(resumeControllerProvider.notifier).refresh();
  }

  void _snack(String msg) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(msg)));

  String _errorText(Object? e) {
    if (e is ApiException && e.statusCode == 415) {
      return 'Unsupported file type (PDF, DOC, DOCX).';
    }
    if (e is ApiException && e.statusCode == 413) {
      return 'File too large (max 10 MB).';
    }
    if (e is NetworkException) return "Couldn't reach KPA.";
    return "Couldn't upload. Try again.";
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(resumeControllerProvider);
    final uploading = state.isLoading;
    return Scaffold(
      appBar: AppBar(title: const Text('Résumé')),
      body: RefreshIndicator(
        onRefresh: () =>
            ref.read(resumeControllerProvider.notifier).refresh(),
        child: ListView(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          children: [
            AsyncValueWidget<ResumeDto?>(
              value: state,
              onRetry: () =>
                  ref.read(resumeControllerProvider.notifier).refresh(),
              data: (resume) => resume == null
                  ? _Empty()
                  : _ResumeCard(resume: resume),
            ),
            const SizedBox(height: KpaSpacing.xl),
            FilledButton.icon(
              onPressed: uploading ? null : _pickAndUpload,
              icon: const Icon(Icons.upload_file),
              label: Text(uploading ? 'Uploading…' : 'Upload / Replace résumé'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: KpaSpacing.xl),
        child: Text(
          'No résumé yet. Upload one so we can match you to roles.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
}

class _ResumeCard extends StatelessWidget {
  const _ResumeCard({required this.resume});
  final ResumeDto resume;

  ({String label, Color fg, Color bg}) _status(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    switch (resume.parseStatus) {
      case ResumeParseStatus.parsed:
        return (label: 'Ready', fg: c.onPrimaryContainer, bg: c.primaryContainer);
      case ResumeParseStatus.failed:
        return (label: "Couldn't parse", fg: c.onErrorContainer, bg: c.errorContainer);
      case ResumeParseStatus.pending:
      case ResumeParseStatus.parsing:
      case ResumeParseStatus.unknown:
        return (
          label: 'Processing…',
          fg: c.onSurfaceVariant,
          bg: c.surfaceContainerHighest
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final s = _status(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(KpaSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(resume.originalFilename, style: theme.textTheme.titleMedium),
            const SizedBox(height: KpaSpacing.xs),
            Text(
              'Uploaded ${_dateFormat.format(resume.createdAt)}',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: KpaSpacing.sm),
            Container(
              padding: const EdgeInsets.symmetric(
                  horizontal: KpaSpacing.sm, vertical: KpaSpacing.xs),
              decoration: BoxDecoration(
                color: s.bg,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(s.label,
                  style: theme.textTheme.labelSmall?.copyWith(color: s.fg)),
            ),
          ],
        ),
      ),
    );
  }
}
```

NOTE: confirm `AsyncValueWidget`'s constructor params (`value`, `data`, `onRetry`) against `lib/presentation/widgets/async_value_widget.dart` and that `data:` accepts a nullable `T` builder; if its API differs, adapt (e.g. handle null inside `data`). Confirm `ApiException`/`NetworkException` shapes in `lib/core/error/exceptions.dart`.

- [ ] **Step 4: Wire the Profile "Resume" row**

In `app/lib/presentation/profile/profile_screen.dart`, replace the disabled Resume `ListTile` (currently `leading: Icon(Icons.description_outlined), title: Text('Resume'), subtitle: Text('Coming soon'), enabled: false`) with:

```dart
            ListTile(
              leading: const Icon(Icons.description_outlined),
              title: const Text('Résumé'),
              subtitle: const Text('Manage your résumé'),
              onTap: () => context.go(Routes.resume),
            ),
```

(`context` + `Routes` are already imported in this file from the profile-edit work; verify.)

- [ ] **Step 5: Write the widget test (rendering states only)**

The real `FilePicker.platform` is a platform channel and isn't exercised here; the controller test (Task 4) covers upload logic. This test covers the screen's render states with a fake repo.

`app/test/widget/resume_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/data/resume/resume_repository.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';
import 'package:kpa_app/presentation/resume/resume_screen.dart';

class _Repo implements ResumeRepository {
  _Repo(this._current);
  final ResumeDto? _current;
  @override
  Future<ResumeDto?> current() async => _current;
  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async =>
      throw UnimplementedError();
}

ResumeDto _dto(ResumeParseStatus s) => ResumeDto(
      id: 'r1',
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: s,
      createdAt: DateTime(2026),
    );

Future<void> _pump(WidgetTester tester, ResumeDto? current) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [resumeRepositoryProvider.overrideWithValue(_Repo(current))],
      child: const MaterialApp(home: ResumeScreen()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('empty state shows prompt + upload button', (tester) async {
    await _pump(tester, null);
    expect(find.textContaining('No résumé yet'), findsOneWidget);
    expect(find.text('Upload / Replace résumé'), findsOneWidget);
  });

  testWidgets('parsed resume shows filename + Ready chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.parsed));
    expect(find.text('cv.pdf'), findsOneWidget);
    expect(find.text('Ready'), findsOneWidget);
  });

  testWidgets('failed resume shows error chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.failed));
    expect(find.text("Couldn't parse"), findsOneWidget);
  });

  testWidgets('parsing resume shows processing chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.parsing));
    expect(find.text('Processing…'), findsOneWidget);
  });
}
```

- [ ] **Step 6: Generate (router) + run + analyze**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/widget/resume_screen_test.dart && flutter analyze lib/presentation/resume lib/presentation/routing`
Expected: PASS; no errors.

- [ ] **Step 7: Commit**

```bash
git add lib/presentation/resume/resume_screen.dart lib/presentation/routing/routes.dart lib/presentation/routing/router.dart lib/presentation/routing/router.g.dart lib/presentation/profile/profile_screen.dart test/widget/resume_screen_test.dart
git commit -m "feat(app): ResumeScreen + /profile/resume route"
```

---

## Task 6: App — Notification DTOs

**Files:**
- Create: `app/lib/data/notifications/notification_dto.dart`
- Test: `app/test/unit/data/notifications/notification_dto_test.dart`

- [ ] **Step 1: Create the DTOs**

`app/lib/data/notifications/notification_dto.dart`:

```dart
import 'package:json_annotation/json_annotation.dart';

part 'notification_dto.g.dart';

/// Mirrors api `NotificationRead` (routes/notifications.py).
@JsonSerializable(createToJson: false)
class NotificationDto {
  const NotificationDto({
    required this.id,
    required this.kind,
    required this.channel,
    required this.status,
    required this.payload,
    required this.sendAfter,
    required this.createdAt,
    this.sentAt,
    this.readAt,
  });

  factory NotificationDto.fromJson(Map<String, dynamic> json) =>
      _$NotificationDtoFromJson(json);

  final String id;
  final String kind;
  final String channel;
  final String status;
  final Map<String, dynamic> payload;
  @JsonKey(name: 'send_after')
  final DateTime sendAfter;
  @JsonKey(name: 'sent_at')
  final DateTime? sentAt;
  @JsonKey(name: 'read_at')
  final DateTime? readAt;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
}

@JsonSerializable(createToJson: false)
class NotificationListItemDto {
  const NotificationListItemDto({required this.notification});

  factory NotificationListItemDto.fromJson(Map<String, dynamic> json) =>
      _$NotificationListItemDtoFromJson(json);

  final NotificationDto notification;
}

@JsonSerializable(createToJson: false)
class NotificationsPageDto {
  const NotificationsPageDto({required this.items, this.nextCursor});

  factory NotificationsPageDto.fromJson(Map<String, dynamic> json) =>
      _$NotificationsPageDtoFromJson(json);

  final List<NotificationListItemDto> items;
  @JsonKey(name: 'next_cursor')
  final String? nextCursor;
}
```

- [ ] **Step 2: Generate + test**

Run: `dart run build_runner build --delete-conflicting-outputs`

`app/test/unit/data/notifications/notification_dto_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';

void main() {
  test('parses the NotificationListResponse wire shape', () {
    final page = NotificationsPageDto.fromJson(const {
      'items': [
        {
          'notification': {
            'id': 'n1',
            'kind': 'application_received',
            'channel': 'in_app',
            'status': 'sent',
            'payload': {'job_id': 'j1', 'job_title': 'Engineer', 'employer_name': 'Acme'},
            'send_after': '2026-05-01T00:00:00Z',
            'sent_at': '2026-05-01T00:00:01Z',
            'read_at': null,
            'created_at': '2026-05-01T00:00:00Z',
          }
        }
      ],
      'next_cursor': null,
    });
    expect(page.items.length, 1);
    final n = page.items.first.notification;
    expect(n.id, 'n1');
    expect(n.kind, 'application_received');
    expect(n.payload['job_id'], 'j1');
    expect(n.readAt, isNull);
    expect(page.nextCursor, isNull);
  });
}
```

Run: `flutter test test/unit/data/notifications/notification_dto_test.dart`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add lib/data/notifications/notification_dto.dart lib/data/notifications/notification_dto.g.dart test/unit/data/notifications/notification_dto_test.dart
git commit -m "feat(app): Notification DTOs"
```

---

## Task 7: App — NotificationApi + NotificationsRepository

**Files:**
- Create: `app/lib/data/notifications/notification_api.dart`, `notifications_repository.dart`, `notifications_repository_impl.dart`
- Test: `app/test/unit/data/notifications/notifications_repository_impl_test.dart`

- [ ] **Step 1: Write the failing test**

`app/test/unit/data/notifications/notifications_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/notifications/notification_api.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _n(String id, {String? readAt}) => {
      'id': id,
      'kind': 'application_received',
      'channel': 'in_app',
      'status': 'sent',
      'payload': {'job_id': 'j1'},
      'send_after': '2026-05-01T00:00:00Z',
      'sent_at': '2026-05-01T00:00:01Z',
      'read_at': readAt,
      'created_at': '2026-05-01T00:00:00Z',
    };

void main() {
  test('fetchPage parses items + next_cursor', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('GET', '/v1/notifications', 200, {
      'items': [
        {'notification': _n('n1')},
      ],
      'next_cursor': 'CUR',
    });
    final repo = NotificationsRepositoryImpl(NotificationApi(dio));
    final page = await repo.fetchPage();
    expect(page.items.single.notification.id, 'n1');
    expect(page.nextCursor, 'CUR');
  });

  test('markRead POSTs to /{id}/read and parses NotificationDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('POST', '/v1/notifications/n1/read', 200,
        _n('n1', readAt: '2026-05-02T00:00:00Z'));
    final repo = NotificationsRepositoryImpl(NotificationApi(dio));
    final dto = await repo.markRead('n1');
    expect(dto.id, 'n1');
    expect(dto.readAt, isNotNull);
  });
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `flutter test test/unit/data/notifications/notifications_repository_impl_test.dart`
Expected: FAIL — undefined.

- [ ] **Step 3: Create API + repository**

`app/lib/data/notifications/notification_api.dart`:

```dart
import 'package:dio/dio.dart';

import 'package:kpa_app/data/notifications/notification_dto.dart';

class NotificationApi {
  NotificationApi(this._dio);
  final Dio _dio;

  Future<NotificationsPageDto> list({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/notifications',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return NotificationsPageDto.fromJson(res.data!);
  }

  Future<NotificationDto> markRead(String id) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/notifications/$id/read',
    );
    return NotificationDto.fromJson(res.data!);
  }
}
```

`app/lib/data/notifications/notifications_repository.dart`:

```dart
import 'package:kpa_app/data/notifications/notification_dto.dart';

abstract interface class NotificationsRepository {
  Future<NotificationsPageDto> fetchPage({String? cursor, int limit});
  Future<NotificationDto> markRead(String id);
}
```

`app/lib/data/notifications/notifications_repository_impl.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/notifications/notification_api.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository.dart';

part 'notifications_repository_impl.g.dart';

class NotificationsRepositoryImpl implements NotificationsRepository {
  NotificationsRepositoryImpl(this._api);
  final NotificationApi _api;

  @override
  Future<NotificationsPageDto> fetchPage({String? cursor, int limit = 20}) async {
    try {
      return await _api.list(cursor: cursor, limit: limit);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<NotificationDto> markRead(String id) async {
    try {
      return await _api.markRead(id);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
NotificationsRepository notificationsRepository(Ref ref) =>
    NotificationsRepositoryImpl(NotificationApi(ref.read(dioProvider)));
```

- [ ] **Step 4: Generate + run**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/data/notifications/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/data/notifications/notification_api.dart lib/data/notifications/notifications_repository.dart lib/data/notifications/notifications_repository_impl.dart lib/data/notifications/notifications_repository_impl.g.dart test/unit/data/notifications/notifications_repository_impl_test.dart
git commit -m "feat(app): NotificationApi + NotificationsRepository"
```

---

## Task 8: App — NotificationsController + title mapper

**Files:**
- Create: `app/lib/presentation/notifications/notifications_controller.dart`, `app/lib/presentation/notifications/notification_title.dart`
- Test: `app/test/unit/presentation/notifications/notifications_controller_test.dart`, `app/test/unit/presentation/notifications/notification_title_test.dart`

- [ ] **Step 1: Create the title mapper**

`app/lib/presentation/notifications/notification_title.dart`:

```dart
import 'package:kpa_app/data/notifications/notification_dto.dart';

/// Human-readable title for a notification, from its kind + payload. Every
/// payload read is null-guarded (payload is an untyped wire dict).
String notificationTitle(NotificationDto n) {
  final p = n.payload;
  switch (n.kind) {
    case 'application_received':
      final job = p['job_title'] as String?;
      final emp = p['employer_name'] as String?;
      if (job != null && emp != null) {
        return 'Application received for $job at $emp';
      }
      if (job != null) return 'Application received for $job';
      return 'Application received';
    default:
      return _humanize(n.kind);
  }
}

String _humanize(String kind) {
  if (kind.isEmpty) return 'Notification';
  final words = kind.replaceAll('_', ' ');
  return words[0].toUpperCase() + words.substring(1);
}
```

NOTE: check `api/src/kpa/routes/applications.py` (and any other notification writer) for the actual `kind` strings + `payload` keys, and add `case` branches for each real kind. `application_received` is the apply trigger; confirm the exact string.

- [ ] **Step 2: Create the controller**

`app/lib/presentation/notifications/notifications_controller.dart`:

```dart
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';
import 'package:kpa_app/presentation/paging/paged_state.dart';
import 'package:kpa_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'notifications_controller.g.dart';

typedef NotificationsState = PagedState<NotificationDto>;

@riverpod
class NotificationsController extends _$NotificationsController {
  @override
  Future<NotificationsState> build() async {
    final page =
        await ref.read(notificationsRepositoryProvider).fetchPage();
    return PagedState(
      items: [for (final it in page.items) it.notification],
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() => loadNextPage<NotificationDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page = await ref
              .read(notificationsRepositoryProvider)
              .fetchPage(cursor: cursor);
          return PagedState(
            items: [for (final it in page.items) it.notification],
            cursor: page.nextCursor,
            hasMore: page.nextCursor != null,
          );
        },
        setState: (s) => state = s,
      );

  /// Mark one notification read and replace it in the loaded list in place
  /// (no invalidate — that would refetch page 1 and reset scroll).
  Future<void> markRead(String id) async {
    final updated =
        await ref.read(notificationsRepositoryProvider).markRead(id);
    final current = state.value;
    if (current == null) return;
    state = AsyncValue.data(
      current.copyWith(
        items: [
          for (final n in current.items) if (n.id == id) updated else n,
        ],
      ),
    );
  }
}
```

- [ ] **Step 3: Generate code**

Run: `dart run build_runner build --delete-conflicting-outputs`
Confirm provider name `notificationsControllerProvider` in the `.g.dart`.

- [ ] **Step 4: Write + run the tests**

`app/test/unit/presentation/notifications/notification_title_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/presentation/notifications/notification_title.dart';

NotificationDto _n(String kind, Map<String, dynamic> payload) => NotificationDto(
      id: 'n1',
      kind: kind,
      channel: 'in_app',
      status: 'sent',
      payload: payload,
      sendAfter: DateTime(2026),
      createdAt: DateTime(2026),
    );

void main() {
  test('application_received with job + employer', () {
    expect(
      notificationTitle(
          _n('application_received', {'job_title': 'Engineer', 'employer_name': 'Acme'})),
      'Application received for Engineer at Acme',
    );
  });
  test('application_received missing payload keys → graceful', () {
    expect(notificationTitle(_n('application_received', {})),
        'Application received');
  });
  test('unknown kind is humanized', () {
    expect(notificationTitle(_n('something_happened', {})), 'Something happened');
  });
}
```

`app/test/unit/presentation/notifications/notifications_controller_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';
import 'package:kpa_app/presentation/notifications/notifications_controller.dart';

NotificationDto _n(String id, {DateTime? readAt}) => NotificationDto(
      id: id,
      kind: 'application_received',
      channel: 'in_app',
      status: 'sent',
      payload: const {'job_id': 'j1'},
      sendAfter: DateTime(2026),
      readAt: readAt,
      createdAt: DateTime(2026),
    );

class _Repo implements NotificationsRepository {
  @override
  Future<NotificationsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      NotificationsPageDto(
        items: [NotificationListItemDto(notification: _n('n1'))],
        nextCursor: null,
      );
  @override
  Future<NotificationDto> markRead(String id) async =>
      _n(id, readAt: DateTime(2026, 2));
}

void main() {
  test('markRead replaces the item in place with read_at set', () async {
    final c = ProviderContainer(overrides: [
      notificationsRepositoryProvider.overrideWithValue(_Repo()),
    ]);
    addTearDown(c.dispose);
    await c.read(notificationsControllerProvider.future);
    await c.read(notificationsControllerProvider.notifier).markRead('n1');
    final items = c.read(notificationsControllerProvider).value!.items;
    expect(items.single.readAt, isNotNull);
  });
}
```

Run: `flutter test test/unit/presentation/notifications/`
Expected: PASS. Fix provider name / `NotificationsPageDto`/`NotificationListItemDto` constructors if they differ from Task 6.

- [ ] **Step 5: Commit**

```bash
git add lib/presentation/notifications/notifications_controller.dart lib/presentation/notifications/notifications_controller.g.dart lib/presentation/notifications/notification_title.dart test/unit/presentation/notifications/
git commit -m "feat(app): NotificationsController + title mapper"
```

---

## Task 9: App — NotificationsScreen + routes + Profile row

**Files:**
- Create: `app/lib/presentation/notifications/notifications_screen.dart`
- Modify: `app/lib/presentation/routing/routes.dart`, `app/lib/presentation/routing/router.dart`, `app/lib/presentation/profile/profile_screen.dart`
- Test: `app/test/widget/notifications_screen_test.dart`

- [ ] **Step 1: Add the route constant**

In `routes.dart`, inside `Routes`:

```dart
  static const notifications = '/profile/notifications';
```

- [ ] **Step 2: Register the nested routes**

In `router.dart`, add import:

```dart
import 'package:kpa_app/presentation/notifications/notifications_screen.dart';
```

In the profile `GoRoute`'s `routes:` (now `edit`, `resume`), add a `notifications` route WITH a `jobs/:id` child so a notification opens job detail in the profile stack:

```dart
                  GoRoute(
                    path: 'notifications',
                    builder: (_, __) => const NotificationsScreen(),
                    routes: [
                      GoRoute(
                        path: 'jobs/:id',
                        builder: (_, s) =>
                            JobDetailScreen(jobId: s.pathParameters['id']!),
                      ),
                    ],
                  ),
```

(`JobDetailScreen` is already imported in `router.dart`.)

- [ ] **Step 3: Create the screen**

`app/lib/presentation/notifications/notifications_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/presentation/notifications/notifications_controller.dart';
import 'package:kpa_app/presentation/notifications/notification_title.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

final _dateFormat = DateFormat.yMMMd();

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});
  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(notificationsControllerProvider.notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _onTap(NotificationDto n) async {
    await ref.read(notificationsControllerProvider.notifier).markRead(n.id);
    if (!mounted) return;
    final jobId = n.payload['job_id'];
    if (jobId is String && jobId.isNotEmpty) {
      context.go('${Routes.notifications}/jobs/$jobId');
    }
  }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(notificationsControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: AsyncValueWidget<NotificationsState>(
        value: value,
        onRetry: () =>
            ref.read(notificationsControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => const Center(child: Text('No notifications yet')),
        data: (s) => RefreshIndicator(
          onRefresh: () =>
              ref.read(notificationsControllerProvider.notifier).refresh(),
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(KpaSpacing.lg),
            itemCount: s.items.length + 1,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              if (i == s.items.length) {
                return s.isLoadingMore
                    ? const Padding(
                        padding: EdgeInsets.all(KpaSpacing.lg),
                        child: KpaLoadingView(),
                      )
                    : const SizedBox.shrink();
              }
              final n = s.items[i];
              final unread = n.readAt == null;
              return ListTile(
                leading: unread
                    ? const Icon(Icons.circle, size: 10, color: Colors.blue)
                    : const SizedBox(width: 10),
                title: Text(
                  notificationTitle(n),
                  style: TextStyle(
                    fontWeight: unread ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
                subtitle: Text(_dateFormat.format(n.createdAt)),
                onTap: () => _onTap(n),
              );
            },
          ),
        ),
      ),
    );
  }
}
```

NOTE: confirm `AsyncValueWidget` supports the `isEmpty`/`empty` params (it's used that way in `applications_screen.dart`) and mirror that file's exact usage if it differs. Confirm `KpaLoadingView` exists at `lib/presentation/widgets/kpa_loading_view.dart` (used in `applications_screen.dart`).

- [ ] **Step 4: Wire the Profile "Notifications" row**

In `profile_screen.dart`, replace the disabled Notifications `ListTile` with:

```dart
            ListTile(
              leading: const Icon(Icons.notifications_outlined),
              title: const Text('Notifications'),
              subtitle: const Text('View your notifications'),
              onTap: () => context.go(Routes.notifications),
            ),
```

- [ ] **Step 5: Write the widget test**

`app/test/widget/notifications_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';
import 'package:kpa_app/presentation/notifications/notifications_screen.dart';

NotificationDto _n(String id, {DateTime? readAt}) => NotificationDto(
      id: id,
      kind: 'application_received',
      channel: 'in_app',
      status: 'sent',
      payload: const {'job_title': 'Engineer', 'employer_name': 'Acme'},
      sendAfter: DateTime(2026),
      readAt: readAt,
      createdAt: DateTime(2026),
    );

class _Repo implements NotificationsRepository {
  final List<String> marked = [];
  @override
  Future<NotificationsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      NotificationsPageDto(
        items: [NotificationListItemDto(notification: _n('n1'))],
        nextCursor: null,
      );
  @override
  Future<NotificationDto> markRead(String id) async {
    marked.add(id);
    return _n(id, readAt: DateTime(2026, 2));
  }
}

void main() {
  testWidgets('renders friendly title + marks read on tap', (tester) async {
    final repo = _Repo();
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => const NotificationsScreen()),
    ]);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [notificationsRepositoryProvider.overrideWithValue(repo)],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Application received for Engineer at Acme'),
        findsOneWidget);

    await tester.tap(find.text('Application received for Engineer at Acme'));
    await tester.pumpAndSettle();
    expect(repo.marked, ['n1']);
  });
}
```

NOTE: the tap navigates to `/profile/notifications/jobs/...` only if `payload['job_id']` is set; this fixture omits `job_id`, so no navigation occurs (keeps the single-route test simple) — the assertion is just that `markRead` fired.

- [ ] **Step 6: Generate + run + analyze + format**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test && flutter analyze lib test && dart format lib test`
Expected: ALL tests pass; no analyzer errors/warnings (pre-existing infos OK).

- [ ] **Step 7: Commit**

```bash
git add lib/presentation/notifications/notifications_screen.dart lib/presentation/routing/routes.dart lib/presentation/routing/router.dart lib/presentation/routing/router.g.dart lib/presentation/profile/profile_screen.dart test/widget/notifications_screen_test.dart
git commit -m "feat(app): NotificationsScreen + /profile/notifications route"
```

---

## Final verification

- [ ] Backend: `cd api && uv run pytest -q -m integration tests/integration/test_resumes_list.py && uv run ruff check src/ tests/ && uv run mypy`
- [ ] App: `cd app && flutter analyze lib test && flutter test`
- [ ] Manual: sign in → Profile → Résumé → upload a PDF → status moves to Ready; Profile → Notifications → see apply notifications, tap one → marks read + (if job_id) opens the job.
