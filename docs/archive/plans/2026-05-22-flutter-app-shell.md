# Flutter App Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a new `app/` Flutter package — iOS + Android + Web — that signs the user in via Google, lists matched jobs, opens job details, and supports the apply / withdraw / save / unsave mutations against the existing `/v1` endpoints, on top of a foundation (dio + refresh interceptor, Riverpod, go_router, design tokens, AsyncValue primitives) designed to outlive v0.

**Architecture:** Pragmatic Clean Architecture with three layers (`data/`, `domain/`, `presentation/`) + a `core/` for framework primitives. Riverpod 2.x with codegen for DI and state; dio + freezed for the HTTP plane; go_router `StatefulShellRoute` for tab-bar navigation; single-flight refresh interceptor for transparent 401 handling; `flutter_secure_storage` for refresh-token persistence; Google Sign-In via the `google_sign_in` + `google_sign_in_web` plugin pair.

**Tech Stack:** Flutter 3.27.x (stable channel), Dart 3.6+, Riverpod 2.6, freezed 2.5, dio 5.7, go_router 14.6, google_sign_in 6.2, flutter_secure_storage 9.2.

**Spec ref:** `docs/superpowers/specs/2026-05-21-flutter-app-shell-design.md` (approved 2026-05-21).

---

## File structure after this plan

```
app/                                                              NEW PACKAGE
├── pubspec.yaml                                                  Dep manifest + asset/font config
├── analysis_options.yaml                                         very_good_analysis lint ruleset
├── build.yaml                                                    riverpod_generator + freezed + json_serializable + go_router_builder
├── README.md                                                     Run / build / env-var docs
├── .gitignore                                                    Flutter defaults + web/index.html (generated)
├── .env.example                                                  --dart-define convenience template
├── lib/
│   ├── main.dart                                                 runApp(ProviderScope(...))
│   ├── app.dart                                                  KpaApp widget (ThemeData + Router)
│   ├── core/
│   │   ├── config/env.dart                                       String.fromEnvironment validation
│   │   ├── error/exceptions.dart                                 AuthException, ApiException, NetworkException
│   │   ├── error/error_mapping.dart                              DioException → typed exception
│   │   └── log/logger.dart                                       structured-ish logger (println in dev)
│   ├── data/
│   │   ├── api/
│   │   │   ├── dio_provider.dart                                 Riverpod-exposed Dio instance
│   │   │   ├── auth_header_interceptor.dart                      adds Authorization on non-skip requests
│   │   │   ├── request_id_interceptor.dart                       uuid4 → X-Request-Id, stash in extra
│   │   │   └── refresh_on_401_interceptor.dart                   single-flight refresh + replay
│   │   ├── auth/
│   │   │   ├── token_storage.dart                                flutter_secure_storage wrapper
│   │   │   ├── google_sign_in_data_source.dart                   wraps google_sign_in for all platforms
│   │   │   ├── auth_dto.dart                                     SignInResponseDto + RefreshResponseDto (freezed)
│   │   │   └── auth_repository_impl.dart                         AuthRepository concrete impl
│   │   ├── feed/
│   │   │   ├── feed_dto.dart                                     FeedItemDto + FeedPageDto + JobSummaryDto + EmployerSummaryDto + ExplanationDto + MatchSummaryDto (freezed)
│   │   │   ├── feed_api.dart                                     GET /v1/feed wrapper
│   │   │   └── feed_repository_impl.dart                         FeedRepository concrete impl
│   │   ├── jobs/
│   │   │   ├── jobs_dto.dart                                     JobDetailDto + ApplicationDto + SavedJobDto (freezed)
│   │   │   ├── jobs_api.dart                                     GET /v1/jobs/{id}, POST/DELETE save, POST apply
│   │   │   ├── jobs_repository_impl.dart                         JobsRepository concrete impl
│   │   │   ├── applications_api.dart                             GET /v1/applications, PATCH withdraw
│   │   │   ├── applications_repository_impl.dart                 ApplicationsRepository concrete impl
│   │   │   ├── saved_jobs_api.dart                               GET /v1/saved
│   │   │   └── saved_jobs_repository_impl.dart                   SavedJobsRepository concrete impl
│   │   └── me/
│   │       ├── me_dto.dart                                       MeDto + ApplicantSummaryDto (freezed)
│   │       ├── me_api.dart                                       GET /v1/me
│   │       └── me_repository_impl.dart                           MeRepository concrete impl
│   ├── domain/
│   │   ├── auth/auth_repository.dart                             AuthRepository abstract + AuthState sealed
│   │   ├── feed/feed_repository.dart                             FeedRepository abstract + FeedPage value
│   │   ├── jobs/jobs_repository.dart                             JobsRepository abstract + JobDetail value
│   │   ├── jobs/applications_repository.dart                     ApplicationsRepository abstract + ApplicationsPage value
│   │   ├── jobs/saved_jobs_repository.dart                       SavedJobsRepository abstract + SavedJobsPage value
│   │   └── me/me_repository.dart                                 MeRepository abstract
│   └── presentation/
│       ├── routing/
│       │   ├── router.dart                                       GoRouter config + StatefulShellRoute + auth redirect
│       │   └── routes.dart                                       Typed route classes (go_router_builder)
│       ├── theme/
│       │   ├── kpa_colors.dart                                   palette + score-band semantics
│       │   ├── kpa_typography.dart                               Inter via google_fonts
│       │   ├── kpa_spacing.dart                                  4-base spacing constants
│       │   ├── kpa_radii.dart                                    radius constants
│       │   ├── kpa_motion.dart                                   re-exports Material defaults
│       │   └── build_theme.dart                                  ThemeData buildTheme(Brightness)
│       ├── widgets/
│       │   ├── kpa_loading_view.dart
│       │   ├── kpa_error_view.dart
│       │   ├── kpa_empty_state.dart
│       │   ├── kpa_score_badge.dart
│       │   ├── kpa_shell_scaffold.dart                           bottom-nav scaffold for StatefulShellRoute
│       │   └── async_value_widget.dart                           AsyncValue three-way switch helper
│       ├── auth/
│       │   ├── auth_providers.dart                               authStateProvider, accessTokenProvider, repo wiring
│       │   ├── sign_in_controller.dart                           mutation controller
│       │   └── sign_in_screen.dart
│       ├── splash/
│       │   ├── bootstrap_controller.dart                         silent-refresh sequence
│       │   └── splash_screen.dart
│       ├── feed/
│       │   ├── feed_providers.dart                               feedRepositoryProvider wiring
│       │   ├── feed_controller.dart                              paginated AsyncNotifier
│       │   ├── feed_item_card.dart                               reused on Saved tab
│       │   └── feed_screen.dart
│       ├── job_detail/
│       │   ├── job_detail_providers.dart                         jobsRepositoryProvider wiring
│       │   ├── job_detail_controller.dart                        AsyncNotifier .family(jobId)
│       │   ├── apply_to_job_controller.dart                      mutation
│       │   ├── withdraw_application_controller.dart              mutation
│       │   ├── save_job_controller.dart                          mutation
│       │   ├── unsave_job_controller.dart                        mutation
│       │   ├── action_bar.dart                                   sticky bottom action-bar widget
│       │   └── job_detail_screen.dart
│       ├── applications/
│       │   ├── applications_providers.dart
│       │   ├── applications_controller.dart                      paginated AsyncNotifier
│       │   └── applications_screen.dart
│       ├── saved/
│       │   ├── saved_providers.dart
│       │   ├── saved_controller.dart                             paginated AsyncNotifier
│       │   └── saved_screen.dart
│       └── profile/
│           ├── profile_providers.dart                            meRepositoryProvider wiring
│           ├── me_controller.dart
│           ├── sign_out_controller.dart                          mutation
│           └── profile_screen.dart
├── ios/Runner/
│   ├── Info.plist                                                GIDClientID + URL scheme + ATS local-net
│   ├── Debug.xcconfig.example                                    GOOGLE_IOS_CLIENT_ID template (real one gitignored)
│   └── Release.xcconfig.example
├── android/app/src/
│   ├── main/AndroidManifest.xml                                  usesCleartextTraffic + networkSecurityConfig (debug)
│   ├── main/res/xml/network_security_config.xml                  10.0.2.2 + 127.0.0.1 cleartext whitelist
│   └── debug/AndroidManifest.xml                                 debug-only manifest overlay
├── web/
│   ├── index.template.html                                       sources GIS meta tag from {{GOOGLE_WEB_CLIENT_ID}}
│   └── index.html                                                generated, .gitignored
├── scripts/
│   └── build_web.sh                                              substitutes template then flutter build web
└── test/
    ├── helpers/
    │   ├── test_overrides.dart                                   Riverpod ProviderContainer factory
    │   └── fake_repositories.dart                                FakeAuthRepository, FakeFeedRepository, ...
    ├── unit/
    │   ├── core/error/error_mapping_test.dart
    │   ├── data/api/refresh_on_401_interceptor_test.dart         BIG — single-flight, replay, failure, concurrent
    │   ├── data/api/auth_header_interceptor_test.dart
    │   ├── data/api/request_id_interceptor_test.dart
    │   ├── data/auth/token_storage_test.dart
    │   ├── data/auth/auth_repository_impl_test.dart
    │   ├── data/feed/feed_repository_impl_test.dart
    │   ├── data/jobs/jobs_repository_impl_test.dart
    │   ├── data/jobs/applications_repository_impl_test.dart
    │   ├── data/jobs/saved_jobs_repository_impl_test.dart
    │   ├── data/me/me_repository_impl_test.dart
    │   └── presentation/
    │       ├── splash/bootstrap_controller_test.dart
    │       ├── feed/feed_controller_test.dart
    │       ├── job_detail/apply_to_job_controller_test.dart
    │       └── ... (one per controller)
    ├── widget/
    │   ├── splash_screen_test.dart                               loading + success-redirect + error render
    │   ├── sign_in_screen_test.dart
    │   ├── feed_screen_test.dart
    │   ├── job_detail_screen_test.dart
    │   ├── applications_screen_test.dart
    │   ├── saved_screen_test.dart
    │   └── profile_screen_test.dart
    └── integration/
        └── golden_path_test.dart                                 sign-in → feed → detail → apply

.github/workflows/
└── app.yml                                                       NEW — analyze + format + test on app/** PRs

CLAUDE.md                                                          APPEND — Flutter app section
```

---

## Notes for all tasks

- **Working directory** for every command below is `/Users/ahamadshah/ahamed_personal/kpa/app/` unless stated otherwise. Plan-execution-time check: `pwd` should print `…/kpa/app` before running `flutter` or `dart` commands.
- **All code-gen artifacts** (`*.g.dart`, `*.freezed.dart`) are produced by `dart run build_runner build --delete-conflicting-outputs`. Run this after every task that adds or edits an `@freezed`, `@riverpod`, `@JsonSerializable`, or `@TypedGoRoute` annotation. Generated files are checked into git (matches Riverpod-codegen convention — keeps `flutter analyze` clean on fresh clones).
- **Commit cadence:** one task = one commit, message follows the repo's past pattern (`feat(app): …`, `test(app): …`, `chore(app): …`, `docs(app): …`).
- **Branch:** continue on `feat/app-shell-foundation` (already checked out from the spec commit).

---

## Phase 1 — Project scaffolding

### Task 1: Generate the Flutter package + clean the boilerplate

**Files:**
- Create: `app/` (whole directory via `flutter create`)
- Delete: `app/test/widget_test.dart` (counter demo)
- Delete: `app/lib/main.dart` (will be rewritten in Task 30)
- Delete: `app/integration_test/` (Flutter's `integration_test` package; we use `flutter_test`'s `testWidgets` for our one integration test instead — simpler, no separate runner)

- [ ] **Step 1: Run flutter create from the repo root**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
flutter create \
  --org com.kpa \
  --project-name kpa_app \
  --description "KPA applicant app — iOS, Android, Web" \
  --platforms=ios,android,web \
  --no-pub \
  app
```

Expected output: a tree under `app/` with `lib/main.dart`, `pubspec.yaml`, `ios/`, `android/`, `web/`, `test/widget_test.dart`. The `--no-pub` flag skips `pub get` (we'll run it ourselves after editing `pubspec.yaml`).

- [ ] **Step 2: Verify the create output**

```bash
ls app/
```

Expected to include: `android/  ios/  lib/  pubspec.yaml  test/  web/  analysis_options.yaml`.

- [ ] **Step 3: Delete the boilerplate**

```bash
rm app/lib/main.dart
rm app/test/widget_test.dart
rm -rf app/integration_test
```

- [ ] **Step 4: Commit the scaffolding**

```bash
git add app/ -- ':!app/lib/main.dart' ':!app/test/widget_test.dart'
git status --short  # verify only `app/` files staged
git commit -m "$(cat <<'EOF'
chore(app): scaffold flutter package via flutter create

iOS + Android + Web platforms; com.kpa org; project name kpa_app.
Demo main.dart and counter widget test deleted; they'll be rewritten
on top of the foundation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Wire pubspec.yaml — runtime deps, dev deps, font asset

**Files:**
- Overwrite: `app/pubspec.yaml`

The generated `pubspec.yaml` has the Flutter default. Replace it with the full dep set the foundation needs.

- [ ] **Step 1: Overwrite `app/pubspec.yaml`**

```yaml
name: kpa_app
description: KPA applicant app — iOS, Android, Web.
publish_to: 'none'
version: 0.1.0+1

environment:
  sdk: ^3.6.0
  flutter: ">=3.27.0"

dependencies:
  flutter:
    sdk: flutter

  # State management
  flutter_riverpod: ^2.6.1
  riverpod_annotation: ^2.6.1

  # Models / serialization
  freezed_annotation: ^2.4.4
  json_annotation: ^4.9.0

  # Routing
  go_router: ^14.6.2

  # HTTP
  dio: ^5.7.0

  # Auth + storage
  flutter_secure_storage: ^9.2.2
  google_sign_in: ^6.2.2
  google_sign_in_web: ^0.12.4+3

  # Misc
  google_fonts: ^6.2.1
  package_info_plus: ^8.1.1
  intl: ^0.19.0
  uuid: ^4.5.1                  # X-Request-Id generation

dev_dependencies:
  flutter_test:
    sdk: flutter

  # Lints
  very_good_analysis: ^6.0.0

  # Code-gen
  build_runner: ^2.4.13
  freezed: ^2.5.7
  json_serializable: ^6.8.0
  riverpod_generator: ^2.6.3
  go_router_builder: ^2.7.1
  custom_lint: ^0.7.0           # required by riverpod_lint
  riverpod_lint: ^2.6.3         # surfaces Riverpod misuse in `flutter analyze`

  # Test infra
  mocktail: ^1.0.4
  http_mock_adapter: ^0.6.1

flutter:
  uses-material-design: true
  # No font assets here — google_fonts fetches Inter at runtime and caches.
  # If we later bundle Inter as an asset, register it in this `fonts:` section.
```

- [ ] **Step 2: Run `flutter pub get`**

```bash
cd app
flutter pub get
```

Expected: "Got dependencies!" plus a list of resolved versions. No errors. If a transitive version conflict surfaces, prefer raising the upper bound on the conflicting package over downgrading.

- [ ] **Step 3: Sanity-check the resolution**

```bash
flutter pub deps --no-dev | head -30
```

Expected: top-level package `kpa_app`, with the runtime deps from above listed under it.

- [ ] **Step 4: Commit**

```bash
git add app/pubspec.yaml app/pubspec.lock
git commit -m "$(cat <<'EOF'
chore(app): pin runtime + dev dependencies

Riverpod 2.6 + codegen, freezed 2.5, dio 5.7, go_router 14.6,
flutter_secure_storage 9.2, google_sign_in 6.2 + web 0.12.
Dev: very_good_analysis, build_runner, mocktail, http_mock_adapter.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Lint rules, build config, gitignore, env template

**Files:**
- Overwrite: `app/analysis_options.yaml`
- Create: `app/build.yaml`
- Modify: `app/.gitignore`
- Create: `app/.env.example`

- [ ] **Step 1: Overwrite `app/analysis_options.yaml`**

```yaml
include: package:very_good_analysis/analysis_options.yaml

analyzer:
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"
    - "**/build/**"
  plugins:
    - custom_lint

linter:
  rules:
    # very_good_analysis is strict; loosen the rules that fight with our patterns:
    public_member_api_docs: false       # internal app; not a published package
    sort_pub_dependencies: false        # pubspec.yaml is hand-grouped by purpose
    avoid_classes_with_only_static_members: false  # used by KpaSpacing, KpaRadii
```

- [ ] **Step 2: Create `app/build.yaml`**

```yaml
targets:
  $default:
    builders:
      freezed:
        enabled: true
      json_serializable:
        enabled: true
        options:
          explicit_to_json: true
          field_rename: snake            # API uses snake_case; Dart uses camelCase
          create_factory: true
          create_to_json: true
      riverpod_generator:
        enabled: true
      go_router_builder:
        enabled: true
```

`field_rename: snake` makes `@JsonSerializable()` accept the backend's `applicant_id` / `total_score` etc. without per-field `@JsonKey(name: '...')` overrides.

- [ ] **Step 3: Append to `app/.gitignore`**

`flutter create` already generated a reasonable `.gitignore`. Append:

```gitignore

# Generated by our own build script — see scripts/build_web.sh
/web/index.html

# Local env override for --dart-define convenience
.env
.env.local

# Xcode configs containing real client IDs
/ios/Runner/Debug.xcconfig
/ios/Runner/Release.xcconfig
```

- [ ] **Step 4: Create `app/.env.example`**

```bash
# Convenience template for local development.
# Copy to .env (gitignored) and source before `flutter run`.
# `flutter` itself does not read .env files; we read them via --dart-define-from-file
# (Flutter 3.7+). Example:
#
#   flutter run -d chrome --dart-define-from-file=.env

KPA_API_BASE_URL=http://localhost:8000
KPA_GOOGLE_WEB_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
KPA_BUILD_ENV=local
```

- [ ] **Step 5: Commit**

```bash
git add app/analysis_options.yaml app/build.yaml app/.gitignore app/.env.example
git commit -m "$(cat <<'EOF'
chore(app): lint, codegen, gitignore, env template

very_good_analysis with three loosened rules; build.yaml configures
freezed + json_serializable (snake field rename) + riverpod_generator
+ go_router_builder; generated web/index.html and Debug/Release
xcconfigs are gitignored.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 — Core layer

### Task 4: `core/config/env.dart` — build-time env validation

**Files:**
- Create: `app/lib/core/config/env.dart`
- Create: `app/test/unit/core/config/env_test.dart`

`String.fromEnvironment` returns `''` for an unset var (NOT null), so validation uses emptiness checks. We fail fast at app start so missing env vars surface before any UI renders.

- [ ] **Step 1: Write the failing test**

Create `app/test/unit/core/config/env_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/config/env.dart';

void main() {
  group('Env', () {
    test('exposes the four documented getters', () {
      // We can't really test --dart-define behavior in a unit test without
      // spawning a subprocess. This test is a structural smoke test that the
      // getters exist and return strings.
      expect(Env.apiBaseUrl, isA<String>());
      expect(Env.googleWebClientId, isA<String>());
      expect(Env.buildEnv, isA<String>());
      expect(Env.isDev, isA<bool>());
    });

    test('validateOrThrow lists every missing required var in one message', () {
      // We can't drive --dart-define from a test, so we test the helper
      // directly with explicit args.
      final missing = Env.collectMissing(
        apiBaseUrl: '',
        googleWebClientId: '',
      );
      expect(missing, equals(['KPA_API_BASE_URL', 'KPA_GOOGLE_WEB_CLIENT_ID']));
    });

    test('collectMissing returns empty when everything set', () {
      final missing = Env.collectMissing(
        apiBaseUrl: 'http://localhost:8000',
        googleWebClientId: 'abc.apps.googleusercontent.com',
      );
      expect(missing, isEmpty);
    });

    test('validateOrThrow throws with all missing vars and a fix hint', () {
      expect(
        () => Env.validateGiven(apiBaseUrl: '', googleWebClientId: ''),
        throwsA(
          isA<StateError>().having(
            (e) => e.message,
            'message',
            allOf(
              contains('KPA_API_BASE_URL'),
              contains('KPA_GOOGLE_WEB_CLIENT_ID'),
              contains('--dart-define'),
            ),
          ),
        ),
      );
    });
  });
}
```

- [ ] **Step 2: Run the test — expect failure**

```bash
cd app
flutter test test/unit/core/config/env_test.dart
```

Expected: compile error ("`Env` not defined").

- [ ] **Step 3: Implement `app/lib/core/config/env.dart`**

```dart
/// Build-time environment configuration.
///
/// All values are sourced from `--dart-define` at compile time via
/// [String.fromEnvironment]. Unset vars come back as the empty string,
/// not null, so [collectMissing] tests for emptiness.
///
/// Call [validateOrThrow] from `main()` before `runApp` — a missing
/// required var should fail fast with a printable message.
abstract final class Env {
  static const apiBaseUrl = String.fromEnvironment('KPA_API_BASE_URL');
  static const googleWebClientId = String.fromEnvironment('KPA_GOOGLE_WEB_CLIENT_ID');
  static const buildEnv = String.fromEnvironment('KPA_BUILD_ENV', defaultValue: 'local');

  static bool get isDev => buildEnv != 'prod';

  /// Validate the compiled-in values. Throws [StateError] if anything required is missing.
  static void validateOrThrow() {
    validateGiven(apiBaseUrl: apiBaseUrl, googleWebClientId: googleWebClientId);
  }

  /// Internal helper, exposed for testing. Mirrors [validateOrThrow] but takes args.
  static void validateGiven({
    required String apiBaseUrl,
    required String googleWebClientId,
  }) {
    final missing = collectMissing(
      apiBaseUrl: apiBaseUrl,
      googleWebClientId: googleWebClientId,
    );
    if (missing.isEmpty) return;
    throw StateError(
      'Missing required --dart-define vars: ${missing.join(', ')}. '
      'Pass them on the flutter command line, e.g.:\n'
      '  flutter run --dart-define=KPA_API_BASE_URL=http://localhost:8000 '
      '--dart-define=KPA_GOOGLE_WEB_CLIENT_ID=<your-id>\n'
      'Or use --dart-define-from-file=.env (see app/.env.example).',
    );
  }

  /// Pure helper: returns the names of unset required vars.
  static List<String> collectMissing({
    required String apiBaseUrl,
    required String googleWebClientId,
  }) {
    return [
      if (apiBaseUrl.isEmpty) 'KPA_API_BASE_URL',
      if (googleWebClientId.isEmpty) 'KPA_GOOGLE_WEB_CLIENT_ID',
    ];
  }
}
```

- [ ] **Step 4: Run the test — expect pass**

```bash
flutter test test/unit/core/config/env_test.dart
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/lib/core/config/env.dart app/test/unit/core/config/env_test.dart
git commit -m "$(cat <<'EOF'
feat(app): core/config/env with boot-time validation

String.fromEnvironment getters for KPA_API_BASE_URL,
KPA_GOOGLE_WEB_CLIENT_ID, KPA_BUILD_ENV. Env.validateOrThrow()
fails fast with a printable hint listing every missing var.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `core/error/exceptions.dart` + `error_mapping.dart` — typed exceptions

**Files:**
- Create: `app/lib/core/error/exceptions.dart`
- Create: `app/lib/core/error/error_mapping.dart`
- Create: `app/test/unit/core/error/error_mapping_test.dart`

Three exception types map onto the backend's response shape (RFC 7807 `application/problem+json` documented in `api/CLAUDE.md`). All three carry an optional `requestId` so they correlate with backend logs.

- [ ] **Step 1: Write the failing test**

Create `app/test/unit/core/error/error_mapping_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/error_mapping.dart';
import 'package:kpa_app/core/error/exceptions.dart';

DioException _dioErrWithResponse({
  required int status,
  required Map<String, dynamic> body,
  String? requestId,
}) {
  final requestOptions = RequestOptions(path: '/v1/feed');
  return DioException(
    requestOptions: requestOptions,
    response: Response<Map<String, dynamic>>(
      requestOptions: requestOptions,
      statusCode: status,
      data: body,
      headers: requestId == null
          ? Headers()
          : Headers.fromMap({'x-request-id': [requestId]}),
    ),
    type: DioExceptionType.badResponse,
  );
}

void main() {
  group('mapDioException', () {
    test('401 with invalid_access_token slug → AuthException', () {
      final e = _dioErrWithResponse(
        status: 401,
        body: {'type': 'about:blank', 'title': 'Unauthorized', 'status': 401, 'slug': 'invalid_access_token', 'detail': 'token invalid'},
        requestId: 'req-1',
      );
      final mapped = mapDioException(e);
      expect(mapped, isA<AuthException>());
      expect((mapped as AuthException).slug, equals('invalid_access_token'));
      expect(mapped.requestId, equals('req-1'));
    });

    test('403 not_an_applicant → ApiException with slug', () {
      final e = _dioErrWithResponse(
        status: 403,
        body: {'status': 403, 'slug': 'not_an_applicant', 'detail': 'recruiters cannot upload resumes'},
      );
      final mapped = mapDioException(e);
      expect(mapped, isA<ApiException>());
      expect((mapped as ApiException).statusCode, equals(403));
      expect(mapped.slug, equals('not_an_applicant'));
    });

    test('500 with empty body → ApiException with status only', () {
      final e = _dioErrWithResponse(status: 500, body: {});
      final mapped = mapDioException(e);
      expect(mapped, isA<ApiException>());
      expect((mapped as ApiException).slug, isNull);
    });

    test('connection error → NetworkException', () {
      final e = DioException(
        requestOptions: RequestOptions(path: '/v1/feed'),
        type: DioExceptionType.connectionError,
        message: 'connection refused',
      );
      final mapped = mapDioException(e);
      expect(mapped, isA<NetworkException>());
    });

    test('connection timeout → NetworkException', () {
      final e = DioException(
        requestOptions: RequestOptions(path: '/v1/feed'),
        type: DioExceptionType.connectionTimeout,
      );
      expect(mapDioException(e), isA<NetworkException>());
    });
  });
}
```

- [ ] **Step 2: Run the test — expect failure**

```bash
flutter test test/unit/core/error/error_mapping_test.dart
```

Expected: compile errors (`AuthException`, `ApiException`, `NetworkException`, `mapDioException` not defined).

- [ ] **Step 3: Implement `app/lib/core/error/exceptions.dart`**

```dart
/// Base for all typed exceptions thrown from the data layer.
sealed class KpaException implements Exception {
  const KpaException({this.requestId, this.cause});

  /// X-Request-Id from the response (when present). Pair this with backend
  /// logs to chase a single request end-to-end.
  final String? requestId;

  /// The underlying exception that triggered this one (e.g., the original
  /// DioException for an [ApiException]). Useful for `error: e, stackTrace:`
  /// in structured logging.
  final Object? cause;
}

/// Authentication failures — bad token, expired session, missing bearer.
/// The refresh interceptor handles 401 → retry transparently; an
/// [AuthException] reaches the screen only after the refresh itself failed
/// (or the request was unauthenticated to begin with).
final class AuthException extends KpaException {
  const AuthException({
    required this.slug,
    this.detail,
    super.requestId,
    super.cause,
  });

  final String slug;        // e.g., invalid_access_token, missing_bearer_token
  final String? detail;     // backend's user-facing detail (problem+json)

  @override
  String toString() => 'AuthException($slug${detail == null ? '' : ': $detail'})';
}

/// Any non-401 4xx/5xx response from the backend.
final class ApiException extends KpaException {
  const ApiException({
    required this.statusCode,
    this.slug,
    this.detail,
    super.requestId,
    super.cause,
  });

  final int statusCode;
  final String? slug;
  final String? detail;

  @override
  String toString() => 'ApiException($statusCode${slug == null ? '' : ' $slug'}${detail == null ? '' : ': $detail'})';
}

/// Network-layer failure — DNS, connection refused, timeout.
final class NetworkException extends KpaException {
  const NetworkException({this.message, super.cause});

  final String? message;

  @override
  String toString() => 'NetworkException(${message ?? 'unknown'})';
}
```

- [ ] **Step 4: Implement `app/lib/core/error/error_mapping.dart`**

```dart
import 'package:dio/dio.dart';
import 'exceptions.dart';

/// Map a [DioException] into a typed [KpaException].
///
/// Call from dio's `onError` interceptor (or inside each repo's catch block).
/// 401 + slug `invalid_access_token` → [AuthException] so the
/// refresh-on-401 interceptor can be selective; other 4xx/5xx → [ApiException];
/// transport errors → [NetworkException].
KpaException mapDioException(DioException e) {
  final response = e.response;
  final requestId = response?.headers.value('x-request-id');

  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.connectionError:
      return NetworkException(message: e.message, cause: e);

    case DioExceptionType.badCertificate:
    case DioExceptionType.cancel:
    case DioExceptionType.unknown:
      // Unknown / cancel — bucket into NetworkException so the UI shows a
      // recoverable error rather than a 500-style message.
      if (response == null) {
        return NetworkException(message: e.message, cause: e);
      }
      // fall through to badResponse handling
      return _mapResponse(response, requestId, e);

    case DioExceptionType.badResponse:
      if (response == null) {
        return ApiException(statusCode: 0, cause: e);
      }
      return _mapResponse(response, requestId, e);
  }
}

KpaException _mapResponse(Response<dynamic> response, String? requestId, DioException cause) {
  final body = response.data;
  final slug = body is Map ? body['slug'] as String? : null;
  final detail = body is Map ? body['detail'] as String? : null;
  final status = response.statusCode ?? 0;

  if (status == 401 && slug == 'invalid_access_token') {
    return AuthException(slug: slug!, detail: detail, requestId: requestId, cause: cause);
  }
  if (status == 401) {
    // Other 401 slugs (missing_bearer_token, user_not_found) are also auth-y.
    return AuthException(slug: slug ?? 'unauthorized', detail: detail, requestId: requestId, cause: cause);
  }
  return ApiException(
    statusCode: status,
    slug: slug,
    detail: detail,
    requestId: requestId,
    cause: cause,
  );
}
```

- [ ] **Step 5: Run the test — expect pass**

```bash
flutter test test/unit/core/error/error_mapping_test.dart
```

Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/lib/core/error/ app/test/unit/core/error/
git commit -m "$(cat <<'EOF'
feat(app): typed exceptions + DioException mapping

KpaException sealed base; AuthException for 401 invalid_access_token
(refresh interceptor's signal); ApiException for other 4xx/5xx;
NetworkException for transport errors. All carry optional requestId
from X-Request-Id for backend log correlation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `core/log/logger.dart` — minimal structured logger

**Files:**
- Create: `app/lib/core/log/logger.dart`

Lightweight wrapper over `dart:developer`'s `log()`. Production-grade telemetry (Sentry / Crashlytics / Fluent Bit forwarding) is explicitly out of scope per the spec; this file is the seam where that lands later.

- [ ] **Step 1: Implement `app/lib/core/log/logger.dart`**

```dart
import 'dart:developer' as developer;

import 'package:kpa_app/core/config/env.dart';

/// Minimal logger. Replace the implementation with a real telemetry
/// adapter (Sentry / Crashlytics / Fluent Bit forwarder) when that lands.
///
/// Semantics:
/// - In dev builds, every level prints via dart:developer.log (shows in IDE).
/// - In prod builds, info/debug are silent; warn/error still print so they
///   show up in platform-specific crash logs.
class KpaLogger {
  KpaLogger(this._name);

  factory KpaLogger.named(String name) => KpaLogger(name);

  final String _name;

  void debug(String message, {Object? error, StackTrace? stack}) {
    if (!Env.isDev) return;
    developer.log(message, name: _name, level: 500, error: error, stackTrace: stack);
  }

  void info(String message, {Object? error, StackTrace? stack}) {
    if (!Env.isDev) return;
    developer.log(message, name: _name, level: 800, error: error, stackTrace: stack);
  }

  void warn(String message, {Object? error, StackTrace? stack}) {
    developer.log(message, name: _name, level: 900, error: error, stackTrace: stack);
  }

  void error(String message, {Object? error, StackTrace? stack}) {
    developer.log(message, name: _name, level: 1000, error: error, stackTrace: stack);
  }
}
```

- [ ] **Step 2: Smoke-build to verify it compiles**

```bash
flutter analyze lib/core/log/
```

Expected: "No issues found!"

- [ ] **Step 3: Commit**

```bash
git add app/lib/core/log/
git commit -m "$(cat <<'EOF'
feat(app): core/log minimal KpaLogger

dart:developer.log wrapper with dev-vs-prod gating. Placeholder for
the real telemetry adapter (Sentry / Crashlytics / Fluent Bit) that
lands when the deploy target is picked.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3 — Theme tokens + primitive widgets

### Task 7: Theme token files + `build_theme`

**Files:**
- Create: `app/lib/presentation/theme/kpa_colors.dart`
- Create: `app/lib/presentation/theme/kpa_typography.dart`
- Create: `app/lib/presentation/theme/kpa_spacing.dart`
- Create: `app/lib/presentation/theme/kpa_radii.dart`
- Create: `app/lib/presentation/theme/kpa_motion.dart`
- Create: `app/lib/presentation/theme/build_theme.dart`
- Create: `app/test/unit/presentation/theme/build_theme_test.dart`

Five token families, one builder. Values are placeholder-grade per the spec ("token surface defined; art-direction comes later").

- [ ] **Step 1: Create `app/lib/presentation/theme/kpa_colors.dart`**

```dart
import 'package:flutter/material.dart';

/// KPA color tokens. Placeholder values for v0 — replace when a designer
/// enters the loop. Bands map to ColorScheme slots in [buildTheme].
abstract final class KpaColors {
  // Brand
  static const indigo50  = Color(0xFFEEF0FF);
  static const indigo100 = Color(0xFFDDE2FF);
  static const indigo200 = Color(0xFFBAC4FF);
  static const indigo300 = Color(0xFF96A6FF);
  static const indigo400 = Color(0xFF7388FA);
  static const indigo500 = Color(0xFF5067E8);
  static const indigo600 = Color(0xFF3D52C6);
  static const indigo700 = Color(0xFF2E3EA0);
  static const indigo800 = Color(0xFF1F2C7A);
  static const indigo900 = Color(0xFF111A55);

  // Neutrals
  static const neutral0   = Color(0xFFFFFFFF);
  static const neutral50  = Color(0xFFF7F8FA);
  static const neutral100 = Color(0xFFEEEFF3);
  static const neutral200 = Color(0xFFD9DCE3);
  static const neutral300 = Color(0xFFB7BCC8);
  static const neutral400 = Color(0xFF8A91A1);
  static const neutral500 = Color(0xFF626878);
  static const neutral600 = Color(0xFF464B58);
  static const neutral700 = Color(0xFF2E323C);
  static const neutral800 = Color(0xFF1B1E26);
  static const neutral900 = Color(0xFF0E1015);

  // Score bands — product semantics, not chrome.
  /// `total_score < 0.65`
  static const scoreLow  = Color(0xFFCF8A1D);
  /// `0.65 <= total_score < 0.80`
  static const scoreMid  = Color(0xFF3D52C6);
  /// `total_score >= 0.80`
  static const scoreHigh = Color(0xFF1E8A4F);

  // Semantic
  static const error    = Color(0xFFB3261E);
  static const onError  = Color(0xFFFFFFFF);
}
```

- [ ] **Step 2: Create `app/lib/presentation/theme/kpa_typography.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// KPA typography — Inter via google_fonts, six size roles mapped onto
/// Material 3's text theme. The roles match Material 3 naming so widgets
/// can refer to `Theme.of(context).textTheme.headlineMedium` directly.
abstract final class KpaTypography {
  static TextTheme textTheme(Brightness brightness) {
    final base = brightness == Brightness.dark
        ? Typography.whiteMountainView
        : Typography.blackMountainView;
    return GoogleFonts.interTextTheme(base).copyWith(
      displayLarge:   GoogleFonts.inter(fontSize: 36, fontWeight: FontWeight.w700, height: 1.15),
      displayMedium:  GoogleFonts.inter(fontSize: 28, fontWeight: FontWeight.w700, height: 1.20),
      headlineLarge:  GoogleFonts.inter(fontSize: 24, fontWeight: FontWeight.w600, height: 1.25),
      headlineMedium: GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.w600, height: 1.30),
      titleLarge:     GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w600, height: 1.35),
      titleMedium:    GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w600, height: 1.40),
      bodyLarge:      GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w400, height: 1.45),
      bodyMedium:     GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w400, height: 1.45),
      bodySmall:      GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w400, height: 1.40),
      labelLarge:     GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w600, height: 1.20),
      labelMedium:    GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600, height: 1.20),
      labelSmall:     GoogleFonts.inter(fontSize: 11, fontWeight: FontWeight.w600, height: 1.20),
    );
  }
}
```

- [ ] **Step 3: Create `app/lib/presentation/theme/kpa_spacing.dart`**

```dart
/// 4-base spacing scale. Use as `EdgeInsets.symmetric(vertical: KpaSpacing.md)`.
abstract final class KpaSpacing {
  static const double xs   = 4;
  static const double sm   = 8;
  static const double md   = 12;
  static const double lg   = 16;
  static const double xl   = 24;
  static const double xxl  = 32;
  static const double xxxl = 48;
}
```

- [ ] **Step 4: Create `app/lib/presentation/theme/kpa_radii.dart`**

```dart
import 'package:flutter/widgets.dart';

abstract final class KpaRadii {
  static const double sm   = 4;
  static const double md   = 8;
  static const double lg   = 12;
  static const double xl   = 16;
  static const double pill = 999;

  static const radiusSm   = Radius.circular(sm);
  static const radiusMd   = Radius.circular(md);
  static const radiusLg   = Radius.circular(lg);
  static const radiusXl   = Radius.circular(xl);
  static const radiusPill = Radius.circular(pill);

  static const borderRadiusSm = BorderRadius.all(radiusSm);
  static const borderRadiusMd = BorderRadius.all(radiusMd);
  static const borderRadiusLg = BorderRadius.all(radiusLg);
  static const borderRadiusXl = BorderRadius.all(radiusXl);
}
```

- [ ] **Step 5: Create `app/lib/presentation/theme/kpa_motion.dart`**

```dart
import 'package:flutter/material.dart';

/// Motion tokens — v0 just re-exports Material defaults. The indirection
/// means we can adjust globally later without sweeping every call site.
abstract final class KpaMotion {
  static const Duration durationShort  = Durations.short3;     // 150ms
  static const Duration durationMedium = Durations.medium2;    // 250ms
  static const Duration durationLong   = Durations.long2;      // 500ms

  static const Curve curveStandard = Easing.standard;
  static const Curve curveEmphasized = Easing.emphasized;
}
```

- [ ] **Step 6: Create `app/lib/presentation/theme/build_theme.dart`**

```dart
import 'package:flutter/material.dart';

import 'kpa_colors.dart';
import 'kpa_radii.dart';
import 'kpa_typography.dart';

/// Single ThemeData factory for both brightness modes. v0 only ever calls
/// this with [Brightness.light]; the dark branch is plumbed so flipping
/// `themeMode` later is a one-line change.
ThemeData buildTheme(Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final scheme = ColorScheme(
    brightness: brightness,
    primary: KpaColors.indigo500,
    onPrimary: KpaColors.neutral0,
    primaryContainer: isDark ? KpaColors.indigo700 : KpaColors.indigo100,
    onPrimaryContainer: isDark ? KpaColors.indigo100 : KpaColors.indigo900,
    secondary: KpaColors.indigo400,
    onSecondary: KpaColors.neutral0,
    secondaryContainer: isDark ? KpaColors.indigo800 : KpaColors.indigo50,
    onSecondaryContainer: isDark ? KpaColors.indigo50 : KpaColors.indigo800,
    error: KpaColors.error,
    onError: KpaColors.onError,
    surface: isDark ? KpaColors.neutral900 : KpaColors.neutral0,
    onSurface: isDark ? KpaColors.neutral50 : KpaColors.neutral900,
    surfaceContainerHighest: isDark ? KpaColors.neutral800 : KpaColors.neutral50,
    onSurfaceVariant: isDark ? KpaColors.neutral300 : KpaColors.neutral600,
    outline: isDark ? KpaColors.neutral500 : KpaColors.neutral300,
    outlineVariant: isDark ? KpaColors.neutral700 : KpaColors.neutral200,
  );

  final textTheme = KpaTypography.textTheme(brightness);

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    textTheme: textTheme,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      foregroundColor: scheme.onSurface,
      centerTitle: false,
      elevation: 0,
      titleTextStyle: textTheme.titleLarge,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        shape: const RoundedRectangleBorder(borderRadius: KpaRadii.borderRadiusMd),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        shape: const RoundedRectangleBorder(borderRadius: KpaRadii.borderRadiusMd),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    cardTheme: CardTheme(
      shape: const RoundedRectangleBorder(borderRadius: KpaRadii.borderRadiusLg),
      margin: EdgeInsets.zero,
      elevation: 0,
      color: scheme.surfaceContainerHighest,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: const RoundedRectangleBorder(borderRadius: KpaRadii.borderRadiusMd),
      backgroundColor: scheme.onSurface,
      contentTextStyle: textTheme.bodyMedium?.copyWith(color: scheme.surface),
    ),
  );
}
```

- [ ] **Step 7: Write the test**

Create `app/test/unit/presentation/theme/build_theme_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';
import 'package:kpa_app/presentation/theme/kpa_colors.dart';

void main() {
  group('buildTheme', () {
    test('light theme has expected brightness + surface color', () {
      final theme = buildTheme(Brightness.light);
      expect(theme.brightness, Brightness.light);
      expect(theme.colorScheme.surface, KpaColors.neutral0);
      expect(theme.colorScheme.primary, KpaColors.indigo500);
    });

    test('dark theme has expected brightness + inverted surface', () {
      final theme = buildTheme(Brightness.dark);
      expect(theme.brightness, Brightness.dark);
      expect(theme.colorScheme.surface, KpaColors.neutral900);
    });

    test('uses material 3', () {
      expect(buildTheme(Brightness.light).useMaterial3, isTrue);
    });

    test('text theme is non-null and has Inter family', () {
      final theme = buildTheme(Brightness.light);
      // GoogleFonts.inter sets fontFamily to 'Inter' (or 'Inter_regular' depending on weight).
      expect(theme.textTheme.bodyLarge?.fontFamily, contains('Inter'));
    });
  });
}
```

- [ ] **Step 8: Run the tests — expect pass**

```bash
flutter test test/unit/presentation/theme/build_theme_test.dart
```

Expected: 4 tests pass.

- [ ] **Step 9: Commit**

```bash
git add app/lib/presentation/theme/ app/test/unit/presentation/theme/
git commit -m "$(cat <<'EOF'
feat(app): theme tokens + buildTheme

KpaColors (brand + neutrals + score bands), KpaTypography (Inter via
google_fonts mapped to Material 3 text roles), KpaSpacing (4-base),
KpaRadii, KpaMotion. buildTheme(brightness) produces a Material 3
ThemeData; dark branch plumbed but v0 ships light only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Primitive widgets — loading, error, empty, score badge

**Files:**
- Create: `app/lib/presentation/widgets/kpa_loading_view.dart`
- Create: `app/lib/presentation/widgets/kpa_error_view.dart`
- Create: `app/lib/presentation/widgets/kpa_empty_state.dart`
- Create: `app/lib/presentation/widgets/kpa_score_badge.dart`
- Create: `app/test/widget/widgets/primitive_widgets_test.dart`

- [ ] **Step 1: Create `kpa_loading_view.dart`**

```dart
import 'package:flutter/material.dart';

import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class KpaLoadingView extends StatelessWidget {
  const KpaLoadingView({super.key, this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator.adaptive(),
          if (message != null) ...[
            const SizedBox(height: KpaSpacing.lg),
            Text(message!, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ],
      ),
    );
  }
}
```

- [ ] **Step 2: Create `kpa_error_view.dart`**

```dart
import 'package:flutter/material.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

/// Renders an icon + headline + body + retry button.
/// Headline + body derive from the exception type by default; pass
/// [headline] / [body] explicitly to override.
class KpaErrorView extends StatelessWidget {
  const KpaErrorView({
    super.key,
    this.error,
    this.headline,
    this.body,
    this.onRetry,
  });

  final Object? error;
  final String? headline;
  final String? body;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final (h, b) = _describe(error, headline, body);
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: theme.colorScheme.error),
            const SizedBox(height: KpaSpacing.lg),
            Text(h, style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
            const SizedBox(height: KpaSpacing.sm),
            Text(b, style: theme.textTheme.bodyMedium, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: KpaSpacing.lg),
              FilledButton(onPressed: onRetry, child: const Text('Try again')),
            ],
          ],
        ),
      ),
    );
  }

  (String, String) _describe(Object? error, String? headline, String? body) {
    if (headline != null && body != null) return (headline, body);
    switch (error) {
      case NetworkException _:
        return (headline ?? "Couldn't reach KPA", body ?? 'Check your connection and try again.');
      case AuthException _:
        // Refresh interceptor handles 401 transparently; an AuthException
        // here means the refresh itself failed. The router redirects to
        // /signin via authStateProvider; this view is a fallback.
        return (headline ?? 'Signed out', body ?? 'Your session ended. Sign in to continue.');
      case ApiException e:
        return (headline ?? 'Something went wrong', body ?? (e.detail ?? 'Please try again in a moment.'));
      default:
        return (headline ?? 'Something went wrong', body ?? 'An unexpected error occurred.');
    }
  }
}
```

- [ ] **Step 3: Create `kpa_empty_state.dart`**

```dart
import 'package:flutter/material.dart';

import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class KpaEmptyState extends StatelessWidget {
  const KpaEmptyState({
    super.key,
    required this.headline,
    required this.body,
    this.icon = Icons.inbox_outlined,
    this.primaryAction,
  });

  final String headline;
  final String body;
  final IconData icon;
  final Widget? primaryAction;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: KpaSpacing.lg),
            Text(headline, style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
            const SizedBox(height: KpaSpacing.sm),
            Text(
              body,
              style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
            if (primaryAction != null) ...[
              const SizedBox(height: KpaSpacing.lg),
              primaryAction!,
            ],
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Create `kpa_score_badge.dart`**

```dart
import 'package:flutter/material.dart';

import 'package:kpa_app/presentation/theme/kpa_colors.dart';
import 'package:kpa_app/presentation/theme/kpa_radii.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

/// Small chip showing total_score as a percent, color-graded by band.
/// Score is a 0..1 double from the backend.
class KpaScoreBadge extends StatelessWidget {
  const KpaScoreBadge({super.key, required this.score});

  final double score;

  Color get _bandColor {
    if (score >= 0.80) return KpaColors.scoreHigh;
    if (score >= 0.65) return KpaColors.scoreMid;
    return KpaColors.scoreLow;
  }

  @override
  Widget build(BuildContext context) {
    final percent = (score * 100).round().clamp(0, 100);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.sm, vertical: KpaSpacing.xs),
      decoration: BoxDecoration(
        color: _bandColor,
        borderRadius: KpaRadii.borderRadiusPill,
      ),
      child: Text(
        '$percent%',
        style: Theme.of(context).textTheme.labelMedium?.copyWith(color: KpaColors.neutral0),
      ),
    );
  }
}
```

(Where `borderRadiusPill` lives — add it to `kpa_radii.dart` if not already there:)

```dart
static const borderRadiusPill = BorderRadius.all(radiusPill);
```

- [ ] **Step 5: Write widget tests**

Create `app/test/widget/widgets/primitive_widgets_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_error_view.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';
import 'package:kpa_app/presentation/widgets/kpa_score_badge.dart';

Widget _wrap(Widget child) {
  return MaterialApp(
    theme: buildTheme(Brightness.light),
    home: Scaffold(body: child),
  );
}

void main() {
  testWidgets('KpaLoadingView renders an adaptive spinner', (tester) async {
    await tester.pumpWidget(_wrap(const KpaLoadingView(message: 'Loading…')));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Loading…'), findsOneWidget);
  });

  testWidgets('KpaErrorView with NetworkException shows network copy', (tester) async {
    await tester.pumpWidget(_wrap(KpaErrorView(error: const NetworkException(message: 'oops'))));
    expect(find.textContaining("Couldn't reach KPA"), findsOneWidget);
  });

  testWidgets('KpaErrorView with onRetry shows the button', (tester) async {
    var taps = 0;
    await tester.pumpWidget(_wrap(KpaErrorView(
      error: const NetworkException(),
      onRetry: () => taps++,
    )));
    await tester.tap(find.text('Try again'));
    expect(taps, 1);
  });

  testWidgets('KpaEmptyState renders headline + body + action', (tester) async {
    await tester.pumpWidget(_wrap(KpaEmptyState(
      headline: 'Nothing here',
      body: 'Try something else',
      primaryAction: FilledButton(onPressed: () {}, child: const Text('Go')),
    )));
    expect(find.text('Nothing here'), findsOneWidget);
    expect(find.text('Try something else'), findsOneWidget);
    expect(find.text('Go'), findsOneWidget);
  });

  testWidgets('KpaScoreBadge renders rounded percent', (tester) async {
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.857)));
    expect(find.text('86%'), findsOneWidget);
  });

  testWidgets('KpaScoreBadge bands by score', (tester) async {
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.5)));   // low
    expect(find.text('50%'), findsOneWidget);
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.7)));   // mid
    expect(find.text('70%'), findsOneWidget);
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.95)));  // high
    expect(find.text('95%'), findsOneWidget);
  });
}
```

- [ ] **Step 6: Run the tests**

```bash
flutter test test/widget/widgets/primitive_widgets_test.dart
```

Expected: 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/lib/presentation/widgets/ app/test/widget/widgets/ app/lib/presentation/theme/kpa_radii.dart
git commit -m "$(cat <<'EOF'
feat(app): primitive widgets — loading, error, empty, score badge

KpaLoadingView, KpaErrorView (typed-exception-aware copy), KpaEmptyState,
KpaScoreBadge (color-graded by score band). KpaRadii gains borderRadiusPill.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: `AsyncValueWidget` — the AsyncValue three-way switch helper

**Files:**
- Create: `app/lib/presentation/widgets/async_value_widget.dart`
- Create: `app/test/widget/widgets/async_value_widget_test.dart`

Single helper used by every screen at its root. Collapses ~15 lines of `value.when(...)` into 3.

- [ ] **Step 1: Implement `async_value_widget.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'kpa_empty_state.dart';
import 'kpa_error_view.dart';
import 'kpa_loading_view.dart';

class AsyncValueWidget<T> extends StatelessWidget {
  const AsyncValueWidget({
    super.key,
    required this.value,
    required this.data,
    this.loading,
    this.error,
    this.isEmpty,
    this.empty,
    this.onRetry,
  });

  final AsyncValue<T> value;
  final Widget Function(T data) data;

  /// Defaults to [KpaLoadingView].
  final Widget Function()? loading;

  /// Defaults to [KpaErrorView] wired to [onRetry].
  final Widget Function(Object e, StackTrace s)? error;

  /// Optional predicate. When true, render [empty] (or [KpaEmptyState]) instead of [data].
  final bool Function(T data)? isEmpty;
  final Widget Function()? empty;

  /// Wired into the default [KpaErrorView]'s retry button (and the default
  /// empty state's primary action, when an [empty] builder isn't supplied).
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return value.when(
      loading: () => (loading ?? () => const KpaLoadingView())(),
      error: (e, s) => (error ?? (e, s) => KpaErrorView(error: e, onRetry: onRetry))(e, s),
      data: (d) {
        if (isEmpty?.call(d) ?? false) {
          return (empty ?? () => const KpaEmptyState(
            headline: 'Nothing here yet',
            body: '',
          ))();
        }
        return data(d);
      },
    );
  }
}
```

- [ ] **Step 2: Write the test**

Create `app/test/widget/widgets/async_value_widget_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';

Widget _wrap(Widget child) {
  return MaterialApp(
    theme: buildTheme(Brightness.light),
    home: Scaffold(body: child),
  );
}

void main() {
  testWidgets('renders loading by default', (tester) async {
    await tester.pumpWidget(_wrap(AsyncValueWidget<int>(
      value: const AsyncValue.loading(),
      data: (d) => Text('$d'),
    )));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('renders data when AsyncValue.data', (tester) async {
    await tester.pumpWidget(_wrap(AsyncValueWidget<int>(
      value: const AsyncValue.data(42),
      data: (d) => Text('$d'),
    )));
    expect(find.text('42'), findsOneWidget);
  });

  testWidgets('renders KpaErrorView with typed exception copy on error', (tester) async {
    await tester.pumpWidget(_wrap(AsyncValueWidget<int>(
      value: AsyncValue.error(const NetworkException(), StackTrace.current),
      data: (d) => Text('$d'),
    )));
    expect(find.textContaining("Couldn't reach KPA"), findsOneWidget);
  });

  testWidgets('renders empty when isEmpty predicate matches', (tester) async {
    await tester.pumpWidget(_wrap(AsyncValueWidget<List<int>>(
      value: const AsyncValue.data(<int>[]),
      isEmpty: (d) => d.isEmpty,
      empty: () => const Text('NOTHING'),
      data: (d) => Text('${d.length}'),
    )));
    expect(find.text('NOTHING'), findsOneWidget);
  });

  testWidgets('renders data when isEmpty predicate is false', (tester) async {
    await tester.pumpWidget(_wrap(AsyncValueWidget<List<int>>(
      value: const AsyncValue.data(<int>[1, 2]),
      isEmpty: (d) => d.isEmpty,
      empty: () => const Text('NOTHING'),
      data: (d) => Text('${d.length}'),
    )));
    expect(find.text('2'), findsOneWidget);
  });
}
```

- [ ] **Step 3: Run the tests**

```bash
flutter test test/widget/widgets/async_value_widget_test.dart
```

Expected: 5 tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/widgets/async_value_widget.dart app/test/widget/widgets/async_value_widget_test.dart
git commit -m "$(cat <<'EOF'
feat(app): AsyncValueWidget primitive

Three-way AsyncValue switch collapsed into one widget. Defaults to
KpaLoadingView / KpaErrorView (typed-exception-aware) / KpaEmptyState
with overridable builders. Used at every screen's root.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 4 — Domain interfaces

### Task 10: Repository interfaces + value types + `AuthState` sealed

**Files:**
- Create: `app/lib/domain/auth/auth_repository.dart`
- Create: `app/lib/domain/auth/auth_state.dart`
- Create: `app/lib/domain/feed/feed_repository.dart`
- Create: `app/lib/domain/feed/feed_page.dart`
- Create: `app/lib/domain/jobs/jobs_repository.dart`
- Create: `app/lib/domain/jobs/job_detail.dart`
- Create: `app/lib/domain/jobs/applications_repository.dart`
- Create: `app/lib/domain/jobs/applications_page.dart`
- Create: `app/lib/domain/jobs/saved_jobs_repository.dart`
- Create: `app/lib/domain/jobs/saved_jobs_page.dart`
- Create: `app/lib/domain/me/me_repository.dart`

Pure Dart — no `package:flutter`, `package:dio`, or `package:riverpod` imports anywhere under `lib/domain/`. Value types are simple `@freezed` classes; **DTOs from `data/` will satisfy the value-type slots** per the Pragmatic CA cheat (spec §Architecture). The interfaces here only reference concrete types declared in `data/` once those DTOs exist; until then, we forward-declare the types we need via aliasing in `lib/domain/_dto_exports.dart` (intentionally created later, in Task 11).

For now, each `*_page.dart` re-exports `*Dto` types via a `typedef` once they exist. Domain stays interface-only.

- [ ] **Step 1: Create `app/lib/domain/auth/auth_state.dart`**

```dart
/// The three states the app's auth lifecycle can be in.
/// Watched by the router for redirect decisions and by every screen
/// that needs the current user.
sealed class AuthState {
  const AuthState();
}

class SignedOut extends AuthState {
  const SignedOut();
}

class Authenticating extends AuthState {
  const Authenticating();
}

class SignedIn extends AuthState {
  const SignedIn({required this.userId, required this.email, this.displayName});

  final String userId;
  final String email;
  final String? displayName;
}
```

- [ ] **Step 2: Create `app/lib/domain/auth/auth_repository.dart`**

```dart
import 'auth_state.dart';

abstract interface class AuthRepository {
  /// Reactive auth state — splash bootstrap, sign-in success, sign-out,
  /// and refresh-failure all push to this stream. Router listens.
  Stream<AuthState> watch();

  /// Most recent state, synchronous read.
  AuthState get current;

  /// Run the platform-correct Google flow, exchange the resulting ID token
  /// with the backend, persist the refresh token, and surface a SignedIn.
  /// Throws AuthException / NetworkException / ApiException on failure.
  Future<SignedIn> signInWithGoogle();

  /// Splash-bootstrap path: read the stored refresh token and exchange it
  /// for a fresh pair. Throws on 4xx (no refresh token, expired, revoked)
  /// or transport error. On success, [current] becomes [SignedIn] before
  /// this future completes.
  Future<SignedIn> refreshSession();

  /// POST /v1/auth/logout (idempotent), then clear local secrets and emit SignedOut.
  /// Never throws to the caller — logging out is non-cancellable from a UX
  /// perspective; errors are logged and swallowed.
  Future<void> signOut();
}
```

- [ ] **Step 3: Create the feed/jobs/applications/saved/me domain files**

`app/lib/domain/feed/feed_page.dart`:

```dart
// Pragmatic CA: the value type is the data-layer DTO. The typedef gives
// domain consumers a domain-named handle without duplicating the model.
//
// This file is intentionally a single export line; the real definition
// lives in lib/data/feed/feed_dto.dart (created in Task 17).
export 'package:kpa_app/data/feed/feed_dto.dart' show FeedPageDto, FeedItemDto;

// Domain-named handle — consumers import this rather than the Dto name.
typedef FeedPage = FeedPageDto;     // ignore: avoid_classes_with_only_static_members
typedef FeedItem = FeedItemDto;
```

Wait — that doesn't work. `typedef` and `export` in the same file are fine, but the typedef-after-export is redundant if consumers already import the export. Let me revise to be cleaner:

```dart
// app/lib/domain/feed/feed_page.dart
//
// Pragmatic CA cheat: the value type IS the data-layer DTO. Domain
// consumers import these names from here; the actual definition lives
// in lib/data/feed/feed_dto.dart (created in Task 17).
export 'package:kpa_app/data/feed/feed_dto.dart' show FeedPageDto, FeedItemDto;
```

Consumers write `import 'package:kpa_app/domain/feed/feed_page.dart';` then use `FeedPageDto` directly. The intent is clear because the import path says `domain/`.

Apply the same pattern to the other domain `*_page.dart` files:

`app/lib/domain/jobs/job_detail.dart`:

```dart
// Pragmatic CA: value type IS the data-layer DTO.
// Real definition lives in lib/data/jobs/jobs_dto.dart.
export 'package:kpa_app/data/jobs/jobs_dto.dart' show JobDetailDto, ApplicationDto, SavedJobDto;
```

`app/lib/domain/jobs/applications_page.dart`:

```dart
export 'package:kpa_app/data/jobs/jobs_dto.dart' show ApplicationsPageDto, ApplicationDto;
```

`app/lib/domain/jobs/saved_jobs_page.dart`:

```dart
export 'package:kpa_app/data/jobs/jobs_dto.dart' show SavedJobsPageDto, SavedJobDto;
```

(Single re-export from `jobs_dto.dart` because applications + saved jobs + job detail all share DTO definitions — they reference the same `JobSummaryDto` etc.)

- [ ] **Step 4: Create the repository interfaces**

`app/lib/domain/feed/feed_repository.dart`:

```dart
import 'feed_page.dart';

abstract interface class FeedRepository {
  /// GET /v1/feed?limit=&cursor=. Throws AuthException / ApiException /
  /// NetworkException on failure.
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20});
}
```

`app/lib/domain/jobs/jobs_repository.dart`:

```dart
import 'job_detail.dart';

abstract interface class JobsRepository {
  Future<JobDetailDto> fetchById(String jobId);

  Future<ApplicationDto> applyTo(String jobId, {String source = 'feed'});

  Future<SavedJobDto> save(String jobId);

  Future<void> unsave(String jobId);
}
```

`app/lib/domain/jobs/applications_repository.dart`:

```dart
import 'applications_page.dart';

abstract interface class ApplicationsRepository {
  Future<ApplicationsPageDto> fetchPage({String? cursor, int limit = 20});

  Future<ApplicationDto> withdraw(String applicationId);
}
```

`app/lib/domain/jobs/saved_jobs_repository.dart`:

```dart
import 'saved_jobs_page.dart';

abstract interface class SavedJobsRepository {
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20});
}
```

`app/lib/domain/me/me_repository.dart`:

```dart
export 'package:kpa_app/data/me/me_dto.dart' show MeDto, ApplicantSummaryDto;

import 'package:kpa_app/data/me/me_dto.dart';

abstract interface class MeRepository {
  Future<MeDto> fetch();
}
```

- [ ] **Step 5: Don't compile yet — DTOs don't exist**

`flutter analyze lib/domain/` will fail until Tasks 15-19 create the DTOs. **Do not run analyze right now.** This is normal; the interfaces are correct, the imports will resolve as the DTO files land.

- [ ] **Step 6: Commit**

```bash
git add app/lib/domain/
git commit -m "$(cat <<'EOF'
feat(app): domain interfaces + AuthState sealed

Six repository interfaces (AuthRepository, FeedRepository, JobsRepository,
ApplicationsRepository, SavedJobsRepository, MeRepository) under lib/domain/.
Pure Dart — no Flutter, dio, or Riverpod imports.

Value-type slots re-export the data-layer DTOs (Pragmatic CA cheat per
spec §Architecture). lib/data/*_dto.dart files arrive in Tasks 15-19;
flutter analyze will fail on lib/domain/ until then by design.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5 — Data foundation

### Task 11: dio provider + `RequestIdInterceptor` + `AuthHeaderInterceptor`

**Files:**
- Create: `app/lib/data/api/dio_provider.dart`
- Create: `app/lib/data/api/request_id_interceptor.dart`
- Create: `app/lib/data/api/auth_header_interceptor.dart`
- Create: `app/lib/data/api/access_token_holder.dart`
- Create: `app/test/unit/data/api/request_id_interceptor_test.dart`
- Create: `app/test/unit/data/api/auth_header_interceptor_test.dart`

`AccessTokenHolder` is a tiny mutable shared store for the in-memory access token. Interceptors read it; the auth repository writes to it. We don't put the access token directly on the Riverpod provider tree yet because dio interceptors live below Riverpod's reach — the holder is the bridge. The Riverpod-side `accessTokenProvider` (Task 14) wraps it.

- [ ] **Step 1: Create `access_token_holder.dart`**

```dart
/// In-memory mutable holder for the current access token.
///
/// Lives below Riverpod's reach because dio interceptors are constructed
/// once and shouldn't take a Ref. The auth repository writes to this when
/// it mints/refreshes a token; the Riverpod accessTokenProvider mirrors
/// it for UI consumers.
class AccessTokenHolder {
  String? _token;

  String? get current => _token;

  void set(String? token) {
    _token = token;
  }

  void clear() => set(null);
}
```

- [ ] **Step 2: Create `request_id_interceptor.dart`**

```dart
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

const _kRequestIdExtraKey = 'kpa.requestId';
const _kRequestIdHeader   = 'X-Request-Id';

/// Generates a uuid4 per outgoing request, sets it as X-Request-Id, and
/// stashes it in options.extra so error mapping can attach it to thrown
/// exceptions even when the response has no body.
class RequestIdInterceptor extends Interceptor {
  RequestIdInterceptor({Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  final Uuid _uuid;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final id = _uuid.v4();
    options.headers[_kRequestIdHeader] = id;
    options.extra[_kRequestIdExtraKey] = id;
    handler.next(options);
  }
}

String? requestIdFromOptions(RequestOptions options) =>
    options.extra[_kRequestIdExtraKey] as String?;
```

- [ ] **Step 3: Create `auth_header_interceptor.dart`**

```dart
import 'package:dio/dio.dart';

import 'access_token_holder.dart';

/// Extras flag — set `options.extra[kSkipAuth] = true` on requests that
/// must not carry an Authorization header (the sign-in and refresh
/// endpoints). The auth repo sets this when issuing those calls.
const String kSkipAuth = 'kpa.skipAuth';

class AuthHeaderInterceptor extends Interceptor {
  AuthHeaderInterceptor(this._holder);

  final AccessTokenHolder _holder;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final skip = options.extra[kSkipAuth] == true;
    if (!skip) {
      final token = _holder.current;
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }
}
```

- [ ] **Step 4: Create `dio_provider.dart`**

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/config/env.dart';
import 'access_token_holder.dart';
import 'auth_header_interceptor.dart';
import 'request_id_interceptor.dart';

part 'dio_provider.g.dart';

/// Holder is a singleton because every dio call must see the same access
/// token, and the auth repo + the refresh interceptor both write to it.
@Riverpod(keepAlive: true)
AccessTokenHolder accessTokenHolder(Ref ref) => AccessTokenHolder();

@Riverpod(keepAlive: true)
Dio dio(Ref ref) {
  final holder = ref.read(accessTokenHolderProvider);
  final dio = Dio(BaseOptions(
    baseUrl: Env.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    contentType: 'application/json',
    responseType: ResponseType.json,
    // Don't throw on 4xx — interceptors and repos handle status mapping.
    validateStatus: (s) => s != null && s < 500,
  ));
  dio.interceptors.add(RequestIdInterceptor());
  dio.interceptors.add(AuthHeaderInterceptor(holder));
  // RefreshOn401Interceptor is added in Task 13 (after AuthRepository exists).
  return dio;
}
```

- [ ] **Step 5: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Expected: generates `app/lib/data/api/dio_provider.g.dart`. Other generated files for not-yet-written providers will surface as the plan progresses.

- [ ] **Step 6: Write tests for the interceptors**

Create `app/test/unit/data/api/request_id_interceptor_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/data/api/request_id_interceptor.dart';

void main() {
  test('sets X-Request-Id header on every request', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    dio.interceptors.add(RequestIdInterceptor());
    final adapter = DioAdapter(dio: dio);

    String? seenId;
    adapter.onGet('/foo', (server) {
      seenId = server.request.headers.value('X-Request-Id');
      server.reply(200, {'ok': true});
    });
    await dio.get<dynamic>('/foo');
    expect(seenId, isNotNull);
    expect(seenId, hasLength(36)); // uuid4
  });

  test('different requests get different ids', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    dio.interceptors.add(RequestIdInterceptor());
    final adapter = DioAdapter(dio: dio);

    final seen = <String?>[];
    adapter
      ..onGet('/a', (s) { seen.add(s.request.headers.value('X-Request-Id')); s.reply(200, {}); })
      ..onGet('/b', (s) { seen.add(s.request.headers.value('X-Request-Id')); s.reply(200, {}); });
    await dio.get<dynamic>('/a');
    await dio.get<dynamic>('/b');
    expect(seen[0], isNot(seen[1]));
  });
}
```

Create `app/test/unit/data/api/auth_header_interceptor_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';

void main() {
  late Dio dio;
  late DioAdapter adapter;
  late AccessTokenHolder holder;

  setUp(() {
    holder = AccessTokenHolder();
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    dio.interceptors.add(AuthHeaderInterceptor(holder));
    adapter = DioAdapter(dio: dio);
  });

  test('attaches Bearer token when present', () async {
    holder.set('tok-123');
    String? authHeader;
    adapter.onGet('/foo', (s) { authHeader = s.request.headers.value('Authorization'); s.reply(200, {}); });
    await dio.get<dynamic>('/foo');
    expect(authHeader, 'Bearer tok-123');
  });

  test('omits Authorization when no token', () async {
    String? authHeader;
    adapter.onGet('/foo', (s) { authHeader = s.request.headers.value('Authorization'); s.reply(200, {}); });
    await dio.get<dynamic>('/foo');
    expect(authHeader, isNull);
  });

  test('omits Authorization when kSkipAuth=true even with token', () async {
    holder.set('tok-xyz');
    String? authHeader;
    adapter.onGet('/foo', (s) { authHeader = s.request.headers.value('Authorization'); s.reply(200, {}); });
    await dio.get<dynamic>('/foo', options: Options(extra: {kSkipAuth: true}));
    expect(authHeader, isNull);
  });
}
```

- [ ] **Step 7: Run the tests**

```bash
flutter test test/unit/data/api/
```

Expected: 5 tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/lib/data/api/ app/test/unit/data/api/
git commit -m "$(cat <<'EOF'
feat(app): dio provider + request-id + auth-header interceptors

AccessTokenHolder bridges Riverpod and dio for the in-memory access
token. RequestIdInterceptor stamps a uuid4 X-Request-Id and stashes
it in options.extra for error mapping. AuthHeaderInterceptor reads
the holder and honors the kSkipAuth extras flag for /auth endpoints.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: `TokenStorage` — flutter_secure_storage wrapper

**Files:**
- Create: `app/lib/data/auth/token_storage.dart`
- Create: `app/test/unit/data/auth/token_storage_test.dart`

Wraps `flutter_secure_storage` so we have one place to swap implementations (or stub for tests). Only the refresh token is persisted — access token lives in `AccessTokenHolder`.

- [ ] **Step 1: Create `token_storage.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'token_storage.g.dart';

abstract interface class TokenStorage {
  Future<String?> readRefreshToken();
  Future<void> writeRefreshToken(String token);
  Future<void> clear();
}

class SecureTokenStorage implements TokenStorage {
  SecureTokenStorage([FlutterSecureStorage? storage])
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
              iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
              webOptions: WebOptions(dbName: 'kpa_app_secure'),
            );

  final FlutterSecureStorage _storage;

  static const _kRefreshKey = 'kpa.refresh_token';

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _kRefreshKey);

  @override
  Future<void> writeRefreshToken(String token) =>
      _storage.write(key: _kRefreshKey, value: token);

  @override
  Future<void> clear() => _storage.delete(key: _kRefreshKey);
}

@Riverpod(keepAlive: true)
TokenStorage tokenStorage(Ref ref) => SecureTokenStorage();
```

- [ ] **Step 2: Write the test (uses a hand-rolled in-memory implementation)**

Create `app/test/unit/data/auth/token_storage_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/token_storage.dart';

/// Hand-rolled in-memory implementation. We don't test SecureTokenStorage
/// directly because flutter_secure_storage uses platform channels that
/// don't run in unit tests. The integration test (Task 34) exercises the
/// real plugin in a tester context.
class InMemoryTokenStorage implements TokenStorage {
  String? _t;
  @override Future<String?> readRefreshToken() async => _t;
  @override Future<void> writeRefreshToken(String token) async => _t = token;
  @override Future<void> clear() async => _t = null;
}

void main() {
  group('TokenStorage contract', () {
    late TokenStorage storage;
    setUp(() => storage = InMemoryTokenStorage());

    test('write then read returns the token', () async {
      await storage.writeRefreshToken('rt-1');
      expect(await storage.readRefreshToken(), 'rt-1');
    });

    test('clear removes the token', () async {
      await storage.writeRefreshToken('rt-1');
      await storage.clear();
      expect(await storage.readRefreshToken(), isNull);
    });

    test('read on empty storage returns null', () async {
      expect(await storage.readRefreshToken(), isNull);
    });

    test('write overwrites previous value', () async {
      await storage.writeRefreshToken('rt-1');
      await storage.writeRefreshToken('rt-2');
      expect(await storage.readRefreshToken(), 'rt-2');
    });
  });
}
```

- [ ] **Step 3: Run codegen + tests**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
flutter test test/unit/data/auth/token_storage_test.dart
```

Expected: codegen produces `token_storage.g.dart`; 4 tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/lib/data/auth/token_storage.dart app/lib/data/auth/token_storage.g.dart app/test/unit/data/auth/token_storage_test.dart
git commit -m "$(cat <<'EOF'
feat(app): TokenStorage interface + SecureTokenStorage impl

Wraps flutter_secure_storage with platform options for keychain/keystore/
web crypto. Only the refresh token is persisted at rest; access token
lives in AccessTokenHolder. tokenStorageProvider keepAlive in Riverpod.

Contract tested via an in-memory impl; the real plugin uses platform
channels not available in unit tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: `RefreshOn401Interceptor` — single-flight refresh + replay (THE BIG TASK)

**Files:**
- Create: `app/lib/data/api/refresh_on_401_interceptor.dart`
- Create: `app/test/unit/data/api/refresh_on_401_interceptor_test.dart`

This is the most important code in the foundation. Five scenarios are tested explicitly:

1. 401 → single refresh succeeds → original request replays → 200.
2. 401 → refresh fails with 4xx → original throws AuthException, holder cleared, signed-out callback invoked.
3. Two concurrent 401s → exactly one refresh call (single-flight) → both replays succeed.
4. 401 on a `kSkipAuth=true` request → no refresh attempted.
5. Network error during refresh → NetworkException propagated; holder unchanged.

The interceptor takes a `Future<String> Function()` for the refresh call (rather than depending on `AuthRepository` directly) to break the circular import (`AuthRepositoryImpl` depends on `dio` which carries this interceptor). The auth repo wires the callback at construction time.

- [ ] **Step 1: Implement `refresh_on_401_interceptor.dart`**

```dart
import 'dart:async';

import 'package:dio/dio.dart';

import 'access_token_holder.dart';
import 'auth_header_interceptor.dart';

/// Slug the backend returns on access-token failure. Other 401 slugs
/// (missing_bearer_token, user_not_found) are NOT refresh-eligible —
/// they indicate the request was malformed or the user is gone.
const String _kAccessTokenInvalidSlug = 'invalid_access_token';

typedef RefreshCallback = Future<String> Function();
typedef OnSignedOut    = void Function();

/// Intercepts 401 responses, performs a single-flight call to [refresh],
/// updates [_holder] with the new access token, and replays the original
/// request once. If [refresh] itself fails, calls [onSignedOut] and lets
/// the original 401 propagate as an [AuthException] (via error_mapping
/// downstream).
class RefreshOn401Interceptor extends Interceptor {
  RefreshOn401Interceptor({
    required AccessTokenHolder holder,
    required RefreshCallback refresh,
    required Dio dio,
    OnSignedOut? onSignedOut,
  })  : _holder = holder,
        _refresh = refresh,
        _dio = dio,
        _onSignedOut = onSignedOut;

  final AccessTokenHolder _holder;
  final RefreshCallback _refresh;
  final Dio _dio;
  final OnSignedOut? _onSignedOut;

  Completer<String>? _inFlight;

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    final response = err.response;
    if (response == null || response.statusCode != 401) {
      return handler.next(err);
    }

    final body = response.data;
    final slug = body is Map ? body['slug'] : null;
    if (slug != _kAccessTokenInvalidSlug) {
      return handler.next(err);
    }

    if (err.requestOptions.extra[kSkipAuth] == true) {
      // The auth endpoints themselves shouldn't retry.
      return handler.next(err);
    }

    // Guard against a replay request also 401ing — if we already attached
    // a fresh token and still got 401, give up.
    if (err.requestOptions.extra[_kReplayedFlag] == true) {
      _holder.clear();
      _onSignedOut?.call();
      return handler.next(err);
    }

    try {
      final newAccess = await _runRefreshSingleFlight();
      _holder.set(newAccess);

      // Replay the original request once.
      final cloned = err.requestOptions.copyWith(
        headers: {
          ...err.requestOptions.headers,
          'Authorization': 'Bearer $newAccess',
        },
        extra: {
          ...err.requestOptions.extra,
          _kReplayedFlag: true,
        },
      );
      final replay = await _dio.fetch<dynamic>(cloned);
      return handler.resolve(replay);
    } on _RefreshFailed {
      _holder.clear();
      _onSignedOut?.call();
      return handler.next(err);
    } catch (replayErr, st) {
      // Replay threw — pass that through as the new error.
      if (replayErr is DioException) {
        return handler.next(replayErr);
      }
      return handler.next(DioException(
        requestOptions: err.requestOptions,
        error: replayErr,
        stackTrace: st,
        type: DioExceptionType.unknown,
      ));
    }
  }

  Future<String> _runRefreshSingleFlight() {
    final existing = _inFlight;
    if (existing != null) return existing.future;
    final c = Completer<String>();
    _inFlight = c;
    _refresh().then(
      (token) {
        c.complete(token);
        _inFlight = null;
      },
      onError: (Object e, StackTrace s) {
        c.completeError(_RefreshFailed(e), s);
        _inFlight = null;
      },
    );
    return c.future;
  }
}

/// Internal sentinel so the public catch site can distinguish "refresh
/// itself failed" from "replay threw".
class _RefreshFailed implements Exception {
  _RefreshFailed(this.cause);
  final Object cause;
}

const String _kReplayedFlag = 'kpa.refreshReplayed';

extension on RequestOptions {
  RequestOptions copyWith({
    Map<String, dynamic>? headers,
    Map<String, dynamic>? extra,
  }) {
    return RequestOptions(
      path: path,
      method: method,
      data: data,
      queryParameters: queryParameters,
      baseUrl: baseUrl,
      headers: headers ?? this.headers,
      extra: extra ?? this.extra,
      responseType: responseType,
      contentType: contentType,
      validateStatus: validateStatus,
      receiveDataWhenStatusError: receiveDataWhenStatusError,
      followRedirects: followRedirects,
      maxRedirects: maxRedirects,
      requestEncoder: requestEncoder,
      responseDecoder: responseDecoder,
      listFormat: listFormat,
      sendTimeout: sendTimeout,
      receiveTimeout: receiveTimeout,
      connectTimeout: connectTimeout,
      preserveHeaderCase: preserveHeaderCase,
    );
  }
}
```

- [ ] **Step 2: Write the test**

Create `app/test/unit/data/api/refresh_on_401_interceptor_test.dart`:

```dart
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';
import 'package:kpa_app/data/api/refresh_on_401_interceptor.dart';

/// Helper: builds a Dio with both interceptors wired around a programmable refresh callback.
({Dio dio, DioAdapter adapter, AccessTokenHolder holder, _RefreshCounter counter})
_buildHarness({
  required Future<String> Function(int callNumber) onRefresh,
  void Function()? onSignedOut,
}) {
  final holder = AccessTokenHolder();
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
  dio.interceptors.add(AuthHeaderInterceptor(holder));
  final counter = _RefreshCounter();
  dio.interceptors.add(RefreshOn401Interceptor(
    holder: holder,
    dio: dio,
    onSignedOut: onSignedOut,
    refresh: () async {
      final n = ++counter.calls;
      return onRefresh(n);
    },
  ));
  final adapter = DioAdapter(dio: dio);
  return (dio: dio, adapter: adapter, holder: holder, counter: counter);
}

class _RefreshCounter { int calls = 0; }

Map<String, dynamic> _invalidAccess() => {
  'type': 'about:blank', 'title': 'Unauthorized', 'status': 401,
  'slug': 'invalid_access_token', 'detail': 'expired',
};

void main() {
  group('RefreshOn401Interceptor', () {
    test('401 → refresh → replay → 200', () async {
      final h = _buildHarness(onRefresh: (_) async => 'NEW_TOKEN');
      h.holder.set('OLD_TOKEN');

      var hits = 0;
      h.adapter.onGet('/v1/feed', (server) {
        hits++;
        if (hits == 1) {
          server.reply(401, _invalidAccess());
        } else {
          // Replay carries the new token
          expect(server.request.headers.value('Authorization'), 'Bearer NEW_TOKEN');
          server.reply(200, {'items': []});
        }
      });

      final res = await h.dio.get<dynamic>('/v1/feed');
      expect(res.statusCode, 200);
      expect(h.holder.current, 'NEW_TOKEN');
      expect(h.counter.calls, 1);
      expect(hits, 2);
    });

    test('401 → refresh fails → original 401 propagates + holder cleared + onSignedOut', () async {
      var signedOut = false;
      final h = _buildHarness(
        onRefresh: (_) async => throw StateError('refresh-failed'),
        onSignedOut: () => signedOut = true,
      );
      h.holder.set('OLD_TOKEN');

      h.adapter.onGet('/v1/feed', (server) => server.reply(401, _invalidAccess()));

      await expectLater(
        h.dio.get<dynamic>('/v1/feed'),
        throwsA(isA<DioException>()),
      );
      expect(h.holder.current, isNull);
      expect(signedOut, isTrue);
    });

    test('two concurrent 401s → exactly one refresh call', () async {
      final completer = Completer<String>();
      final h = _buildHarness(onRefresh: (_) => completer.future);
      h.holder.set('OLD_TOKEN');

      var hits = 0;
      h.adapter.onGet('/v1/feed', (server) {
        hits++;
        if (hits <= 2) {
          server.reply(401, _invalidAccess());
        } else {
          server.reply(200, {'items': []});
        }
      });

      final f1 = h.dio.get<dynamic>('/v1/feed');
      final f2 = h.dio.get<dynamic>('/v1/feed');

      // Let both reach the in-flight refresh.
      await Future<void>.delayed(const Duration(milliseconds: 10));
      completer.complete('NEW_TOKEN');

      final results = await Future.wait([f1, f2]);
      for (final r in results) {
        expect(r.statusCode, 200);
      }
      expect(h.counter.calls, 1, reason: 'refresh single-flight failed');
    });

    test('401 on kSkipAuth request → no refresh attempted', () async {
      final h = _buildHarness(onRefresh: (_) async => fail('should not run'));

      h.adapter.onPost('/v1/auth/refresh', (s) => s.reply(401, _invalidAccess()));

      await expectLater(
        h.dio.post<dynamic>(
          '/v1/auth/refresh',
          options: Options(extra: {kSkipAuth: true}),
        ),
        throwsA(isA<DioException>()),
      );
      expect(h.counter.calls, 0);
    });

    test('401 with non-invalid_access_token slug → no refresh, passes through', () async {
      final h = _buildHarness(onRefresh: (_) async => fail('should not run'));
      h.holder.set('TOK');

      h.adapter.onGet('/v1/x', (s) => s.reply(401, {
        'status': 401, 'slug': 'missing_bearer_token', 'detail': 'no bearer',
      }));

      await expectLater(h.dio.get<dynamic>('/v1/x'), throwsA(isA<DioException>()));
      expect(h.counter.calls, 0);
      expect(h.holder.current, 'TOK', reason: 'holder unchanged');
    });

    test('replay still 401 → give up, clear holder, signed out', () async {
      var signedOut = false;
      final h = _buildHarness(
        onRefresh: (_) async => 'STILL_BAD',
        onSignedOut: () => signedOut = true,
      );
      h.holder.set('OLD');

      h.adapter.onGet('/v1/feed', (s) => s.reply(401, _invalidAccess()));

      await expectLater(h.dio.get<dynamic>('/v1/feed'), throwsA(isA<DioException>()));
      expect(h.holder.current, isNull);
      expect(signedOut, isTrue);
      expect(h.counter.calls, 1);
    });
  });
}
```

- [ ] **Step 3: Run the tests**

```bash
flutter test test/unit/data/api/refresh_on_401_interceptor_test.dart
```

Expected: 6 tests pass. If single-flight test is flaky, increase the `delayed` wait — concurrency in dio's queue can vary by host load.

- [ ] **Step 4: Commit**

```bash
git add app/lib/data/api/refresh_on_401_interceptor.dart app/test/unit/data/api/refresh_on_401_interceptor_test.dart
git commit -m "$(cat <<'EOF'
feat(app): RefreshOn401Interceptor — single-flight + replay

When a response is 401 with slug invalid_access_token, run a
single-flight refresh callback, write the new token to the holder, and
replay the original request once with the fresh Authorization header.
On refresh failure: clear holder + invoke onSignedOut callback.
Replay 401 → give up. kSkipAuth requests bypass.

6 unit tests cover: success, refresh-failure, concurrent-single-flight,
skip-auth-bypass, non-invalid_access_token-slug-passthrough,
replay-still-401.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Auth state + access token Riverpod providers

**Files:**
- Create: `app/lib/presentation/auth/auth_providers.dart`

These providers expose the auth lifecycle to UI consumers. They sit in `presentation/` (not `data/`) because they're framework code that consumers `ref.watch`. The Riverpod providers for the repositories themselves come in Task 16 alongside `AuthRepositoryImpl`.

- [ ] **Step 1: Create the file**

```dart
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';

part 'auth_providers.g.dart';

/// Current auth state — SignedOut on app start; mutated by the bootstrap
/// controller (Task 23), the sign-in controller (Task 24), the sign-out
/// controller (Task 29), and the refresh interceptor's onSignedOut callback.
@Riverpod(keepAlive: true)
class AuthStateNotifier extends _$AuthStateNotifier {
  @override
  AuthState build() => const SignedOut();

  // ignore: use_setters_to_change_properties
  void set(AuthState s) {
    state = s;
  }
}

/// Mirror of AccessTokenHolder for UI consumers. The holder remains the
/// source of truth for dio interceptors; this provider lets widgets and
/// controllers reactively read the token without depending on the holder.
@Riverpod(keepAlive: true)
class AccessTokenNotifier extends _$AccessTokenNotifier {
  @override
  String? build() {
    final holder = ref.read(accessTokenHolderProvider);
    return holder.current;
  }

  void set(String? token) {
    ref.read(accessTokenHolderProvider).set(token);
    state = token;
  }
}
```

- [ ] **Step 2: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Expected: generates `auth_providers.g.dart`.

- [ ] **Step 3: Verify analyze**

```bash
flutter analyze lib/presentation/auth/auth_providers.dart lib/data/api/
```

Expected: "No issues found!"

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/auth/auth_providers.dart app/lib/presentation/auth/auth_providers.g.dart
git commit -m "$(cat <<'EOF'
feat(app): authStateNotifier + accessTokenNotifier Riverpod providers

UI-facing reactive handles for auth lifecycle and current access token.
AccessTokenHolder remains the dio-side source of truth; the notifier
mirrors it so widgets can ref.watch without depending on the holder
directly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 6 — Auth data layer

### Task 15: Auth DTOs + Google sign-in data source

**Files:**
- Create: `app/lib/data/auth/auth_dto.dart`
- Create: `app/lib/data/auth/google_sign_in_data_source.dart`

- [ ] **Step 1: Create `auth_dto.dart`**

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'auth_dto.freezed.dart';
part 'auth_dto.g.dart';

@freezed
class SignInResponseDto with _$SignInResponseDto {
  const factory SignInResponseDto({
    required String access,
    required String refresh,
    required AuthUserDto user,
    AuthApplicantDto? applicant,
  }) = _SignInResponseDto;

  factory SignInResponseDto.fromJson(Map<String, dynamic> json) =>
      _$SignInResponseDtoFromJson(json);
}

@freezed
class RefreshResponseDto with _$RefreshResponseDto {
  const factory RefreshResponseDto({
    required String access,
    required String refresh,
  }) = _RefreshResponseDto;

  factory RefreshResponseDto.fromJson(Map<String, dynamic> json) =>
      _$RefreshResponseDtoFromJson(json);
}

@freezed
class AuthUserDto with _$AuthUserDto {
  const factory AuthUserDto({
    required String id,
    required String email,
    String? displayName,
    required String role,
  }) = _AuthUserDto;

  factory AuthUserDto.fromJson(Map<String, dynamic> json) =>
      _$AuthUserDtoFromJson(json);
}

@freezed
class AuthApplicantDto with _$AuthApplicantDto {
  const factory AuthApplicantDto({
    required String id,
    required String userId,
  }) = _AuthApplicantDto;

  factory AuthApplicantDto.fromJson(Map<String, dynamic> json) =>
      _$AuthApplicantDtoFromJson(json);
}
```

- [ ] **Step 2: Create `google_sign_in_data_source.dart`**

```dart
import 'package:google_sign_in/google_sign_in.dart';

import 'package:kpa_app/core/config/env.dart';
import 'package:kpa_app/core/error/exceptions.dart';

abstract interface class GoogleSignInDataSource {
  /// Runs the platform-correct Google flow and returns the resulting
  /// ID token (JWT) suitable for POST /v1/auth/oauth/google.
  /// Throws AuthException if the user cancels or the SDK fails.
  Future<String> getIdToken();

  /// Best-effort sign-out from Google's side. Errors are swallowed.
  Future<void> signOut();
}

class GoogleSignInDataSourceImpl implements GoogleSignInDataSource {
  GoogleSignInDataSourceImpl([GoogleSignIn? sdk])
      : _sdk = sdk ?? GoogleSignIn(
              // serverClientId must be the WEB client id even on iOS/Android
              // — that's the client id the backend's KPA_GOOGLE_OAUTH_CLIENT_IDS
              // is verifying against.
              serverClientId: Env.googleWebClientId,
              scopes: const ['email', 'profile', 'openid'],
            );

  final GoogleSignIn _sdk;

  @override
  Future<String> getIdToken() async {
    try {
      final account = await _sdk.signIn();
      if (account == null) {
        throw const AuthException(slug: 'google_sign_in_cancelled', detail: 'Sign-in was cancelled.');
      }
      final auth = await account.authentication;
      final idToken = auth.idToken;
      if (idToken == null) {
        throw const AuthException(slug: 'google_id_token_missing', detail: 'Google returned no ID token.');
      }
      return idToken;
    } on AuthException {
      rethrow;
    } catch (e, s) {
      throw AuthException(
        slug: 'google_sign_in_failed',
        detail: e.toString(),
        cause: e,
      );
    }
  }

  @override
  Future<void> signOut() async {
    try {
      await _sdk.signOut();
    } catch (_) {/* swallow */}
  }
}
```

- [ ] **Step 3: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Expected: generates `auth_dto.freezed.dart` and `auth_dto.g.dart`.

- [ ] **Step 4: Verify analyze**

```bash
flutter analyze lib/data/auth/
```

Expected: "No issues found!" (or only generated-file noise the analyzer already excludes).

- [ ] **Step 5: Commit**

```bash
git add app/lib/data/auth/auth_dto.dart app/lib/data/auth/auth_dto.freezed.dart app/lib/data/auth/auth_dto.g.dart app/lib/data/auth/google_sign_in_data_source.dart
git commit -m "$(cat <<'EOF'
feat(app): auth DTOs + GoogleSignInDataSource

SignInResponseDto + RefreshResponseDto + AuthUserDto + AuthApplicantDto
mirror the backend's /v1/auth/oauth/google + /v1/auth/refresh responses.
GoogleSignInDataSource wraps google_sign_in with serverClientId set to
the web client id (required so the backend's aud-claim check passes).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: `AuthRepositoryImpl` + wiring with `RefreshOn401Interceptor`

**Files:**
- Create: `app/lib/data/auth/auth_repository_impl.dart`
- Modify: `app/lib/data/api/dio_provider.dart` (add the refresh interceptor)
- Create: `app/test/unit/data/auth/auth_repository_impl_test.dart`

The implementation needs to be wired such that:
- The dio instance carries `RefreshOn401Interceptor` whose `refresh` callback calls back into the AuthRepository.
- The repo's `refreshSession()` issues `POST /v1/auth/refresh` with `kSkipAuth=true` so the interceptor doesn't loop.

Done via a small Riverpod provider trick: `dioProvider` reads `authRepositoryProvider` for the refresh callback; `authRepositoryProvider` reads `dioProvider` for the dio. This would deadlock without care — we break the cycle by constructing dio first, then attaching the interceptor in a separate Riverpod provider (`dioWithAuthProvider`).

- [ ] **Step 1: Implement `auth_repository_impl.dart`**

```dart
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/error/error_mapping.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/core/log/logger.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/auth/auth_dto.dart';
import 'package:kpa_app/data/auth/google_sign_in_data_source.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/domain/auth/auth_repository.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';

part 'auth_repository_impl.g.dart';

class AuthRepositoryImpl implements AuthRepository {
  AuthRepositoryImpl({
    required Dio dio,
    required AccessTokenHolder accessHolder,
    required TokenStorage tokenStorage,
    required GoogleSignInDataSource google,
    required void Function(AuthState) emit,
    required AuthState Function() readState,
  })  : _dio = dio,
        _accessHolder = accessHolder,
        _tokenStorage = tokenStorage,
        _google = google,
        _emit = emit,
        _readState = readState;

  final Dio _dio;
  final AccessTokenHolder _accessHolder;
  final TokenStorage _tokenStorage;
  final GoogleSignInDataSource _google;
  final void Function(AuthState) _emit;
  final AuthState Function() _readState;
  final _log = KpaLogger.named('auth.repo');
  final _controller = StreamController<AuthState>.broadcast();

  @override
  Stream<AuthState> watch() => _controller.stream;

  @override
  AuthState get current => _readState();

  void _push(AuthState s) {
    _emit(s);
    _controller.add(s);
  }

  @override
  Future<SignedIn> signInWithGoogle() async {
    _push(const Authenticating());
    try {
      final idToken = await _google.getIdToken();
      final res = await _dio.post<Map<String, dynamic>>(
        '/v1/auth/oauth/google',
        data: {'id_token': idToken},
        options: Options(extra: {kSkipAuth: true}),
      );
      final dto = SignInResponseDto.fromJson(res.data!);
      _accessHolder.set(dto.access);
      await _tokenStorage.writeRefreshToken(dto.refresh);
      final signedIn = SignedIn(
        userId: dto.user.id,
        email: dto.user.email,
        displayName: dto.user.displayName,
      );
      _push(signedIn);
      return signedIn;
    } on DioException catch (e) {
      _push(const SignedOut());
      throw mapDioException(e);
    } on AuthException {
      _push(const SignedOut());
      rethrow;
    }
  }

  @override
  Future<SignedIn> refreshSession() async {
    final stored = await _tokenStorage.readRefreshToken();
    if (stored == null) {
      throw const AuthException(slug: 'no_refresh_token', detail: 'Nothing to refresh.');
    }
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/v1/auth/refresh',
        data: {'refresh': stored},
        options: Options(extra: {kSkipAuth: true}),
      );
      final dto = RefreshResponseDto.fromJson(res.data!);
      _accessHolder.set(dto.access);
      await _tokenStorage.writeRefreshToken(dto.refresh);
      // Hydrate the user identity by hitting /v1/me — splash uses this.
      final me = await _dio.get<Map<String, dynamic>>('/v1/me');
      final user = me.data!['user'] as Map<String, dynamic>;
      final signedIn = SignedIn(
        userId: user['id'] as String,
        email: user['email'] as String,
        displayName: user['display_name'] as String?,
      );
      _push(signedIn);
      return signedIn;
    } on DioException catch (e) {
      _accessHolder.clear();
      await _tokenStorage.clear();
      _push(const SignedOut());
      throw mapDioException(e);
    }
  }

  /// Refresh callback used by RefreshOn401Interceptor. Returns the new
  /// access token; the interceptor handles holder updates + replay.
  Future<String> refreshAccessTokenForInterceptor() async {
    final stored = await _tokenStorage.readRefreshToken();
    if (stored == null) {
      throw const AuthException(slug: 'no_refresh_token');
    }
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/refresh',
      data: {'refresh': stored},
      options: Options(extra: {kSkipAuth: true}),
    );
    final dto = RefreshResponseDto.fromJson(res.data!);
    await _tokenStorage.writeRefreshToken(dto.refresh);
    return dto.access;
  }

  @override
  Future<void> signOut() async {
    try {
      await _dio.post<dynamic>('/v1/auth/logout');
    } catch (e, s) {
      _log.warn('logout request failed (continuing)', error: e, stack: s);
    }
    await _google.signOut();
    _accessHolder.clear();
    await _tokenStorage.clear();
    _push(const SignedOut());
  }
}
```

- [ ] **Step 2: Add the wiring providers + refresh interceptor attachment**

Append to `app/lib/data/api/dio_provider.dart`:

```dart
import 'refresh_on_401_interceptor.dart';

/// Provider for AuthRepository — see auth_repository_impl.dart for the
/// concrete impl. Declared here to break the import cycle (dioProvider
/// needs it for the refresh callback; authRepoProvider needs dio).
///
/// The cycle is resolved by:
///   1. Build the base Dio with only the request-id + auth-header interceptors.
///   2. Build AuthRepository, passing it that base Dio.
///   3. Wrap with RefreshOn401Interceptor in `dioProvider` (overrides the
///      base accessor lazily via the holder pattern).
///
/// We expose dioProvider as the SINGLE Dio instance for the whole app;
/// it gets the refresh interceptor attached at first read.
```

Actually the cleanest resolution: redefine `dioProvider` as a single provider that wires everything in order. Replace the existing `dioProvider` body with:

```dart
@Riverpod(keepAlive: true)
Dio dio(Ref ref) {
  final holder = ref.read(accessTokenHolderProvider);
  final dio = Dio(BaseOptions(
    baseUrl: Env.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    contentType: 'application/json',
    responseType: ResponseType.json,
    validateStatus: (s) => s != null && s < 500,
  ));
  dio.interceptors.add(RequestIdInterceptor());
  dio.interceptors.add(AuthHeaderInterceptor(holder));

  // Lazily build the auth repo on first refresh — by then all the other
  // wiring (tokenStorage, google) is available, and the repo's
  // refreshAccessTokenForInterceptor closure captures the same `dio`.
  dio.interceptors.add(RefreshOn401Interceptor(
    holder: holder,
    dio: dio,
    refresh: () async {
      final repo = ref.read(authRepositoryProvider);
      return (repo as AuthRepositoryImpl).refreshAccessTokenForInterceptor();
    },
    onSignedOut: () {
      // Imperative push to the notifier. Safe inside Riverpod read.
      ref.read(authStateNotifierProvider.notifier).set(const SignedOut());
    },
  ));
  return dio;
}
```

The `authStateNotifierProvider` import is from `presentation/auth/auth_providers.dart`. We're letting `data/` depend on a `presentation/` notifier here — a minor layering wart that's preferable to adding an indirection just for this edge case. Documented inline:

```dart
// LAYERING NOTE: dio_provider intentionally references the presentation-layer
// authStateNotifierProvider to push SignedOut on refresh failure. The
// alternative (yet another callback indirection) costs clarity for no real
// purchase; this is the one allowed exception to data/→presentation/ purity.
```

- [ ] **Step 3: Create `authRepositoryProvider`**

Append to `app/lib/data/auth/auth_repository_impl.dart`:

```dart
@Riverpod(keepAlive: true)
AuthRepository authRepository(Ref ref) {
  return AuthRepositoryImpl(
    dio: ref.read(dioProvider),
    accessHolder: ref.read(accessTokenHolderProvider),
    tokenStorage: ref.read(tokenStorageProvider),
    google: GoogleSignInDataSourceImpl(),
    emit: (s) => ref.read(authStateNotifierProvider.notifier).set(s),
    readState: () => ref.read(authStateNotifierProvider),
  );
}
```

- [ ] **Step 4: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Expected: generates `auth_repository_impl.g.dart`; regenerates `dio_provider.g.dart`.

- [ ] **Step 5: Write tests**

Create `app/test/unit/data/auth/auth_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/auth/auth_repository_impl.dart';
import 'package:kpa_app/data/auth/google_sign_in_data_source.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:mocktail/mocktail.dart';

import '../auth/token_storage_test.dart'; // pulls in InMemoryTokenStorage

class _FakeGoogle implements GoogleSignInDataSource {
  _FakeGoogle({this.idToken = 'GOOGLE_ID_TOKEN'});
  String? idToken;
  @override Future<String> getIdToken() async {
    if (idToken == null) throw Exception('cancelled');
    return idToken!;
  }
  @override Future<void> signOut() async {}
}

void main() {
  late Dio dio;
  late DioAdapter adapter;
  late AccessTokenHolder holder;
  late InMemoryTokenStorage storage;
  late _FakeGoogle google;
  late AuthState state;
  late AuthRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    adapter = DioAdapter(dio: dio);
    holder = AccessTokenHolder();
    storage = InMemoryTokenStorage();
    google = _FakeGoogle();
    state = const SignedOut();
    repo = AuthRepositoryImpl(
      dio: dio, accessHolder: holder, tokenStorage: storage,
      google: google,
      emit: (s) => state = s,
      readState: () => state,
    );
  });

  test('signInWithGoogle: 200 → SignedIn, tokens persisted', () async {
    adapter.onPost('/v1/auth/oauth/google', (s) => s.reply(200, {
      'access': 'ACCESS_A', 'refresh': 'REFRESH_A',
      'user': {'id': 'u1', 'email': 'u@e.com', 'display_name': 'U', 'role': 'applicant'},
      'applicant': {'id': 'a1', 'user_id': 'u1'},
    }));
    final si = await repo.signInWithGoogle();
    expect(si.userId, 'u1');
    expect(holder.current, 'ACCESS_A');
    expect(await storage.readRefreshToken(), 'REFRESH_A');
    expect(state, isA<SignedIn>());
  });

  test('signInWithGoogle: 401 → throws AuthException, state SignedOut', () async {
    adapter.onPost('/v1/auth/oauth/google', (s) => s.reply(401, {
      'status': 401, 'slug': 'invalid_google_token', 'detail': 'bad',
    }));
    await expectLater(repo.signInWithGoogle(), throwsA(isA<Exception>()));
    expect(state, isA<SignedOut>());
    expect(holder.current, isNull);
  });

  test('refreshSession: no stored token → AuthException', () async {
    await expectLater(repo.refreshSession(), throwsA(isA<Exception>()));
  });

  test('refreshSession: 200 → SignedIn, tokens updated', () async {
    await storage.writeRefreshToken('OLD');
    adapter
      ..onPost('/v1/auth/refresh', (s) => s.reply(200, {'access': 'NEW', 'refresh': 'NEW_RT'}))
      ..onGet('/v1/me', (s) => s.reply(200, {'user': {'id': 'u1', 'email': 'u@e.com', 'display_name': 'U'}}));
    final si = await repo.refreshSession();
    expect(si.userId, 'u1');
    expect(holder.current, 'NEW');
    expect(await storage.readRefreshToken(), 'NEW_RT');
  });

  test('refreshSession: 401 → clear + SignedOut + throws', () async {
    await storage.writeRefreshToken('OLD');
    adapter.onPost('/v1/auth/refresh', (s) => s.reply(401, {'status': 401, 'slug': 'invalid_refresh_token'}));
    await expectLater(repo.refreshSession(), throwsA(isA<Exception>()));
    expect(holder.current, isNull);
    expect(await storage.readRefreshToken(), isNull);
    expect(state, isA<SignedOut>());
  });

  test('signOut: clears everything regardless of network outcome', () async {
    holder.set('ACCESS');
    await storage.writeRefreshToken('RT');
    adapter.onPost('/v1/auth/logout', (s) => s.reply(500, {})); // even on failure...
    await repo.signOut();
    expect(holder.current, isNull);
    expect(await storage.readRefreshToken(), isNull);
    expect(state, isA<SignedOut>());
  });
}
```

- [ ] **Step 6: Run tests**

```bash
flutter test test/unit/data/auth/
```

Expected: 4 (storage) + 6 (repo) = 10 tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/lib/data/auth/auth_repository_impl.dart app/lib/data/auth/auth_repository_impl.g.dart app/lib/data/api/dio_provider.dart app/lib/data/api/dio_provider.g.dart app/test/unit/data/auth/auth_repository_impl_test.dart
git commit -m "$(cat <<'EOF'
feat(app): AuthRepositoryImpl + dio wired with RefreshOn401Interceptor

Sign-in → POST /v1/auth/oauth/google (kSkipAuth=true), persists access
in holder + refresh in TokenStorage. refreshSession → POST /v1/auth/refresh
+ GET /v1/me to hydrate identity. signOut → POST /v1/auth/logout (best
effort) + clear everything + emit SignedOut.

dioProvider now attaches RefreshOn401Interceptor whose refresh callback
lazily reads AuthRepository (cycle resolved by lazy ref.read at refresh
time, not construction time).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 7 — DTOs + remaining repositories

### Task 17: Feed DTOs + `FeedApi` + `FeedRepositoryImpl`

**Files:**
- Create: `app/lib/data/feed/feed_dto.dart`
- Create: `app/lib/data/feed/feed_api.dart`
- Create: `app/lib/data/feed/feed_repository_impl.dart`
- Create: `app/test/unit/data/feed/feed_repository_impl_test.dart`

`JobSummaryDto`, `EmployerSummaryDto`, `ExplanationDto`, and `MatchSummaryDto` live in `feed_dto.dart` because Feed is the first consumer. Other repos (jobs, applications, saved) import them from here.

- [ ] **Step 1: Create `feed_dto.dart`**

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'feed_dto.freezed.dart';
part 'feed_dto.g.dart';

@freezed
class FeedPageDto with _$FeedPageDto {
  const factory FeedPageDto({
    required List<FeedItemDto> items,
    String? nextCursor,
  }) = _FeedPageDto;

  factory FeedPageDto.fromJson(Map<String, dynamic> json) => _$FeedPageDtoFromJson(json);
}

@freezed
class FeedItemDto with _$FeedItemDto {
  const factory FeedItemDto({
    required MatchSummaryDto match,
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
  }) = _FeedItemDto;

  factory FeedItemDto.fromJson(Map<String, dynamic> json) => _$FeedItemDtoFromJson(json);
}

@freezed
class MatchSummaryDto with _$MatchSummaryDto {
  const factory MatchSummaryDto({
    required String id,
    required double totalScore,
    required Map<String, dynamic> scoreComponents,
    ExplanationDto? explanation,
    DateTime? surfacedAt,
  }) = _MatchSummaryDto;

  factory MatchSummaryDto.fromJson(Map<String, dynamic> json) => _$MatchSummaryDtoFromJson(json);
}

@freezed
class ExplanationDto with _$ExplanationDto {
  const factory ExplanationDto({
    required String fit,
    String? caveat,
    required String generator,
    required String generatorVersion,
  }) = _ExplanationDto;

  factory ExplanationDto.fromJson(Map<String, dynamic> json) => _$ExplanationDtoFromJson(json);
}

@freezed
class JobSummaryDto with _$JobSummaryDto {
  const factory JobSummaryDto({
    required String id,
    required String title,
    required String location,
    required String status,            // "open" | "closed"
    required DateTime postedAt,
    String? description,
  }) = _JobSummaryDto;

  factory JobSummaryDto.fromJson(Map<String, dynamic> json) => _$JobSummaryDtoFromJson(json);
}

@freezed
class EmployerSummaryDto with _$EmployerSummaryDto {
  const factory EmployerSummaryDto({
    required String id,
    required String name,
    DateTime? verifiedAt,
  }) = _EmployerSummaryDto;

  factory EmployerSummaryDto.fromJson(Map<String, dynamic> json) => _$EmployerSummaryDtoFromJson(json);
}
```

- [ ] **Step 2: Create `feed_api.dart`**

```dart
import 'package:dio/dio.dart';

import 'feed_dto.dart';

class FeedApi {
  FeedApi(this._dio);
  final Dio _dio;

  Future<FeedPageDto> getFeed({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/feed',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return FeedPageDto.fromJson(res.data!);
  }
}
```

- [ ] **Step 3: Create `feed_repository_impl.dart`**

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/error/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/feed/feed_api.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';

part 'feed_repository_impl.g.dart';

class FeedRepositoryImpl implements FeedRepository {
  FeedRepositoryImpl(this._api);
  final FeedApi _api;

  @override
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async {
    try {
      return await _api.getFeed(cursor: cursor, limit: limit);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
FeedRepository feedRepository(Ref ref) =>
    FeedRepositoryImpl(FeedApi(ref.read(dioProvider)));
```

- [ ] **Step 4: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

- [ ] **Step 5: Write the test**

Create `app/test/unit/data/feed/feed_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/feed/feed_api.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';

Map<String, dynamic> _samplePage({String? next}) => {
  'items': [
    {
      'match': {
        'id': 'm1', 'total_score': 0.81,
        'score_components': {'vec': 0.9, 'rules': 0.7},
        'explanation': {'fit': 'great', 'caveat': null, 'generator': 'templated', 'generator_version': '1'},
        'surfaced_at': '2026-05-20T10:00:00Z',
      },
      'job': {
        'id': 'j1', 'title': 'Eng', 'location': 'Bangalore',
        'status': 'open', 'posted_at': '2026-05-18T00:00:00Z',
      },
      'employer': {'id': 'e1', 'name': 'Acme', 'verified_at': '2026-01-01T00:00:00Z'},
    }
  ],
  'next_cursor': next,
};

void main() {
  late Dio dio;
  late DioAdapter adapter;
  late FeedRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    adapter = DioAdapter(dio: dio);
    repo = FeedRepositoryImpl(FeedApi(dio));
  });

  test('200 → FeedPageDto with parsed items', () async {
    adapter.onGet('/v1/feed', (s) => s.reply(200, _samplePage(next: 'c1')),
        queryParameters: {'limit': 20});
    final page = await repo.fetchPage();
    expect(page.items.single.job.title, 'Eng');
    expect(page.items.single.match.totalScore, 0.81);
    expect(page.nextCursor, 'c1');
  });

  test('cursor passed through', () async {
    adapter.onGet('/v1/feed', (s) => s.reply(200, _samplePage()),
        queryParameters: {'limit': 20, 'cursor': 'xyz'});
    final page = await repo.fetchPage(cursor: 'xyz');
    expect(page.nextCursor, isNull);
  });

  test('401 invalid_access_token → AuthException', () async {
    adapter.onGet('/v1/feed', (s) => s.reply(401, {
      'status': 401, 'slug': 'invalid_access_token',
    }), queryParameters: {'limit': 20});
    await expectLater(repo.fetchPage(), throwsA(isA<AuthException>()));
  });

  test('500 → ApiException', () async {
    adapter.onGet('/v1/feed', (s) => s.reply(500, {}),
        queryParameters: {'limit': 20});
    await expectLater(repo.fetchPage(), throwsA(isA<ApiException>()));
  });
}
```

- [ ] **Step 6: Run tests**

```bash
flutter test test/unit/data/feed/
```

Expected: 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/lib/data/feed/ app/test/unit/data/feed/
git commit -m "$(cat <<'EOF'
feat(app): feed DTOs + FeedApi + FeedRepositoryImpl

FeedPageDto + FeedItemDto + MatchSummaryDto + ExplanationDto +
JobSummaryDto + EmployerSummaryDto (latter four reused by jobs /
applications / saved repos). DioException → KpaException mapping
via error_mapping.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: Jobs DTOs + `JobsApi` + `JobsRepositoryImpl`

**Files:**
- Create: `app/lib/data/jobs/jobs_dto.dart`
- Create: `app/lib/data/jobs/jobs_api.dart`
- Create: `app/lib/data/jobs/jobs_repository_impl.dart`
- Create: `app/test/unit/data/jobs/jobs_repository_impl_test.dart`

- [ ] **Step 1: Create `jobs_dto.dart`**

```dart
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';

part 'jobs_dto.freezed.dart';
part 'jobs_dto.g.dart';

/// Full job detail = job + employer + (optional) match for the current
/// applicant + (optional) Application + (optional) SavedJob.
@freezed
class JobDetailDto with _$JobDetailDto {
  const factory JobDetailDto({
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
    MatchSummaryDto? match,
    ApplicationDto? application,
    SavedJobDto? savedJob,
  }) = _JobDetailDto;

  factory JobDetailDto.fromJson(Map<String, dynamic> json) => _$JobDetailDtoFromJson(json);
}

@freezed
class ApplicationDto with _$ApplicationDto {
  const factory ApplicationDto({
    required String id,
    required String applicantId,
    required String jobId,
    required String status,        // applied | withdrawn
    required String source,
    required DateTime createdAt,
    DateTime? withdrawnAt,
  }) = _ApplicationDto;

  factory ApplicationDto.fromJson(Map<String, dynamic> json) => _$ApplicationDtoFromJson(json);
}

@freezed
class SavedJobDto with _$SavedJobDto {
  const factory SavedJobDto({
    required String id,
    required String applicantId,
    required String jobId,
    required DateTime createdAt,
  }) = _SavedJobDto;

  factory SavedJobDto.fromJson(Map<String, dynamic> json) => _$SavedJobDtoFromJson(json);
}

@freezed
class ApplicationsPageDto with _$ApplicationsPageDto {
  const factory ApplicationsPageDto({
    required List<ApplicationListItemDto> items,
    String? nextCursor,
  }) = _ApplicationsPageDto;

  factory ApplicationsPageDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationsPageDtoFromJson(json);
}

@freezed
class ApplicationListItemDto with _$ApplicationListItemDto {
  const factory ApplicationListItemDto({
    required ApplicationDto application,
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
  }) = _ApplicationListItemDto;

  factory ApplicationListItemDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationListItemDtoFromJson(json);
}

@freezed
class SavedJobsPageDto with _$SavedJobsPageDto {
  const factory SavedJobsPageDto({
    required List<SavedJobListItemDto> items,
    String? nextCursor,
  }) = _SavedJobsPageDto;

  factory SavedJobsPageDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobsPageDtoFromJson(json);
}

@freezed
class SavedJobListItemDto with _$SavedJobListItemDto {
  const factory SavedJobListItemDto({
    required SavedJobDto saved,
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
    MatchSummaryDto? match,
  }) = _SavedJobListItemDto;

  factory SavedJobListItemDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobListItemDtoFromJson(json);
}
```

- [ ] **Step 2: Create `jobs_api.dart`**

```dart
import 'package:dio/dio.dart';

import 'jobs_dto.dart';

class JobsApi {
  JobsApi(this._dio);
  final Dio _dio;

  Future<JobDetailDto> getJob(String id) async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/jobs/$id');
    return JobDetailDto.fromJson(res.data!);
  }

  Future<ApplicationDto> apply(String jobId, {String source = 'feed'}) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/jobs/$jobId/apply',
      data: {'source': source},
    );
    return ApplicationDto.fromJson(res.data!);
  }

  Future<SavedJobDto> save(String jobId) async {
    final res = await _dio.post<Map<String, dynamic>>('/v1/jobs/$jobId/save');
    return SavedJobDto.fromJson(res.data!);
  }

  Future<void> unsave(String jobId) async {
    await _dio.delete<dynamic>('/v1/jobs/$jobId/save');
  }
}
```

- [ ] **Step 3: Create `jobs_repository_impl.dart`**

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/error/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/jobs/jobs_api.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/domain/jobs/jobs_repository.dart';

part 'jobs_repository_impl.g.dart';

class JobsRepositoryImpl implements JobsRepository {
  JobsRepositoryImpl(this._api);
  final JobsApi _api;

  @override
  Future<JobDetailDto> fetchById(String jobId) async {
    try { return await _api.getJob(jobId); }
    on DioException catch (e) { throw mapDioException(e); }
  }

  @override
  Future<ApplicationDto> applyTo(String jobId, {String source = 'feed'}) async {
    try { return await _api.apply(jobId, source: source); }
    on DioException catch (e) { throw mapDioException(e); }
  }

  @override
  Future<SavedJobDto> save(String jobId) async {
    try { return await _api.save(jobId); }
    on DioException catch (e) { throw mapDioException(e); }
  }

  @override
  Future<void> unsave(String jobId) async {
    try { await _api.unsave(jobId); }
    on DioException catch (e) { throw mapDioException(e); }
  }
}

@Riverpod(keepAlive: true)
JobsRepository jobsRepository(Ref ref) =>
    JobsRepositoryImpl(JobsApi(ref.read(dioProvider)));
```

- [ ] **Step 4: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

- [ ] **Step 5: Write the test**

Create `app/test/unit/data/jobs/jobs_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/jobs/jobs_api.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';

Map<String, dynamic> _jobDetail() => {
  'job': {'id': 'j1', 'title': 'Eng', 'location': 'Bangalore',
          'status': 'open', 'posted_at': '2026-05-18T00:00:00Z'},
  'employer': {'id': 'e1', 'name': 'Acme'},
  'match': null, 'application': null, 'saved_job': null,
};

void main() {
  late Dio dio;
  late DioAdapter adapter;
  late JobsRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    adapter = DioAdapter(dio: dio);
    repo = JobsRepositoryImpl(JobsApi(dio));
  });

  test('fetchById: 200 → JobDetailDto', () async {
    adapter.onGet('/v1/jobs/j1', (s) => s.reply(200, _jobDetail()));
    final d = await repo.fetchById('j1');
    expect(d.job.title, 'Eng');
  });

  test('fetchById: 404 → ApiException', () async {
    adapter.onGet('/v1/jobs/missing', (s) => s.reply(404, {'status': 404, 'slug': 'not_found'}));
    await expectLater(repo.fetchById('missing'), throwsA(isA<ApiException>()));
  });

  test('applyTo: 201 → ApplicationDto', () async {
    adapter.onPost('/v1/jobs/j1/apply', (s) => s.reply(201, {
      'id': 'a1', 'applicant_id': 'ap1', 'job_id': 'j1',
      'status': 'applied', 'source': 'feed',
      'created_at': '2026-05-21T12:00:00Z', 'withdrawn_at': null,
    }), data: {'source': 'feed'});
    final a = await repo.applyTo('j1');
    expect(a.id, 'a1');
    expect(a.status, 'applied');
  });

  test('save: 201 → SavedJobDto', () async {
    adapter.onPost('/v1/jobs/j1/save', (s) => s.reply(201, {
      'id': 's1', 'applicant_id': 'ap1', 'job_id': 'j1',
      'created_at': '2026-05-21T12:00:00Z',
    }));
    final s = await repo.save('j1');
    expect(s.id, 's1');
  });

  test('unsave: 204 → returns', () async {
    adapter.onDelete('/v1/jobs/j1/save', (s) => s.reply(204, null));
    await repo.unsave('j1');
  });
}
```

- [ ] **Step 6: Run tests**

```bash
flutter test test/unit/data/jobs/jobs_repository_impl_test.dart
```

Expected: 5 tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/lib/data/jobs/jobs_dto.dart app/lib/data/jobs/jobs_dto.freezed.dart app/lib/data/jobs/jobs_dto.g.dart app/lib/data/jobs/jobs_api.dart app/lib/data/jobs/jobs_repository_impl.dart app/lib/data/jobs/jobs_repository_impl.g.dart app/test/unit/data/jobs/jobs_repository_impl_test.dart
git commit -m "$(cat <<'EOF'
feat(app): jobs DTOs + JobsApi + JobsRepositoryImpl

JobDetailDto + ApplicationDto + SavedJobDto + paginated list DTOs.
JobsRepository covers fetchById + applyTo + save + unsave; the read
methods for applications/saved lists are owned by their own repos
(Tasks 19-20) to keep each repo focused.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: `ApplicationsApi` + `ApplicationsRepositoryImpl`

**Files:**
- Create: `app/lib/data/jobs/applications_api.dart`
- Create: `app/lib/data/jobs/applications_repository_impl.dart`
- Create: `app/test/unit/data/jobs/applications_repository_impl_test.dart`

DTOs already live in `jobs_dto.dart` (Task 18).

- [ ] **Step 1: Create `applications_api.dart`**

```dart
import 'package:dio/dio.dart';

import 'jobs_dto.dart';

class ApplicationsApi {
  ApplicationsApi(this._dio);
  final Dio _dio;

  Future<ApplicationsPageDto> list({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/applications',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return ApplicationsPageDto.fromJson(res.data!);
  }

  Future<ApplicationDto> withdraw(String applicationId) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/applications/$applicationId',
      data: {'status': 'withdrawn'},
    );
    return ApplicationDto.fromJson(res.data!);
  }
}
```

- [ ] **Step 2: Create `applications_repository_impl.dart`**

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/error/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/jobs/applications_api.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/domain/jobs/applications_repository.dart';

part 'applications_repository_impl.g.dart';

class ApplicationsRepositoryImpl implements ApplicationsRepository {
  ApplicationsRepositoryImpl(this._api);
  final ApplicationsApi _api;

  @override
  Future<ApplicationsPageDto> fetchPage({String? cursor, int limit = 20}) async {
    try { return await _api.list(cursor: cursor, limit: limit); }
    on DioException catch (e) { throw mapDioException(e); }
  }

  @override
  Future<ApplicationDto> withdraw(String applicationId) async {
    try { return await _api.withdraw(applicationId); }
    on DioException catch (e) { throw mapDioException(e); }
  }
}

@Riverpod(keepAlive: true)
ApplicationsRepository applicationsRepository(Ref ref) =>
    ApplicationsRepositoryImpl(ApplicationsApi(ref.read(dioProvider)));
```

- [ ] **Step 3: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

- [ ] **Step 4: Write the test**

Create `app/test/unit/data/jobs/applications_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/jobs/applications_api.dart';
import 'package:kpa_app/data/jobs/applications_repository_impl.dart';

Map<String, dynamic> _appsPage() => {
  'items': [
    {
      'application': {
        'id': 'a1', 'applicant_id': 'ap1', 'job_id': 'j1',
        'status': 'applied', 'source': 'feed',
        'created_at': '2026-05-21T12:00:00Z', 'withdrawn_at': null,
      },
      'job': {'id': 'j1', 'title': 'Eng', 'location': 'BLR',
              'status': 'open', 'posted_at': '2026-05-18T00:00:00Z'},
      'employer': {'id': 'e1', 'name': 'Acme'},
    }
  ],
  'next_cursor': null,
};

void main() {
  late Dio dio;
  late DioAdapter adapter;
  late ApplicationsRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    adapter = DioAdapter(dio: dio);
    repo = ApplicationsRepositoryImpl(ApplicationsApi(dio));
  });

  test('fetchPage: 200 → ApplicationsPageDto', () async {
    adapter.onGet('/v1/applications', (s) => s.reply(200, _appsPage()),
        queryParameters: {'limit': 20});
    final page = await repo.fetchPage();
    expect(page.items.single.application.id, 'a1');
  });

  test('withdraw: 200 → ApplicationDto with withdrawn status', () async {
    adapter.onPatch('/v1/applications/a1', (s) => s.reply(200, {
      'id': 'a1', 'applicant_id': 'ap1', 'job_id': 'j1',
      'status': 'withdrawn', 'source': 'feed',
      'created_at': '2026-05-21T12:00:00Z', 'withdrawn_at': '2026-05-22T09:00:00Z',
    }), data: {'status': 'withdrawn'});
    final a = await repo.withdraw('a1');
    expect(a.status, 'withdrawn');
    expect(a.withdrawnAt, isNotNull);
  });

  test('withdraw: 400 invalid_transition → ApiException', () async {
    adapter.onPatch('/v1/applications/a1', (s) => s.reply(400, {
      'status': 400, 'slug': 'invalid_transition',
    }), data: {'status': 'withdrawn'});
    await expectLater(repo.withdraw('a1'), throwsA(isA<ApiException>()));
  });
}
```

- [ ] **Step 5: Run tests**

```bash
flutter test test/unit/data/jobs/applications_repository_impl_test.dart
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/lib/data/jobs/applications_api.dart app/lib/data/jobs/applications_repository_impl.dart app/lib/data/jobs/applications_repository_impl.g.dart app/test/unit/data/jobs/applications_repository_impl_test.dart
git commit -m "$(cat <<'EOF'
feat(app): ApplicationsApi + ApplicationsRepositoryImpl

GET /v1/applications list + PATCH /v1/applications/:id withdraw.
DTOs were defined in jobs_dto.dart (Task 18).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: `SavedJobsApi` + `SavedJobsRepositoryImpl`

**Files:**
- Create: `app/lib/data/jobs/saved_jobs_api.dart`
- Create: `app/lib/data/jobs/saved_jobs_repository_impl.dart`
- Create: `app/test/unit/data/jobs/saved_jobs_repository_impl_test.dart`

- [ ] **Step 1: Create `saved_jobs_api.dart`**

```dart
import 'package:dio/dio.dart';

import 'jobs_dto.dart';

class SavedJobsApi {
  SavedJobsApi(this._dio);
  final Dio _dio;

  Future<SavedJobsPageDto> list({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/saved',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return SavedJobsPageDto.fromJson(res.data!);
  }
}
```

- [ ] **Step 2: Create `saved_jobs_repository_impl.dart`**

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/error/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/saved_jobs_api.dart';
import 'package:kpa_app/domain/jobs/saved_jobs_repository.dart';

part 'saved_jobs_repository_impl.g.dart';

class SavedJobsRepositoryImpl implements SavedJobsRepository {
  SavedJobsRepositoryImpl(this._api);
  final SavedJobsApi _api;

  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async {
    try { return await _api.list(cursor: cursor, limit: limit); }
    on DioException catch (e) { throw mapDioException(e); }
  }
}

@Riverpod(keepAlive: true)
SavedJobsRepository savedJobsRepository(Ref ref) =>
    SavedJobsRepositoryImpl(SavedJobsApi(ref.read(dioProvider)));
```

- [ ] **Step 3: Run codegen + write test**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/unit/data/jobs/saved_jobs_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/data/jobs/saved_jobs_api.dart';
import 'package:kpa_app/data/jobs/saved_jobs_repository_impl.dart';

void main() {
  test('fetchPage: 200 → SavedJobsPageDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final adapter = DioAdapter(dio: dio);
    adapter.onGet('/v1/saved', (s) => s.reply(200, {
      'items': [
        {
          'saved': {'id': 's1', 'applicant_id': 'ap1', 'job_id': 'j1',
                    'created_at': '2026-05-21T12:00:00Z'},
          'job': {'id': 'j1', 'title': 'Eng', 'location': 'BLR',
                  'status': 'open', 'posted_at': '2026-05-18T00:00:00Z'},
          'employer': {'id': 'e1', 'name': 'Acme'},
          'match': null,
        }
      ],
      'next_cursor': null,
    }), queryParameters: {'limit': 20});
    final repo = SavedJobsRepositoryImpl(SavedJobsApi(dio));
    final page = await repo.fetchPage();
    expect(page.items.single.saved.id, 's1');
  });
}
```

- [ ] **Step 4: Run tests + commit**

```bash
flutter test test/unit/data/jobs/saved_jobs_repository_impl_test.dart
git add app/lib/data/jobs/saved_jobs_api.dart app/lib/data/jobs/saved_jobs_repository_impl.dart app/lib/data/jobs/saved_jobs_repository_impl.g.dart app/test/unit/data/jobs/saved_jobs_repository_impl_test.dart
git commit -m "$(cat <<'EOF'
feat(app): SavedJobsApi + SavedJobsRepositoryImpl

GET /v1/saved list. Save/unsave mutations live on JobsRepository
since they're keyed by jobId (per /v1/jobs/:id/save URL shape).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 21: `MeApi` + `MeRepositoryImpl`

**Files:**
- Create: `app/lib/data/me/me_dto.dart`
- Create: `app/lib/data/me/me_api.dart`
- Create: `app/lib/data/me/me_repository_impl.dart`
- Create: `app/test/unit/data/me/me_repository_impl_test.dart`

- [ ] **Step 1: Create `me_dto.dart`**

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'me_dto.freezed.dart';
part 'me_dto.g.dart';

@freezed
class MeDto with _$MeDto {
  const factory MeDto({
    required MeUserDto user,
    ApplicantSummaryDto? applicant,
  }) = _MeDto;

  factory MeDto.fromJson(Map<String, dynamic> json) => _$MeDtoFromJson(json);
}

@freezed
class MeUserDto with _$MeUserDto {
  const factory MeUserDto({
    required String id,
    required String email,
    String? displayName,
    required String role,
    required DateTime createdAt,
  }) = _MeUserDto;

  factory MeUserDto.fromJson(Map<String, dynamic> json) => _$MeUserDtoFromJson(json);
}

@freezed
class ApplicantSummaryDto with _$ApplicantSummaryDto {
  const factory ApplicantSummaryDto({
    required String id,
    required String userId,
  }) = _ApplicantSummaryDto;

  factory ApplicantSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicantSummaryDtoFromJson(json);
}
```

- [ ] **Step 2: Create `me_api.dart` + `me_repository_impl.dart`**

```dart
// me_api.dart
import 'package:dio/dio.dart';
import 'me_dto.dart';

class MeApi {
  MeApi(this._dio);
  final Dio _dio;
  Future<MeDto> getMe() async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/me');
    return MeDto.fromJson(res.data!);
  }
}
```

```dart
// me_repository_impl.dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/error/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/me/me_api.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/domain/me/me_repository.dart';

part 'me_repository_impl.g.dart';

class MeRepositoryImpl implements MeRepository {
  MeRepositoryImpl(this._api);
  final MeApi _api;

  @override
  Future<MeDto> fetch() async {
    try { return await _api.getMe(); }
    on DioException catch (e) { throw mapDioException(e); }
  }
}

@Riverpod(keepAlive: true)
MeRepository meRepository(Ref ref) =>
    MeRepositoryImpl(MeApi(ref.read(dioProvider)));
```

- [ ] **Step 3: Run codegen + write test**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/unit/data/me/me_repository_impl_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';
import 'package:kpa_app/data/me/me_api.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';

void main() {
  test('fetch: 200 → MeDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final adapter = DioAdapter(dio: dio);
    adapter.onGet('/v1/me', (s) => s.reply(200, {
      'user': {
        'id': 'u1', 'email': 'u@e.com', 'display_name': 'U', 'role': 'applicant',
        'created_at': '2026-05-21T12:00:00Z',
      },
      'applicant': {'id': 'a1', 'user_id': 'u1'},
    }));
    final repo = MeRepositoryImpl(MeApi(dio));
    final me = await repo.fetch();
    expect(me.user.email, 'u@e.com');
    expect(me.applicant?.id, 'a1');
  });
}
```

- [ ] **Step 4: Run tests + commit**

```bash
flutter test test/unit/data/me/
git add app/lib/data/me/ app/test/unit/data/me/
git commit -m "$(cat <<'EOF'
feat(app): MeApi + MeRepositoryImpl

GET /v1/me — returns user + optional applicant. Profile screen and
splash bootstrap both consume.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 22 — Quick sanity check after all repos land

- [ ] **Run the full unit suite + analyze**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
flutter analyze
flutter test test/unit/
```

Expected: analyze clean; ~30+ tests pass (numbers grow with each task; failures here mean a regression slipped in during Phase 7).

No commit for this step — it's pure verification.

---

## Phase 8 — Routing + shell scaffold

### Task 23: `GoRouter` with `StatefulShellRoute` + auth redirect

**Files:**
- Create: `app/lib/presentation/routing/routes.dart`
- Create: `app/lib/presentation/routing/router.dart`
- Create: `app/lib/presentation/widgets/kpa_shell_scaffold.dart`

Routes are defined imperatively (not via go_router_builder typed routes) for the first iteration — typed routes can come later once the route surface is stable. The redirect logic and `StatefulShellRoute.indexedStack` setup are the load-bearing parts.

Screens themselves don't exist yet — we use placeholder `_PlaceholderScreen(name)` so the router compiles. Phase 9 tasks replace each placeholder with the real screen.

- [ ] **Step 1: Create `routes.dart` (route path constants)**

```dart
/// Centralised route path constants. Keep in sync with the redirect
/// guards in router.dart.
abstract final class Routes {
  static const splash         = '/';
  static const signIn         = '/signin';
  static const feed           = '/feed';
  static const jobDetail      = '/jobs/:id';   // template
  static String jobDetailFor(String id) => '/jobs/$id';
  static const saved          = '/saved';
  static const applications   = '/applications';
  static const profile        = '/profile';
}
```

- [ ] **Step 2: Create `kpa_shell_scaffold.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

/// Bottom-nav scaffold for the four tab destinations. Wired into
/// StatefulShellRoute.indexedStack in router.dart.
class KpaShellScaffold extends StatelessWidget {
  const KpaShellScaffold({super.key, required this.shell});

  final StatefulNavigationShell shell;

  static const _items = [
    NavigationDestination(icon: Icon(Icons.search), label: 'Feed'),
    NavigationDestination(icon: Icon(Icons.bookmark_outline), selectedIcon: Icon(Icons.bookmark), label: 'Saved'),
    NavigationDestination(icon: Icon(Icons.assignment_outlined), selectedIcon: Icon(Icons.assignment), label: 'Applications'),
    NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profile'),
  ];

  void _onTap(int i) {
    // Tapping the active tab pops to its root (iOS convention).
    if (i == shell.currentIndex) {
      shell.goBranch(i, initialLocation: true);
    } else {
      shell.goBranch(i);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(top: false, bottom: false, child: shell),
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        destinations: _items,
        onDestinationSelected: _onTap,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
    );
  }
}
```

- [ ] **Step 3: Create `router.dart`**

```dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/widgets/kpa_shell_scaffold.dart';

import 'routes.dart';

part 'router.g.dart';

/// Placeholder used until the real screens are wired up in Phase 9.
class _Placeholder extends StatelessWidget {
  const _Placeholder(this.name);
  final String name;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(name)),
    body: Center(child: Text('Placeholder: $name')),
  );
}

/// Bridges Riverpod's AuthState changes into GoRouter's `refreshListenable`.
/// GoRouter needs a Listenable; we wrap the provider subscription.
class _AuthChangeNotifier extends ChangeNotifier {
  _AuthChangeNotifier(Ref ref) {
    _sub = ref.listen<AuthState>(
      authStateNotifierProvider,
      (_, __) => notifyListeners(),
    );
  }
  late final ProviderSubscription<AuthState> _sub;

  @override
  void dispose() {
    _sub.close();
    super.dispose();
  }
}

@Riverpod(keepAlive: true)
GoRouter router(Ref ref) {
  final authNotifier = _AuthChangeNotifier(ref);

  return GoRouter(
    initialLocation: Routes.splash,
    refreshListenable: authNotifier,
    redirect: (context, state) {
      final auth = ref.read(authStateNotifierProvider);
      final loc = state.matchedLocation;

      // Splash is reachable only on cold start. Never redirect away from it;
      // its controller pushes either SignedIn (→ /feed) or SignedOut (→ /signin).
      if (loc == Routes.splash) return null;

      // Sign-in routing
      if (auth is SignedOut) {
        return loc == Routes.signIn ? null : Routes.signIn;
      }
      if (auth is SignedIn && loc == Routes.signIn) {
        return Routes.feed;
      }
      return null;
    },
    routes: [
      GoRoute(path: Routes.splash, builder: (_, __) => const _Placeholder('Splash')),
      GoRoute(path: Routes.signIn, builder: (_, __) => const _Placeholder('Sign-in')),

      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => KpaShellScaffold(shell: shell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.feed,
              builder: (_, __) => const _Placeholder('Feed'),
              routes: [
                GoRoute(
                  path: 'jobs/:id',
                  builder: (_, s) => _Placeholder('JobDetail ${s.pathParameters['id']}'),
                ),
              ],
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.saved,
              builder: (_, __) => const _Placeholder('Saved'),
              routes: [
                GoRoute(
                  path: 'jobs/:id',
                  builder: (_, s) => _Placeholder('JobDetail ${s.pathParameters['id']}'),
                ),
              ],
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.applications,
              builder: (_, __) => const _Placeholder('Applications'),
              routes: [
                GoRoute(
                  path: 'jobs/:id',
                  builder: (_, s) => _Placeholder('JobDetail ${s.pathParameters['id']}'),
                ),
              ],
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.profile,
              builder: (_, __) => const _Placeholder('Profile'),
            ),
          ]),
        ],
      ),
    ],
  );
}
```

Note on the `/jobs/:id` placement: it appears under **each** tab branch (not at top-level) so each tab keeps its own stack — tapping a job from Feed pushes onto the Feed stack, tapping from Saved pushes onto the Saved stack. `StatefulShellRoute`'s per-tab persistence depends on this.

- [ ] **Step 4: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Expected: generates `router.g.dart`.

- [ ] **Step 5: Verify analyze**

```bash
flutter analyze lib/presentation/routing/ lib/presentation/widgets/kpa_shell_scaffold.dart
```

Expected: "No issues found!"

- [ ] **Step 6: Commit**

```bash
git add app/lib/presentation/routing/ app/lib/presentation/widgets/kpa_shell_scaffold.dart
git commit -m "$(cat <<'EOF'
feat(app): GoRouter with StatefulShellRoute + auth redirect

Four-tab bottom nav (Feed / Saved / Applications / Profile) via
StatefulShellRoute.indexedStack. /jobs/:id lives under each tab so
per-tab stacks persist. Redirect rule: SignedOut → /signin (from
everywhere except /splash); SignedIn on /signin → /feed.

Screens are placeholder for now; Phase 9 tasks swap them in.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 9 — Screens

Each screen task: presentation/feature/ — providers (wiring + controller), the screen widget(s), one widget smoke test. After each task, swap the corresponding `_Placeholder` in `router.dart` for the real screen.

### Task 24: Splash screen + bootstrap controller

**Files:**
- Create: `app/lib/presentation/splash/bootstrap_controller.dart`
- Create: `app/lib/presentation/splash/splash_screen.dart`
- Modify: `app/lib/presentation/routing/router.dart` (swap splash placeholder)
- Create: `app/test/widget/splash_screen_test.dart`
- Create: `app/test/unit/presentation/splash/bootstrap_controller_test.dart`

- [ ] **Step 1: Create `bootstrap_controller.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/auth_repository_impl.dart';
import 'package:kpa_app/data/auth/token_storage.dart';

part 'bootstrap_controller.g.dart';

/// Runs the silent-refresh sequence on cold start.
///
/// State machine (via AsyncValue<BootstrapOutcome>):
///   loading       → splash spinner
///   data(routeTo) → SplashScreen's listener redirects to /feed or /signin
///   error         → SplashScreen renders KpaErrorView with retry
enum BootstrapOutcome { feed, signIn }

@riverpod
class BootstrapController extends _$BootstrapController {
  @override
  Future<BootstrapOutcome> build() async {
    final storage = ref.read(tokenStorageProvider);
    final token = await storage.readRefreshToken();
    if (token == null) return BootstrapOutcome.signIn;

    final repo = ref.read(authRepositoryProvider);
    try {
      await repo.refreshSession();
      return BootstrapOutcome.feed;
    } on AuthException {
      // 4xx from refresh: not an error, just "needs sign-in".
      return BootstrapOutcome.signIn;
    }
    // NetworkException + ApiException(5xx) bubble — AsyncValue.error → retry UI.
  }

  Future<void> retry() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(build);
  }
}
```

- [ ] **Step 2: Create `splash_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'bootstrap_controller.dart';

class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Listen-and-redirect on success.
    ref.listen<AsyncValue<BootstrapOutcome>>(
      bootstrapControllerProvider,
      (prev, next) {
        next.whenData((outcome) {
          final target = outcome == BootstrapOutcome.feed ? Routes.feed : Routes.signIn;
          context.go(target);
        });
      },
    );

    final value = ref.watch(bootstrapControllerProvider);
    return Scaffold(
      body: AsyncValueWidget<BootstrapOutcome>(
        value: value,
        // Success path navigates via the listener above; render nothing here.
        data: (_) => const SizedBox.shrink(),
        onRetry: () => ref.read(bootstrapControllerProvider.notifier).retry(),
      ),
    );
  }
}
```

- [ ] **Step 3: Swap the placeholder in `router.dart`**

Replace:
```dart
GoRoute(path: Routes.splash, builder: (_, __) => const _Placeholder('Splash')),
```
with:
```dart
GoRoute(path: Routes.splash, builder: (_, __) => const SplashScreen()),
```
and add the import:
```dart
import 'package:kpa_app/presentation/splash/splash_screen.dart';
```

- [ ] **Step 4: Run codegen**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

- [ ] **Step 5: Write tests**

Create `app/test/unit/presentation/splash/bootstrap_controller_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/auth_repository_impl.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/domain/auth/auth_repository.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:kpa_app/presentation/splash/bootstrap_controller.dart';

class _FakeStorage implements TokenStorage {
  String? token;
  _FakeStorage([this.token]);
  @override Future<String?> readRefreshToken() async => token;
  @override Future<void> writeRefreshToken(String t) async => token = t;
  @override Future<void> clear() async => token = null;
}

class _FakeAuthRepo implements AuthRepository {
  _FakeAuthRepo({this.refreshThrows});
  Object? refreshThrows;
  @override Stream<AuthState> watch() => const Stream.empty();
  @override AuthState get current => const SignedOut();
  @override Future<SignedIn> signInWithGoogle() async => throw UnimplementedError();
  @override Future<SignedIn> refreshSession() async {
    if (refreshThrows != null) throw refreshThrows!;
    return const SignedIn(userId: 'u1', email: 'e@e.com');
  }
  @override Future<void> signOut() async {}
}

void main() {
  ProviderContainer container({TokenStorage? storage, AuthRepository? repo}) {
    return ProviderContainer(overrides: [
      tokenStorageProvider.overrideWithValue(storage ?? _FakeStorage()),
      authRepositoryProvider.overrideWithValue(repo ?? _FakeAuthRepo()),
    ]);
  }

  test('no stored token → signIn', () async {
    final c = container();
    final outcome = await c.read(bootstrapControllerProvider.future);
    expect(outcome, BootstrapOutcome.signIn);
  });

  test('stored token + refresh OK → feed', () async {
    final c = container(storage: _FakeStorage('rt'));
    final outcome = await c.read(bootstrapControllerProvider.future);
    expect(outcome, BootstrapOutcome.feed);
  });

  test('stored token + refresh AuthException → signIn (not error)', () async {
    final c = container(
      storage: _FakeStorage('rt'),
      repo: _FakeAuthRepo(refreshThrows: const AuthException(slug: 'invalid_refresh_token')),
    );
    final outcome = await c.read(bootstrapControllerProvider.future);
    expect(outcome, BootstrapOutcome.signIn);
  });

  test('stored token + refresh NetworkException → error', () async {
    final c = container(
      storage: _FakeStorage('rt'),
      repo: _FakeAuthRepo(refreshThrows: const NetworkException()),
    );
    await expectLater(
      c.read(bootstrapControllerProvider.future),
      throwsA(isA<NetworkException>()),
    );
  });
}
```

Create `app/test/widget/splash_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/splash/bootstrap_controller.dart';
import 'package:kpa_app/presentation/splash/splash_screen.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

Widget _wrap(Widget child, {required List<Override> overrides}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(theme: buildTheme(Brightness.light), home: child),
  );
}

void main() {
  testWidgets('renders loading spinner', (tester) async {
    await tester.pumpWidget(_wrap(const SplashScreen(), overrides: [
      bootstrapControllerProvider.overrideWith(() => _StubLoading()),
    ]));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('renders error view with retry on NetworkException', (tester) async {
    await tester.pumpWidget(_wrap(const SplashScreen(), overrides: [
      bootstrapControllerProvider.overrideWith(() => _StubError(const NetworkException())),
    ]));
    await tester.pump();
    expect(find.textContaining("Couldn't reach KPA"), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });
}

class _StubLoading extends BootstrapController {
  @override Future<BootstrapOutcome> build() => Completer<BootstrapOutcome>().future;
}

class _StubError extends BootstrapController {
  _StubError(this.err);
  final Object err;
  @override Future<BootstrapOutcome> build() => Future.error(err);
}
```

Add `import 'dart:async';` to the imports.

- [ ] **Step 6: Run tests**

```bash
flutter test test/unit/presentation/splash/ test/widget/splash_screen_test.dart
```

Expected: 4 controller tests + 2 widget tests = 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/lib/presentation/splash/ app/lib/presentation/routing/router.dart app/test/unit/presentation/splash/ app/test/widget/splash_screen_test.dart
git commit -m "$(cat <<'EOF'
feat(app): splash screen + bootstrap controller

Silent-refresh on cold start. No-token / AuthException → /signin.
Refresh success → /feed. NetworkException → KpaErrorView with retry.
Router placeholder swapped for SplashScreen.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 25: Sign-in screen + signInController

**Files:**
- Create: `app/lib/presentation/auth/sign_in_controller.dart`
- Create: `app/lib/presentation/auth/sign_in_screen.dart`
- Modify: `app/lib/presentation/routing/router.dart` (swap signin placeholder)
- Create: `app/test/widget/sign_in_screen_test.dart`

- [ ] **Step 1: Create `sign_in_controller.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/auth/auth_repository_impl.dart';

part 'sign_in_controller.g.dart';

@riverpod
class SignInController extends _$SignInController {
  @override
  FutureOr<void> build() async {
    // idle
  }

  Future<void> signInWithGoogle() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(authRepositoryProvider).signInWithGoogle();
    });
  }
}
```

- [ ] **Step 2: Create `sign_in_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

import 'sign_in_controller.dart';

class SignInScreen extends ConsumerWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Surface errors via SnackBar.
    ref.listen<AsyncValue<void>>(signInControllerProvider, (prev, next) {
      next.whenOrNull(error: (e, _) {
        final msg = switch (e) {
          AuthException ae when ae.slug == 'google_sign_in_cancelled' => null,
          NetworkException _ => "Couldn't reach KPA. Check your connection.",
          AuthException ae => ae.detail ?? "Sign-in failed. Try again.",
          _ => 'Sign-in failed. Try again.',
        };
        if (msg != null) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
        }
      });
    });

    final state = ref.watch(signInControllerProvider);
    final isLoading = state.isLoading;
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('KPA', style: theme.textTheme.displayMedium),
              const SizedBox(height: KpaSpacing.sm),
              Text(
                'Roles that match you, not the other way around.',
                style: theme.textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: KpaSpacing.xxl),
              FilledButton.icon(
                icon: isLoading
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.login),
                label: Text(isLoading ? 'Signing in…' : 'Continue with Google'),
                onPressed: isLoading ? null : () => ref.read(signInControllerProvider.notifier).signInWithGoogle(),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 3: Swap placeholder in `router.dart`**

```dart
import 'package:kpa_app/presentation/auth/sign_in_screen.dart';
// ...
GoRoute(path: Routes.signIn, builder: (_, __) => const SignInScreen()),
```

- [ ] **Step 4: Run codegen + write widget test**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/widget/sign_in_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/presentation/auth/sign_in_controller.dart';
import 'package:kpa_app/presentation/auth/sign_in_screen.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

Widget _wrap(Widget child, {List<Override> overrides = const []}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(theme: buildTheme(Brightness.light), home: child),
  );
}

void main() {
  testWidgets('renders Continue button + KPA wordmark', (tester) async {
    await tester.pumpWidget(_wrap(const SignInScreen()));
    expect(find.text('KPA'), findsOneWidget);
    expect(find.text('Continue with Google'), findsOneWidget);
  });

  testWidgets('button is disabled while loading', (tester) async {
    await tester.pumpWidget(_wrap(const SignInScreen(), overrides: [
      signInControllerProvider.overrideWith(() => _LoadingStub()),
    ]));
    await tester.pump();
    final btn = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(btn.onPressed, isNull);
    expect(find.text('Signing in…'), findsOneWidget);
  });
}

class _LoadingStub extends SignInController {
  @override Future<void> build() => Completer<void>().future;
}
```

Add `import 'dart:async';`.

- [ ] **Step 5: Run tests + commit**

```bash
flutter test test/widget/sign_in_screen_test.dart
git add app/lib/presentation/auth/sign_in_controller.dart app/lib/presentation/auth/sign_in_controller.g.dart app/lib/presentation/auth/sign_in_screen.dart app/lib/presentation/routing/router.dart app/test/widget/sign_in_screen_test.dart
git commit -m "$(cat <<'EOF'
feat(app): sign-in screen + signInController

Single CTA → AuthRepository.signInWithGoogle. Errors surface as
SnackBar (except cancelled, which is silent). Button shows spinner +
'Signing in…' while loading. Router placeholder swapped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 26: Feed screen + FeedController + FeedItemCard

**Files:**
- Create: `app/lib/presentation/feed/feed_controller.dart`
- Create: `app/lib/presentation/feed/feed_item_card.dart`
- Create: `app/lib/presentation/feed/feed_screen.dart`
- Modify: `app/lib/presentation/routing/router.dart` (swap feed placeholder)
- Create: `app/test/unit/presentation/feed/feed_controller_test.dart`
- Create: `app/test/widget/feed_screen_test.dart`

- [ ] **Step 1: Create `feed_controller.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';

part 'feed_controller.g.dart';
part 'feed_controller.freezed.dart';

@freezed
class FeedState with _$FeedState {
  const factory FeedState({
    required List<FeedItemDto> items,
    required String? cursor,
    required bool hasMore,
    @Default(false) bool isLoadingMore,
  }) = _FeedState;
}

@riverpod
class FeedController extends _$FeedController {
  @override
  Future<FeedState> build() async {
    final page = await ref.read(feedRepositoryProvider).fetchPage();
    return FeedState(
      items: page.items,
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final next = await ref.read(feedRepositoryProvider).fetchPage(cursor: current.cursor);
      state = AsyncValue.data(FeedState(
        items: [...current.items, ...next.items],
        cursor: next.nextCursor,
        hasMore: next.nextCursor != null,
        isLoadingMore: false,
      ));
    } catch (e, st) {
      // Restore the previous data; surface the error via AsyncValue.
      state = AsyncValue.data(current.copyWith(isLoadingMore: false));
      state = AsyncValue.error(e, st);
    }
  }
}
```

- [ ] **Step 2: Create `feed_item_card.dart`** (reused on Saved tab)

```dart
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/kpa_score_badge.dart';

class FeedItemCard extends StatelessWidget {
  const FeedItemCard({
    super.key,
    required this.job,
    required this.employer,
    this.match,
    this.explanation,
    required this.onTap,
    this.showScore = true,
  });

  final JobSummaryDto job;
  final EmployerSummaryDto employer;
  final MatchSummaryDto? match;
  final ExplanationDto? explanation;
  final VoidCallback onTap;
  final bool showScore;

  String _ago(DateTime d) {
    final delta = DateTime.now().toUtc().difference(d.toUtc());
    if (delta.inDays >= 30) return '${(delta.inDays / 30).floor()}mo ago';
    if (delta.inDays >= 1)  return '${delta.inDays}d ago';
    if (delta.inHours >= 1) return '${delta.inHours}h ago';
    return 'just now';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isClosed = job.status != 'open';
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text(employer.name, style: theme.textTheme.labelLarge)),
                  if (isClosed)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.sm, vertical: KpaSpacing.xs),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.outlineVariant,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text('Closed', style: theme.textTheme.labelSmall),
                    )
                  else if (showScore && match != null)
                    KpaScoreBadge(score: match!.totalScore),
                ],
              ),
              const SizedBox(height: KpaSpacing.sm),
              Text(job.title, style: theme.textTheme.titleMedium),
              const SizedBox(height: KpaSpacing.xs),
              Text(
                '${job.location} · ${_ago(job.postedAt)}',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
              if (explanation != null) ...[
                const SizedBox(height: KpaSpacing.md),
                Text(
                  explanation!.fit,
                  style: theme.textTheme.bodyMedium,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (explanation!.caveat != null) ...[
                  const SizedBox(height: KpaSpacing.xs),
                  Text(
                    explanation!.caveat!,
                    style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 3: Create `feed_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

import 'feed_controller.dart';
import 'feed_item_card.dart';

class FeedScreen extends ConsumerStatefulWidget {
  const FeedScreen({super.key});
  @override
  ConsumerState<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends ConsumerState<FeedScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      // Within 200px of the end → loadMore.
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(feedControllerProvider.notifier).loadMore();
      }
    });
  }

  @override
  void dispose() { _scroll.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(feedControllerProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('For you'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(feedControllerProvider.notifier).refresh(),
          ),
        ],
      ),
      body: AsyncValueWidget<FeedState>(
        value: value,
        onRetry: () => ref.read(feedControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => const KpaEmptyState(
          headline: "We're still looking for matches",
          body: 'Upload a resume to help us find you better roles.',
          icon: Icons.search_off,
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () => ref.read(feedControllerProvider.notifier).refresh(),
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(KpaSpacing.lg),
            itemCount: s.items.length + 1,   // +1 for tail
            separatorBuilder: (_, __) => const SizedBox(height: KpaSpacing.md),
            itemBuilder: (context, i) {
              if (i == s.items.length) {
                if (s.isLoadingMore) return const Padding(padding: EdgeInsets.all(KpaSpacing.lg), child: KpaLoadingView());
                if (!s.hasMore) return Padding(
                  padding: const EdgeInsets.all(KpaSpacing.lg),
                  child: Center(child: Text(
                    "You're all caught up",
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  )),
                );
                return const SizedBox.shrink();
              }
              final item = s.items[i];
              return FeedItemCard(
                job: item.job,
                employer: item.employer,
                match: item.match,
                explanation: item.match.explanation,
                onTap: () => context.go('${Routes.feed}/jobs/${item.job.id}'),
              );
            },
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Swap placeholder in `router.dart`**

```dart
import 'package:kpa_app/presentation/feed/feed_screen.dart';
// ...
GoRoute(
  path: Routes.feed,
  builder: (_, __) => const FeedScreen(),
  routes: [
    GoRoute(
      path: 'jobs/:id',
      // JobDetail placeholder still — replaced in Task 27.
      builder: (_, s) => _Placeholder('JobDetail ${s.pathParameters['id']}'),
    ),
  ],
),
```

- [ ] **Step 5: Run codegen + write tests**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/unit/presentation/feed/feed_controller_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';
import 'package:kpa_app/presentation/feed/feed_controller.dart';

class _FakeFeedRepo implements FeedRepository {
  _FakeFeedRepo(this.pages);
  final List<FeedPageDto> pages;   // returned in order
  int call = 0;
  @override Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async {
    return pages[call++];
  }
}

FeedItemDto _item(String jobId) => FeedItemDto(
  match: MatchSummaryDto(id: 'm-$jobId', totalScore: 0.8, scoreComponents: const {}),
  job: JobSummaryDto(id: jobId, title: 'T-$jobId', location: 'BLR', status: 'open',
                     postedAt: DateTime.parse('2026-05-18T00:00:00Z')),
  employer: const EmployerSummaryDto(id: 'e1', name: 'Acme'),
);

void main() {
  test('initial build returns first page; hasMore tracks next_cursor', () async {
    final c = ProviderContainer(overrides: [
      feedRepositoryProvider.overrideWithValue(_FakeFeedRepo([
        FeedPageDto(items: [_item('j1'), _item('j2')], nextCursor: 'c1'),
      ])),
    ]);
    final s = await c.read(feedControllerProvider.future);
    expect(s.items, hasLength(2));
    expect(s.hasMore, isTrue);
    expect(s.cursor, 'c1');
  });

  test('loadMore appends items + updates cursor + flips hasMore', () async {
    final c = ProviderContainer(overrides: [
      feedRepositoryProvider.overrideWithValue(_FakeFeedRepo([
        FeedPageDto(items: [_item('j1')], nextCursor: 'c1'),
        FeedPageDto(items: [_item('j2'), _item('j3')], nextCursor: null),
      ])),
    ]);
    await c.read(feedControllerProvider.future);
    await c.read(feedControllerProvider.notifier).loadMore();
    final s = c.read(feedControllerProvider).value!;
    expect(s.items, hasLength(3));
    expect(s.hasMore, isFalse);
  });

  test('loadMore is a no-op when hasMore=false', () async {
    final c = ProviderContainer(overrides: [
      feedRepositoryProvider.overrideWithValue(_FakeFeedRepo([
        FeedPageDto(items: [_item('j1')], nextCursor: null),
      ])),
    ]);
    await c.read(feedControllerProvider.future);
    await c.read(feedControllerProvider.notifier).loadMore();
    // No second fetch happened — would have thrown RangeError otherwise.
    expect(c.read(feedControllerProvider).value!.items, hasLength(1));
  });
}
```

Create `app/test/widget/feed_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';
import 'package:kpa_app/presentation/feed/feed_screen.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

class _FakeFeedRepo implements FeedRepository {
  _FakeFeedRepo(this.page);
  final FeedPageDto page;
  @override Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async => page;
}

Widget _wrap(Widget child, {required FeedRepository repo}) {
  return ProviderScope(
    overrides: [feedRepositoryProvider.overrideWithValue(repo)],
    child: MaterialApp(theme: buildTheme(Brightness.light), home: child),
  );
}

void main() {
  testWidgets('renders empty state when no items', (tester) async {
    await tester.pumpWidget(_wrap(const FeedScreen(),
      repo: _FakeFeedRepo(const FeedPageDto(items: [], nextCursor: null))));
    await tester.pumpAndSettle();
    expect(find.textContaining("We're still looking"), findsOneWidget);
  });

  testWidgets('renders feed item cards', (tester) async {
    final item = FeedItemDto(
      match: MatchSummaryDto(id: 'm1', totalScore: 0.8, scoreComponents: const {}),
      job: JobSummaryDto(id: 'j1', title: 'Engineer', location: 'BLR', status: 'open',
                         postedAt: DateTime.parse('2026-05-18T00:00:00Z')),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
    );
    await tester.pumpWidget(_wrap(const FeedScreen(),
      repo: _FakeFeedRepo(FeedPageDto(items: [item], nextCursor: null))));
    await tester.pumpAndSettle();
    expect(find.text('Engineer'), findsOneWidget);
    expect(find.text('Acme Co'), findsOneWidget);
    expect(find.text("You're all caught up"), findsOneWidget);
  });
}
```

- [ ] **Step 6: Run tests + commit**

```bash
flutter test test/unit/presentation/feed/ test/widget/feed_screen_test.dart
git add app/lib/presentation/feed/ app/lib/presentation/routing/router.dart app/test/unit/presentation/feed/ app/test/widget/feed_screen_test.dart
git commit -m "$(cat <<'EOF'
feat(app): feed screen + FeedController + FeedItemCard

Cursor-paginated AsyncNotifier; scroll-near-end triggers loadMore;
pull-to-refresh + refresh icon both call refresh(). FeedItemCard
reused on Saved tab (hides score for closed jobs via showScore flag).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 27: Job detail — controllers + ActionBar + screen

**Files:**
- Create: `app/lib/presentation/job_detail/job_detail_controller.dart`
- Create: `app/lib/presentation/job_detail/apply_to_job_controller.dart`
- Create: `app/lib/presentation/job_detail/withdraw_application_controller.dart`
- Create: `app/lib/presentation/job_detail/save_job_controller.dart`
- Create: `app/lib/presentation/job_detail/unsave_job_controller.dart`
- Create: `app/lib/presentation/job_detail/action_bar.dart`
- Create: `app/lib/presentation/job_detail/job_detail_screen.dart`
- Modify: `app/lib/presentation/routing/router.dart` (swap 3 placeholders — Feed/Saved/Applications tabs all open job detail)
- Create: `app/test/widget/job_detail_screen_test.dart`

- [ ] **Step 1: Create the five controllers**

`app/lib/presentation/job_detail/job_detail_controller.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';

part 'job_detail_controller.g.dart';

@riverpod
class JobDetailController extends _$JobDetailController {
  @override
  Future<JobDetailDto> build(String jobId) async {
    return ref.read(jobsRepositoryProvider).fetchById(jobId);
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
```

`app/lib/presentation/job_detail/apply_to_job_controller.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:kpa_app/presentation/applications/applications_controller.dart';
import 'job_detail_controller.dart';

part 'apply_to_job_controller.g.dart';

@riverpod
class ApplyToJobController extends _$ApplyToJobController {
  @override
  FutureOr<ApplicationDto?> build(String jobId) => null;

  Future<void> submit({String source = 'feed'}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final app = await ref.read(jobsRepositoryProvider).applyTo(jobId, source: source);
      ref.invalidate(applicationsControllerProvider);
      ref.invalidate(jobDetailControllerProvider(jobId));
      return app;
    });
  }
}
```

`app/lib/presentation/job_detail/withdraw_application_controller.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/jobs/applications_repository_impl.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/presentation/applications/applications_controller.dart';
import 'job_detail_controller.dart';

part 'withdraw_application_controller.g.dart';

@riverpod
class WithdrawApplicationController extends _$WithdrawApplicationController {
  @override
  FutureOr<ApplicationDto?> build(String applicationId) => null;

  Future<void> submit({required String jobId}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final app = await ref.read(applicationsRepositoryProvider).withdraw(applicationId);
      ref.invalidate(applicationsControllerProvider);
      ref.invalidate(jobDetailControllerProvider(jobId));
      return app;
    });
  }
}
```

`app/lib/presentation/job_detail/save_job_controller.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:kpa_app/presentation/saved/saved_controller.dart';
import 'job_detail_controller.dart';

part 'save_job_controller.g.dart';

@riverpod
class SaveJobController extends _$SaveJobController {
  @override
  FutureOr<SavedJobDto?> build(String jobId) => null;

  Future<void> submit() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final sv = await ref.read(jobsRepositoryProvider).save(jobId);
      ref.invalidate(savedControllerProvider);
      ref.invalidate(jobDetailControllerProvider(jobId));
      return sv;
    });
  }
}
```

`app/lib/presentation/job_detail/unsave_job_controller.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:kpa_app/presentation/saved/saved_controller.dart';
import 'job_detail_controller.dart';

part 'unsave_job_controller.g.dart';

@riverpod
class UnsaveJobController extends _$UnsaveJobController {
  @override
  FutureOr<void> build(String jobId) async {}

  Future<void> submit() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(jobsRepositoryProvider).unsave(jobId);
      ref.invalidate(savedControllerProvider);
      ref.invalidate(jobDetailControllerProvider(jobId));
    });
  }
}
```

Note: `applicationsControllerProvider` and `savedControllerProvider` referenced above are created in Tasks 28-29. If you're executing in order, the imports won't resolve until then. Comment them out (and the `ref.invalidate` lines) temporarily; un-comment in Tasks 28 / 29.

- [ ] **Step 2: Create `action_bar.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

import 'apply_to_job_controller.dart';
import 'save_job_controller.dart';
import 'unsave_job_controller.dart';
import 'withdraw_application_controller.dart';

class ActionBar extends ConsumerWidget {
  const ActionBar({super.key, required this.detail});
  final JobDetailDto detail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = detail.application;
    final saved = detail.savedJob;
    final jobId = detail.job.id;

    final applyState = ref.watch(applyToJobControllerProvider(jobId));
    final withdrawState = app == null
        ? const AsyncValue<ApplicationDto?>.data(null)
        : ref.watch(withdrawApplicationControllerProvider(app.id));
    final saveState = ref.watch(saveJobControllerProvider(jobId));
    final unsaveState = ref.watch(unsaveJobControllerProvider(jobId));

    final isBusy = applyState.isLoading || withdrawState.isLoading
                 || saveState.isLoading || unsaveState.isLoading;

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(KpaSpacing.lg),
        child: Row(
          children: [
            Expanded(child: _applyOrWithdraw(context, ref, app, jobId, isBusy)),
            const SizedBox(width: KpaSpacing.md),
            _saveHeart(context, ref, saved, jobId, isBusy),
          ],
        ),
      ),
    );
  }

  Widget _applyOrWithdraw(BuildContext ctx, WidgetRef ref, ApplicationDto? app, String jobId, bool isBusy) {
    if (app == null || app.status == 'withdrawn') {
      return FilledButton(
        onPressed: isBusy ? null : () => ref.read(applyToJobControllerProvider(jobId).notifier).submit(),
        child: const Text('Apply'),
      );
    }
    // status == 'applied'
    return OutlinedButton(
      onPressed: isBusy ? null : () => _confirmWithdraw(ctx, ref, app, jobId),
      child: const Text('Withdraw'),
    );
  }

  Widget _saveHeart(BuildContext ctx, WidgetRef ref, SavedJobDto? saved, String jobId, bool isBusy) {
    final filled = saved != null;
    return IconButton.filledTonal(
      onPressed: isBusy ? null : () {
        if (filled) {
          ref.read(unsaveJobControllerProvider(jobId).notifier).submit();
        } else {
          ref.read(saveJobControllerProvider(jobId).notifier).submit();
        }
      },
      icon: Icon(filled ? Icons.bookmark : Icons.bookmark_outline),
    );
  }

  Future<void> _confirmWithdraw(BuildContext ctx, WidgetRef ref, ApplicationDto app, String jobId) async {
    final ok = await showDialog<bool>(
      context: ctx,
      builder: (c) => AlertDialog(
        title: const Text('Withdraw application?'),
        content: const Text("You can re-apply later if you change your mind."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Withdraw')),
        ],
      ),
    );
    if (ok == true) {
      await ref.read(withdrawApplicationControllerProvider(app.id).notifier).submit(jobId: jobId);
    }
  }
}
```

- [ ] **Step 3: Create `job_detail_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_score_badge.dart';

import 'action_bar.dart';
import 'apply_to_job_controller.dart';
import 'job_detail_controller.dart';
import 'save_job_controller.dart';
import 'unsave_job_controller.dart';
import 'withdraw_application_controller.dart';

class JobDetailScreen extends ConsumerWidget {
  const JobDetailScreen({super.key, required this.jobId});
  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Surface mutation errors as snackbars.
    void listenErr(AsyncValue v) => v.whenOrNull(error: (e, _) {
      final msg = e is ApiException ? (e.detail ?? 'Action failed') : "Couldn't reach KPA.";
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    });
    ref.listen<AsyncValue>(applyToJobControllerProvider(jobId), (_, n) => listenErr(n));
    ref.listen<AsyncValue>(saveJobControllerProvider(jobId), (_, n) => listenErr(n));
    ref.listen<AsyncValue>(unsaveJobControllerProvider(jobId), (_, n) => listenErr(n));

    final value = ref.watch(jobDetailControllerProvider(jobId));
    return Scaffold(
      appBar: AppBar(leading: BackButton(onPressed: () => context.pop())),
      body: AsyncValueWidget(
        value: value,
        onRetry: () => ref.read(jobDetailControllerProvider(jobId).notifier).refresh(),
        // 404 → KpaErrorView gets ApiException(statusCode=404) — render
        // the empty-state copy explicitly via an error builder override.
        error: (e, s) {
          if (e is ApiException && e.statusCode == 404) {
            return KpaEmptyState(
              headline: 'This job is no longer available',
              body: 'It may have been closed or removed.',
              primaryAction: FilledButton(
                onPressed: () => context.go('/feed'),
                child: const Text('Back to feed'),
              ),
            );
          }
          return null;   // fall through to default KpaErrorView
        } as Widget Function(Object, StackTrace),
        data: (d) => Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(KpaSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(d.employer.name, style: Theme.of(context).textTheme.labelLarge),
                    const SizedBox(height: KpaSpacing.xs),
                    Text(d.job.title, style: Theme.of(context).textTheme.headlineMedium),
                    const SizedBox(height: KpaSpacing.xs),
                    Text(d.job.location, style: Theme.of(context).textTheme.bodyMedium),
                    if (d.match != null) ...[
                      const SizedBox(height: KpaSpacing.lg),
                      _MatchCard(match: d.match!),
                    ],
                    if (d.job.description != null) ...[
                      const SizedBox(height: KpaSpacing.xl),
                      Text(d.job.description!, style: Theme.of(context).textTheme.bodyLarge),
                    ],
                  ],
                ),
              ),
            ),
            ActionBar(detail: d),
          ],
        ),
      ),
    );
  }
}

class _MatchCard extends StatelessWidget {
  const _MatchCard({required this.match});
  final dynamic match;   // MatchSummaryDto — kept dynamic to avoid the import roundtrip

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final exp = match.explanation;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(KpaSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('Why this match', style: theme.textTheme.titleMedium),
                const Spacer(),
                KpaScoreBadge(score: match.totalScore as double),
              ],
            ),
            if (exp != null) ...[
              const SizedBox(height: KpaSpacing.md),
              Text(exp.fit as String, style: theme.textTheme.bodyMedium),
              if (exp.caveat != null) ...[
                const SizedBox(height: KpaSpacing.sm),
                Text(exp.caveat as String, style: theme.textTheme.bodySmall),
              ],
              const SizedBox(height: KpaSpacing.sm),
              Text(exp.generator as String, style: theme.textTheme.labelSmall),
            ],
          ],
        ),
      ),
    );
  }
}
```

Fix the dangling `as Widget Function(Object, StackTrace)` cast — the cleaner approach is a helper inside `AsyncValueWidget` for a nullable error builder. For now, change the screen's error branch to:

```dart
error: (e, s) {
  if (e is ApiException && e.statusCode == 404) {
    return KpaEmptyState(
      headline: 'This job is no longer available',
      body: 'It may have been closed or removed.',
      primaryAction: FilledButton(
        onPressed: () => context.go('/feed'),
        child: const Text('Back to feed'),
      ),
    );
  }
  // Default error rendering — match what AsyncValueWidget would do.
  return Center(child: Text(e.toString()));
},
```

- [ ] **Step 4: Swap 3 placeholders in `router.dart`** (Feed/Saved/Applications tabs all open Job Detail)

For each of the three tab branches, replace:
```dart
GoRoute(
  path: 'jobs/:id',
  builder: (_, s) => _Placeholder('JobDetail ${s.pathParameters['id']}'),
),
```
with:
```dart
GoRoute(
  path: 'jobs/:id',
  builder: (_, s) => JobDetailScreen(jobId: s.pathParameters['id']!),
),
```

And add the import:
```dart
import 'package:kpa_app/presentation/job_detail/job_detail_screen.dart';
```

- [ ] **Step 5: Run codegen + write widget test**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/widget/job_detail_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:kpa_app/domain/jobs/jobs_repository.dart';
import 'package:kpa_app/presentation/job_detail/job_detail_screen.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

class _FakeJobsRepo implements JobsRepository {
  _FakeJobsRepo(this.detail);
  final JobDetailDto detail;
  @override Future<JobDetailDto> fetchById(String id) async => detail;
  @override Future<ApplicationDto> applyTo(String id, {String source = 'feed'}) async =>
      ApplicationDto(id: 'a1', applicantId: 'ap1', jobId: id, status: 'applied',
          source: source, createdAt: DateTime.now());
  @override Future<SavedJobDto> save(String id) async =>
      SavedJobDto(id: 's1', applicantId: 'ap1', jobId: id, createdAt: DateTime.now());
  @override Future<void> unsave(String id) async {}
}

JobDetailDto _detail({ApplicationDto? app, SavedJobDto? saved}) => JobDetailDto(
  job: JobSummaryDto(id: 'j1', title: 'Senior Engineer', location: 'BLR',
                     status: 'open', postedAt: DateTime.parse('2026-05-18T00:00:00Z')),
  employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
  match: MatchSummaryDto(id: 'm1', totalScore: 0.82, scoreComponents: const {},
                         explanation: const ExplanationDto(fit: 'great fit', generator: 'templated', generatorVersion: '1')),
  application: app, savedJob: saved,
);

Widget _wrap(Widget child, {required JobsRepository repo}) {
  return ProviderScope(
    overrides: [jobsRepositoryProvider.overrideWithValue(repo)],
    child: MaterialApp(theme: buildTheme(Brightness.light), home: child),
  );
}

void main() {
  testWidgets('shows Apply button when no application', (tester) async {
    await tester.pumpWidget(_wrap(const JobDetailScreen(jobId: 'j1'),
      repo: _FakeJobsRepo(_detail())));
    await tester.pumpAndSettle();
    expect(find.text('Apply'), findsOneWidget);
    expect(find.text('Withdraw'), findsNothing);
  });

  testWidgets('shows Withdraw when applied', (tester) async {
    final app = ApplicationDto(id: 'a1', applicantId: 'ap1', jobId: 'j1',
        status: 'applied', source: 'feed', createdAt: DateTime.now());
    await tester.pumpWidget(_wrap(const JobDetailScreen(jobId: 'j1'),
      repo: _FakeJobsRepo(_detail(app: app))));
    await tester.pumpAndSettle();
    expect(find.text('Withdraw'), findsOneWidget);
  });

  testWidgets('shows filled heart when saved', (tester) async {
    final s = SavedJobDto(id: 's1', applicantId: 'ap1', jobId: 'j1', createdAt: DateTime.now());
    await tester.pumpWidget(_wrap(const JobDetailScreen(jobId: 'j1'),
      repo: _FakeJobsRepo(_detail(saved: s))));
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.bookmark), findsOneWidget);
  });

  testWidgets('renders explanation card', (tester) async {
    await tester.pumpWidget(_wrap(const JobDetailScreen(jobId: 'j1'),
      repo: _FakeJobsRepo(_detail())));
    await tester.pumpAndSettle();
    expect(find.text('Why this match'), findsOneWidget);
    expect(find.text('great fit'), findsOneWidget);
  });
}
```

- [ ] **Step 6: Run tests + commit**

```bash
flutter test test/widget/job_detail_screen_test.dart
git add app/lib/presentation/job_detail/ app/lib/presentation/routing/router.dart app/test/widget/job_detail_screen_test.dart
git commit -m "$(cat <<'EOF'
feat(app): job detail screen + 5 mutation controllers + ActionBar

JobDetailController (read) + ApplyToJobController, WithdrawApplicationController,
SaveJobController, UnsaveJobController (mutations). Each mutation invalidates
the relevant list controller + the parent JobDetail. ActionBar: Apply/Withdraw
primary + Save/Saved heart; withdraw goes through a confirmation dialog.
Errors surface as snackbars. Router placeholders swapped under all three
tab stacks (Feed/Saved/Applications) so per-tab navigation persists.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 28: Applications tab + controller

**Files:**
- Create: `app/lib/presentation/applications/applications_controller.dart`
- Create: `app/lib/presentation/applications/applications_screen.dart`
- Modify: `app/lib/presentation/routing/router.dart`
- Create: `app/test/widget/applications_screen_test.dart`

- [ ] **Step 1: Create `applications_controller.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/jobs/applications_repository_impl.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';

part 'applications_controller.g.dart';
part 'applications_controller.freezed.dart';

@freezed
class ApplicationsState with _$ApplicationsState {
  const factory ApplicationsState({
    required List<ApplicationListItemDto> items,
    required String? cursor,
    required bool hasMore,
    @Default(false) bool isLoadingMore,
  }) = _ApplicationsState;
}

@riverpod
class ApplicationsController extends _$ApplicationsController {
  @override
  Future<ApplicationsState> build() async {
    final page = await ref.read(applicationsRepositoryProvider).fetchPage();
    return ApplicationsState(items: page.items, cursor: page.nextCursor, hasMore: page.nextCursor != null);
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final next = await ref.read(applicationsRepositoryProvider).fetchPage(cursor: current.cursor);
      state = AsyncValue.data(ApplicationsState(
        items: [...current.items, ...next.items],
        cursor: next.nextCursor, hasMore: next.nextCursor != null,
        isLoadingMore: false,
      ));
    } catch (e, st) {
      state = AsyncValue.data(current.copyWith(isLoadingMore: false));
      state = AsyncValue.error(e, st);
    }
  }
}
```

(Now go back to Task 27's withdraw/apply controllers and un-comment the `ref.invalidate(applicationsControllerProvider)` lines — the import now resolves.)

- [ ] **Step 2: Create `applications_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

import 'applications_controller.dart';

class ApplicationsScreen extends ConsumerStatefulWidget {
  const ApplicationsScreen({super.key});
  @override
  ConsumerState<ApplicationsScreen> createState() => _ApplicationsScreenState();
}

class _ApplicationsScreenState extends ConsumerState<ApplicationsScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(applicationsControllerProvider.notifier).loadMore();
      }
    });
  }

  @override
  void dispose() { _scroll.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(applicationsControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Applications')),
      body: AsyncValueWidget(
        value: value,
        onRetry: () => ref.read(applicationsControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => KpaEmptyState(
          headline: 'No applications yet',
          body: "Browse the feed and apply to roles you like.",
          icon: Icons.assignment_outlined,
          primaryAction: FilledButton(
            onPressed: () => context.go(Routes.feed),
            child: const Text('Browse the feed'),
          ),
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () => ref.read(applicationsControllerProvider.notifier).refresh(),
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(KpaSpacing.lg),
            itemCount: s.items.length + 1,
            separatorBuilder: (_, __) => const SizedBox(height: KpaSpacing.md),
            itemBuilder: (context, i) {
              if (i == s.items.length) {
                if (s.isLoadingMore) return const Padding(padding: EdgeInsets.all(KpaSpacing.lg), child: KpaLoadingView());
                return const SizedBox.shrink();
              }
              final item = s.items[i];
              final isWithdrawn = item.application.status == 'withdrawn';
              return Card(
                child: InkWell(
                  onTap: () => context.go('${Routes.applications}/jobs/${item.job.id}'),
                  child: Padding(
                    padding: const EdgeInsets.all(KpaSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(child: Text(item.employer.name, style: Theme.of(context).textTheme.labelLarge)),
                            _StatusPill(status: item.application.status),
                          ],
                        ),
                        const SizedBox(height: KpaSpacing.sm),
                        Text(item.job.title, style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: KpaSpacing.xs),
                        Text(
                          isWithdrawn
                              ? 'Withdrawn ${DateFormat.yMMMMd().format(item.application.withdrawnAt!)}'
                              : 'Applied ${DateFormat.yMMMMd().format(item.application.createdAt)}',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status});
  final String status;
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context);
    final (label, bg, fg) = status == 'applied'
        ? ('Applied', c.colorScheme.primaryContainer, c.colorScheme.onPrimaryContainer)
        : ('Withdrawn', c.colorScheme.surfaceContainerHighest, c.colorScheme.onSurfaceVariant);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.sm, vertical: KpaSpacing.xs),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text(label, style: c.textTheme.labelSmall?.copyWith(color: fg)),
    );
  }
}
```

- [ ] **Step 3: Swap placeholder in `router.dart`**

```dart
import 'package:kpa_app/presentation/applications/applications_screen.dart';
// ...
GoRoute(
  path: Routes.applications,
  builder: (_, __) => const ApplicationsScreen(),
  routes: [
    GoRoute(
      path: 'jobs/:id',
      builder: (_, s) => JobDetailScreen(jobId: s.pathParameters['id']!),
    ),
  ],
),
```

- [ ] **Step 4: Run codegen + write widget test**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/widget/applications_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/jobs/applications_repository_impl.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/domain/jobs/applications_repository.dart';
import 'package:kpa_app/presentation/applications/applications_screen.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

class _FakeRepo implements ApplicationsRepository {
  _FakeRepo(this.page);
  final ApplicationsPageDto page;
  @override Future<ApplicationsPageDto> fetchPage({String? cursor, int limit = 20}) async => page;
  @override Future<ApplicationDto> withdraw(String id) async => throw UnimplementedError();
}

Widget _wrap(Widget child, {required ApplicationsRepository repo}) => ProviderScope(
  overrides: [applicationsRepositoryProvider.overrideWithValue(repo)],
  child: MaterialApp(theme: buildTheme(Brightness.light), home: child),
);

void main() {
  testWidgets('empty state', (tester) async {
    await tester.pumpWidget(_wrap(const ApplicationsScreen(),
      repo: _FakeRepo(const ApplicationsPageDto(items: [], nextCursor: null))));
    await tester.pumpAndSettle();
    expect(find.text('No applications yet'), findsOneWidget);
  });

  testWidgets('renders applied + withdrawn rows', (tester) async {
    final items = [
      ApplicationListItemDto(
        application: ApplicationDto(id: 'a1', applicantId: 'p', jobId: 'j1',
            status: 'applied', source: 'feed', createdAt: DateTime(2026, 5, 1)),
        job: JobSummaryDto(id: 'j1', title: 'Eng', location: 'BLR', status: 'open',
            postedAt: DateTime(2026, 4, 1)),
        employer: const EmployerSummaryDto(id: 'e1', name: 'Acme'),
      ),
      ApplicationListItemDto(
        application: ApplicationDto(id: 'a2', applicantId: 'p', jobId: 'j2',
            status: 'withdrawn', source: 'feed', createdAt: DateTime(2026, 4, 20),
            withdrawnAt: DateTime(2026, 5, 5)),
        job: JobSummaryDto(id: 'j2', title: 'Designer', location: 'BLR', status: 'open',
            postedAt: DateTime(2026, 4, 1)),
        employer: const EmployerSummaryDto(id: 'e2', name: 'Beta'),
      ),
    ];
    await tester.pumpWidget(_wrap(const ApplicationsScreen(),
      repo: _FakeRepo(ApplicationsPageDto(items: items, nextCursor: null))));
    await tester.pumpAndSettle();
    expect(find.text('Applied'), findsOneWidget);
    expect(find.text('Withdrawn'), findsOneWidget);
    expect(find.text('Eng'), findsOneWidget);
    expect(find.text('Designer'), findsOneWidget);
  });
}
```

- [ ] **Step 5: Run tests + commit**

```bash
flutter test test/widget/applications_screen_test.dart
git add app/lib/presentation/applications/ app/lib/presentation/routing/router.dart app/lib/presentation/job_detail/ app/test/widget/applications_screen_test.dart
git commit -m "$(cat <<'EOF'
feat(app): applications tab + controller

Cursor-paginated list of the applicant's applications (applied +
withdrawn history visible). Status pill, date row, tap pushes
JobDetail onto the Applications tab's stack. Empty CTA navigates
to /feed.

Also un-comments the ref.invalidate(applicationsControllerProvider)
lines in apply / withdraw controllers (Task 27) now that the
import resolves.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 29: Saved tab + controller

**Files:**
- Create: `app/lib/presentation/saved/saved_controller.dart`
- Create: `app/lib/presentation/saved/saved_screen.dart`
- Modify: `app/lib/presentation/routing/router.dart`
- Create: `app/test/widget/saved_screen_test.dart`

- [ ] **Step 1: Create `saved_controller.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/saved_jobs_repository_impl.dart';

part 'saved_controller.g.dart';
part 'saved_controller.freezed.dart';

@freezed
class SavedState with _$SavedState {
  const factory SavedState({
    required List<SavedJobListItemDto> items,
    required String? cursor,
    required bool hasMore,
    @Default(false) bool isLoadingMore,
  }) = _SavedState;
}

@riverpod
class SavedController extends _$SavedController {
  @override
  Future<SavedState> build() async {
    final page = await ref.read(savedJobsRepositoryProvider).fetchPage();
    return SavedState(items: page.items, cursor: page.nextCursor, hasMore: page.nextCursor != null);
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final next = await ref.read(savedJobsRepositoryProvider).fetchPage(cursor: current.cursor);
      state = AsyncValue.data(SavedState(
        items: [...current.items, ...next.items],
        cursor: next.nextCursor, hasMore: next.nextCursor != null,
        isLoadingMore: false,
      ));
    } catch (e, st) {
      state = AsyncValue.data(current.copyWith(isLoadingMore: false));
      state = AsyncValue.error(e, st);
    }
  }
}
```

(Now un-comment the `ref.invalidate(savedControllerProvider)` lines in save / unsave controllers from Task 27.)

- [ ] **Step 2: Create `saved_screen.dart`** (reuses `FeedItemCard`)

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/presentation/feed/feed_item_card.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

import 'saved_controller.dart';

class SavedScreen extends ConsumerStatefulWidget {
  const SavedScreen({super.key});
  @override
  ConsumerState<SavedScreen> createState() => _SavedScreenState();
}

class _SavedScreenState extends ConsumerState<SavedScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(savedControllerProvider.notifier).loadMore();
      }
    });
  }

  @override
  void dispose() { _scroll.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(savedControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Saved')),
      body: AsyncValueWidget(
        value: value,
        onRetry: () => ref.read(savedControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => const KpaEmptyState(
          headline: 'Nothing saved yet',
          body: 'Tap the heart on any job to save it for later.',
          icon: Icons.bookmark_outline,
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () => ref.read(savedControllerProvider.notifier).refresh(),
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(KpaSpacing.lg),
            itemCount: s.items.length + 1,
            separatorBuilder: (_, __) => const SizedBox(height: KpaSpacing.md),
            itemBuilder: (context, i) {
              if (i == s.items.length) {
                if (s.isLoadingMore) return const Padding(padding: EdgeInsets.all(KpaSpacing.lg), child: KpaLoadingView());
                return const SizedBox.shrink();
              }
              final item = s.items[i];
              return FeedItemCard(
                job: item.job,
                employer: item.employer,
                match: item.match,
                explanation: item.match?.explanation,
                showScore: item.job.status == 'open',
                onTap: () => context.go('${Routes.saved}/jobs/${item.job.id}'),
              );
            },
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 3: Swap placeholder in `router.dart`**

```dart
import 'package:kpa_app/presentation/saved/saved_screen.dart';
// ...
GoRoute(
  path: Routes.saved,
  builder: (_, __) => const SavedScreen(),
  routes: [
    GoRoute(
      path: 'jobs/:id',
      builder: (_, s) => JobDetailScreen(jobId: s.pathParameters['id']!),
    ),
  ],
),
```

- [ ] **Step 4: Run codegen + write widget test**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/widget/saved_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:kpa_app/domain/jobs/saved_jobs_repository.dart';
import 'package:kpa_app/presentation/saved/saved_screen.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

class _FakeRepo implements SavedJobsRepository {
  _FakeRepo(this.page);
  final SavedJobsPageDto page;
  @override Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async => page;
}

Widget _wrap(Widget child, {required SavedJobsRepository repo}) => ProviderScope(
  overrides: [savedJobsRepositoryProvider.overrideWithValue(repo)],
  child: MaterialApp(theme: buildTheme(Brightness.light), home: child),
);

void main() {
  testWidgets('empty state', (tester) async {
    await tester.pumpWidget(_wrap(const SavedScreen(),
      repo: _FakeRepo(const SavedJobsPageDto(items: [], nextCursor: null))));
    await tester.pumpAndSettle();
    expect(find.text('Nothing saved yet'), findsOneWidget);
  });

  testWidgets('renders open + closed jobs differently', (tester) async {
    final items = [
      SavedJobListItemDto(
        saved: SavedJobDto(id: 's1', applicantId: 'p', jobId: 'j1', createdAt: DateTime(2026,5,1)),
        job: JobSummaryDto(id: 'j1', title: 'Open Eng', location: 'BLR', status: 'open',
                            postedAt: DateTime(2026,5,1)),
        employer: const EmployerSummaryDto(id: 'e1', name: 'Acme'),
        match: MatchSummaryDto(id: 'm1', totalScore: 0.8, scoreComponents: const {}),
      ),
      SavedJobListItemDto(
        saved: SavedJobDto(id: 's2', applicantId: 'p', jobId: 'j2', createdAt: DateTime(2026,5,2)),
        job: JobSummaryDto(id: 'j2', title: 'Closed Eng', location: 'BLR', status: 'closed',
                            postedAt: DateTime(2026,5,1)),
        employer: const EmployerSummaryDto(id: 'e2', name: 'Beta'),
      ),
    ];
    await tester.pumpWidget(_wrap(const SavedScreen(),
      repo: _FakeRepo(SavedJobsPageDto(items: items, nextCursor: null))));
    await tester.pumpAndSettle();
    expect(find.text('Open Eng'), findsOneWidget);
    expect(find.text('Closed Eng'), findsOneWidget);
    expect(find.text('Closed'), findsOneWidget); // status pill
  });
}
```

- [ ] **Step 5: Run tests + commit**

```bash
flutter test test/widget/saved_screen_test.dart
git add app/lib/presentation/saved/ app/lib/presentation/routing/router.dart app/lib/presentation/job_detail/ app/test/widget/saved_screen_test.dart
git commit -m "$(cat <<'EOF'
feat(app): saved tab + controller

Cursor-paginated list reusing FeedItemCard with showScore disabled
for closed jobs (Closed pill replaces the score badge). Save/unsave
controllers now invalidate this provider on success (un-commented
lines in Task 27 controllers).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 30: Profile screen + me/signOut controllers

**Files:**
- Create: `app/lib/presentation/profile/me_controller.dart`
- Create: `app/lib/presentation/profile/sign_out_controller.dart`
- Create: `app/lib/presentation/profile/profile_screen.dart`
- Modify: `app/lib/presentation/routing/router.dart`
- Create: `app/test/widget/profile_screen_test.dart`

- [ ] **Step 1: Create `me_controller.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';

part 'me_controller.g.dart';

@riverpod
class MeController extends _$MeController {
  @override
  Future<MeDto> build() async => ref.read(meRepositoryProvider).fetch();

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
```

- [ ] **Step 2: Create `sign_out_controller.dart`**

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/auth/auth_repository_impl.dart';

part 'sign_out_controller.g.dart';

@riverpod
class SignOutController extends _$SignOutController {
  @override
  FutureOr<void> build() async {}

  Future<void> submit() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => ref.read(authRepositoryProvider).signOut());
  }
}
```

- [ ] **Step 3: Create `profile_screen.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';

import 'me_controller.dart';
import 'sign_out_controller.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(meControllerProvider);
    final signOut = ref.watch(signOutControllerProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: AsyncValueWidget(
        value: me,
        onRetry: () => ref.read(meControllerProvider.notifier).refresh(),
        data: (data) => ListView(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          children: [
            Text(data.user.displayName ?? data.user.email,
                 style: theme.textTheme.headlineSmall),
            const SizedBox(height: KpaSpacing.xs),
            Text(data.user.email,
                 style: theme.textTheme.bodyMedium?.copyWith(
                   color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: KpaSpacing.xl),
            Text('Account', style: theme.textTheme.titleMedium),
            const SizedBox(height: KpaSpacing.sm),
            const ListTile(
              leading: Icon(Icons.description_outlined),
              title: Text('Resume'),
              subtitle: Text('Coming soon'),
              enabled: false,
            ),
            const ListTile(
              leading: Icon(Icons.notifications_outlined),
              title: Text('Notifications'),
              subtitle: Text('Coming soon'),
              enabled: false,
            ),
            const SizedBox(height: KpaSpacing.xxl),
            OutlinedButton(
              onPressed: signOut.isLoading ? null : () => _confirmSignOut(context, ref),
              child: Text(signOut.isLoading ? 'Signing out…' : 'Sign out'),
            ),
            const SizedBox(height: KpaSpacing.xxl),
            FutureBuilder<PackageInfo>(
              future: PackageInfo.fromPlatform(),
              builder: (_, snap) => Center(
                child: Text(
                  snap.hasData ? 'v${snap.data!.version} (${snap.data!.buildNumber})' : '',
                  style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmSignOut(BuildContext ctx, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: ctx,
      builder: (c) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text("You'll need to sign in again to continue."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Sign out')),
        ],
      ),
    );
    if (ok == true) {
      await ref.read(signOutControllerProvider.notifier).submit();
    }
  }
}
```

- [ ] **Step 4: Swap placeholder in `router.dart`**

```dart
import 'package:kpa_app/presentation/profile/profile_screen.dart';
// ...
StatefulShellBranch(routes: [
  GoRoute(path: Routes.profile, builder: (_, __) => const ProfileScreen()),
]),
```

- [ ] **Step 5: Run codegen + write widget test**

```bash
cd app
dart run build_runner build --delete-conflicting-outputs
```

Create `app/test/widget/profile_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/domain/me/me_repository.dart';
import 'package:kpa_app/presentation/profile/profile_screen.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

class _FakeRepo implements MeRepository {
  _FakeRepo(this.me);
  final MeDto me;
  @override Future<MeDto> fetch() async => me;
}

void main() {
  testWidgets('renders user name + email + Coming soon rows + Sign out', (tester) async {
    final me = MeDto(
      user: MeUserDto(id: 'u1', email: 'eng@example.com', displayName: 'Eng U',
          role: 'applicant', createdAt: DateTime(2026, 1, 1)),
      applicant: const ApplicantSummaryDto(id: 'a1', userId: 'u1'),
    );
    await tester.pumpWidget(ProviderScope(
      overrides: [meRepositoryProvider.overrideWithValue(_FakeRepo(me))],
      child: MaterialApp(theme: buildTheme(Brightness.light), home: const ProfileScreen()),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Eng U'), findsOneWidget);
    expect(find.text('eng@example.com'), findsOneWidget);
    expect(find.text('Resume'), findsOneWidget);
    expect(find.text('Notifications'), findsOneWidget);
    expect(find.text('Sign out'), findsOneWidget);
  });
}
```

- [ ] **Step 6: Run tests + commit**

```bash
flutter test test/widget/profile_screen_test.dart
git add app/lib/presentation/profile/ app/lib/presentation/routing/router.dart app/test/widget/profile_screen_test.dart
git commit -m "$(cat <<'EOF'
feat(app): profile screen + me/signOut controllers

Header (name + email from /v1/me), Coming-soon rows for Resume +
Notifications (placeholders so the surface acknowledges those
endpoints exist), Sign out with confirmation dialog, version + build
number footer via package_info_plus.

Last placeholder swapped in router.dart — all 7 screens now wired.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 10 — Platform configs

### Task 31: iOS — Info.plist + xcconfig templates

**Files:**
- Modify: `app/ios/Runner/Info.plist`
- Create: `app/ios/Runner/Debug.xcconfig.example`
- Create: `app/ios/Runner/Release.xcconfig.example`
- Modify: `app/ios/Runner.xcodeproj/project.pbxproj` (manual Xcode setup — see step 4)

- [ ] **Step 1: Append the Google Sign-In + ATS bits to `Info.plist`**

Open `app/ios/Runner/Info.plist`. Inside the top-level `<dict>` (next to existing keys), add:

```xml
<key>GIDClientID</key>
<string>$(GOOGLE_IOS_CLIENT_ID)</string>
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleTypeRole</key>
    <string>Editor</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>$(GOOGLE_IOS_REVERSED_CLIENT_ID)</string>
    </array>
  </dict>
</array>
<key>NSAppTransportSecurity</key>
<dict>
  <key>NSAllowsLocalNetworking</key>
  <true/>
</dict>
```

The two `$(…)` variables are substituted at build time from the xcconfig files.

- [ ] **Step 2: Create xcconfig templates**

`app/ios/Runner/Debug.xcconfig.example`:

```
// Copy to Debug.xcconfig (gitignored) and fill in real values.
// Get the iOS client id from Google Cloud Console → Credentials.
// REVERSED_CLIENT_ID is the same value with components reversed; the
// google_sign_in plugin docs show how to compute it.
GOOGLE_IOS_CLIENT_ID = YOUR_IOS_CLIENT_ID.apps.googleusercontent.com
GOOGLE_IOS_REVERSED_CLIENT_ID = com.googleusercontent.apps.YOUR_IOS_CLIENT_ID

#include "Generated.xcconfig"
```

`app/ios/Runner/Release.xcconfig.example`:

```
GOOGLE_IOS_CLIENT_ID = YOUR_IOS_CLIENT_ID.apps.googleusercontent.com
GOOGLE_IOS_REVERSED_CLIENT_ID = com.googleusercontent.apps.YOUR_IOS_CLIENT_ID

#include "Generated.xcconfig"
```

- [ ] **Step 3: Document the manual Xcode step**

The xcconfig files need to be wired into the Runner target's build configurations via Xcode (a project.pbxproj edit that's brittle to make by hand). Add a one-line note to `app/README.md` (created in Task 37):

> **iOS one-time setup:** open `ios/Runner.xcworkspace` in Xcode, select the `Runner` project, then under *Info → Configurations*, set the `Debug` config file to `Runner/Debug.xcconfig` and `Release` to `Runner/Release.xcconfig`. Copy `Debug.xcconfig.example` → `Debug.xcconfig` (gitignored) and fill in real values from Google Cloud Console.

- [ ] **Step 4: Smoke-build iOS (manual)**

```bash
cd app
flutter pub get
flutter build ios --no-codesign --debug
```

Expected: build succeeds. If `GOOGLE_IOS_CLIENT_ID` is undefined, Info.plist will contain the literal `$(GOOGLE_IOS_CLIENT_ID)` string — the plugin will fail at runtime but the build is fine.

- [ ] **Step 5: Commit**

```bash
git add app/ios/Runner/Info.plist app/ios/Runner/Debug.xcconfig.example app/ios/Runner/Release.xcconfig.example
git commit -m "$(cat <<'EOF'
chore(app): iOS Info.plist + xcconfig templates

GIDClientID + URL scheme entries substituted from xcconfig. NSAllowsLocalNetworking
enabled so debug builds can hit http://localhost:8000. Real Debug.xcconfig /
Release.xcconfig are gitignored; examples shipped for onboarding.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 32: Android — manifest + network security config

**Files:**
- Modify: `app/android/app/src/main/AndroidManifest.xml`
- Create: `app/android/app/src/debug/AndroidManifest.xml`
- Create: `app/android/app/src/debug/res/xml/network_security_config.xml`

- [ ] **Step 1: Add INTERNET permission to main manifest**

`flutter create` doesn't generate the INTERNET permission by default for newer Flutter versions. Add to `app/android/app/src/main/AndroidManifest.xml` *before* the `<application>` tag:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

- [ ] **Step 2: Create the debug-only manifest overlay**

`app/android/app/src/debug/AndroidManifest.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:usesCleartextTraffic="true"
        android:networkSecurityConfig="@xml/network_security_config"
        tools:replace="android:usesCleartextTraffic,android:networkSecurityConfig"
        xmlns:tools="http://schemas.android.com/tools" />
</manifest>
```

- [ ] **Step 3: Create the debug network security config**

`app/android/app/src/debug/res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">10.0.2.2</domain>
        <domain includeSubdomains="false">127.0.0.1</domain>
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
</network-security-config>
```

`10.0.2.2` is the Android emulator's host loopback alias.

- [ ] **Step 4: Smoke-build Android**

```bash
cd app
flutter build apk --debug
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add app/android/
git commit -m "$(cat <<'EOF'
chore(app): Android manifest + debug network security config

INTERNET permission in main manifest. Debug overlay enables
cleartextTraffic for 10.0.2.2 / 127.0.0.1 / localhost so emulator
builds can hit the local backend. Release builds inherit the
default Android-N+ HTTPS-only posture.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 33: Web — index template + build script

**Files:**
- Rename: `app/web/index.html` → `app/web/index.template.html`
- Modify: `app/web/index.template.html` (add GIS meta tag)
- Create: `app/scripts/build_web.sh`
- Modify: `app/.gitignore` (already covered in Task 3 but verify)

- [ ] **Step 1: Rename + edit**

```bash
cd app
git mv web/index.html web/index.template.html
```

In `app/web/index.template.html`, inside the `<head>` add:

```html
<meta name="google-signin-client_id" content="{{GOOGLE_WEB_CLIENT_ID}}">
```

Place it before the closing `</head>` tag.

- [ ] **Step 2: Create `app/scripts/build_web.sh`**

```bash
#!/usr/bin/env bash
# Substitutes the GIS client id into web/index.template.html, writes web/index.html,
# then runs `flutter build web`. Pass --dart-define-from-file=.env if you keep
# env vars in .env locally.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${KPA_GOOGLE_WEB_CLIENT_ID:-}" ]]; then
  echo "KPA_GOOGLE_WEB_CLIENT_ID is not set. Source your .env first or export it." >&2
  exit 1
fi

sed "s|{{GOOGLE_WEB_CLIENT_ID}}|${KPA_GOOGLE_WEB_CLIENT_ID}|g" \
  web/index.template.html > web/index.html

flutter build web "$@"
```

Make it executable:
```bash
chmod +x app/scripts/build_web.sh
```

- [ ] **Step 3: For `flutter run -d chrome` during dev**

The dev workflow needs a pre-step before `flutter run`. Add to `app/README.md` (Task 37):

> **Web dev:** before `flutter run -d chrome`, run `KPA_GOOGLE_WEB_CLIENT_ID=… bash scripts/build_web.sh --no-build` (or just run the sed substitution yourself). The dev server reads from `web/index.html` not `web/index.template.html`.

(`--no-build` doesn't exist in `flutter build web`; for dev the script can be simplified — just do the sed step then `flutter run`. Document accordingly.)

Final dev recipe to put in the README:

```bash
sed "s|{{GOOGLE_WEB_CLIENT_ID}}|$KPA_GOOGLE_WEB_CLIENT_ID|g" \
  app/web/index.template.html > app/web/index.html
cd app
flutter run -d chrome \
  --dart-define=KPA_API_BASE_URL=$KPA_API_BASE_URL \
  --dart-define=KPA_GOOGLE_WEB_CLIENT_ID=$KPA_GOOGLE_WEB_CLIENT_ID
```

- [ ] **Step 4: Commit**

```bash
git add app/web/index.template.html app/scripts/build_web.sh
git commit -m "$(cat <<'EOF'
chore(app): web index template + build_web.sh

index.template.html (committed) carries a {{GOOGLE_WEB_CLIENT_ID}}
placeholder; scripts/build_web.sh substitutes from
KPA_GOOGLE_WEB_CLIENT_ID and runs flutter build web. Generated
index.html is gitignored (Task 3).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 11 — App entrypoint

### Task 34: `main.dart` + `app.dart` — wire it all together

**Files:**
- Create: `app/lib/main.dart`
- Create: `app/lib/app.dart`

- [ ] **Step 1: Create `main.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/app.dart';
import 'package:kpa_app/core/config/env.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  Env.validateOrThrow();  // fails fast before any UI renders
  runApp(const ProviderScope(child: KpaApp()));
}
```

- [ ] **Step 2: Create `app.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/presentation/routing/router.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

class KpaApp extends ConsumerWidget {
  const KpaApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'KPA',
      theme: buildTheme(Brightness.light),
      // Dark plumbed but disabled per spec:
      // darkTheme: buildTheme(Brightness.dark),
      themeMode: ThemeMode.light,
      routerConfig: router,
      debugShowCheckedModeBanner: false,
    );
  }
}
```

- [ ] **Step 3: Verify full-app analyze + test pass**

```bash
cd app
flutter analyze
flutter test
```

Expected: analyze clean; all tests pass.

- [ ] **Step 4: Smoke-run (one platform sufficient — pick whichever is easiest)**

```bash
# Make sure the backend is running locally on :8000 first.
cd app
flutter run -d chrome \
  --dart-define=KPA_API_BASE_URL=http://localhost:8000 \
  --dart-define=KPA_GOOGLE_WEB_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
```

Expected: splash appears, redirects to /signin (no refresh token); Sign-in button renders.

- [ ] **Step 5: Commit**

```bash
git add app/lib/main.dart app/lib/app.dart
git commit -m "$(cat <<'EOF'
feat(app): main.dart + KpaApp — wire the foundation together

main validates Env (fails fast on missing --dart-define) then runApp
with ProviderScope. KpaApp consumes the GoRouter via Riverpod and
mounts MaterialApp.router with the light theme. themeMode=light;
darkTheme commented out, ready for the day dark mode ships.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 12 — Integration test (golden path)

### Task 35: Single end-to-end test — sign-in → feed → detail → apply

**Files:**
- Create: `app/test/integration/golden_path_test.dart`
- Create: `app/test/helpers/fake_repositories.dart`

The integration test mocks all six repositories with fakes (no real HTTP). It exercises the full route stack: splash → /feed → tap → /jobs/:id → tap Apply → action bar flips to Withdraw.

- [ ] **Step 1: Create `fake_repositories.dart`**

```dart
import 'dart:async';

import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/domain/auth/auth_repository.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';
import 'package:kpa_app/domain/jobs/applications_repository.dart';
import 'package:kpa_app/domain/jobs/jobs_repository.dart';
import 'package:kpa_app/domain/jobs/saved_jobs_repository.dart';
import 'package:kpa_app/domain/me/me_repository.dart';

class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository({AuthState initial = const SignedOut()}) : _state = initial;
  AuthState _state;
  final _controller = StreamController<AuthState>.broadcast();
  @override Stream<AuthState> watch() => _controller.stream;
  @override AuthState get current => _state;
  @override Future<SignedIn> signInWithGoogle() async {
    final si = const SignedIn(userId: 'u1', email: 'u@e.com', displayName: 'U');
    _state = si; _controller.add(si); return si;
  }
  @override Future<SignedIn> refreshSession() async {
    final si = const SignedIn(userId: 'u1', email: 'u@e.com', displayName: 'U');
    _state = si; _controller.add(si); return si;
  }
  @override Future<void> signOut() async {
    _state = const SignedOut(); _controller.add(_state);
  }
}

class FakeFeedRepository implements FeedRepository {
  FakeFeedRepository({required this.items});
  final List<FeedItemDto> items;
  @override Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async {
    return FeedPageDto(items: items, nextCursor: null);
  }
}

class FakeJobsRepository implements JobsRepository {
  FakeJobsRepository({required this.detail});
  JobDetailDto detail;
  @override Future<JobDetailDto> fetchById(String id) async => detail;
  @override Future<ApplicationDto> applyTo(String jobId, {String source = 'feed'}) async {
    final app = ApplicationDto(id: 'a1', applicantId: 'p', jobId: jobId,
        status: 'applied', source: source, createdAt: DateTime.now());
    detail = detail.copyWith(application: app);
    return app;
  }
  @override Future<SavedJobDto> save(String jobId) async {
    final s = SavedJobDto(id: 's1', applicantId: 'p', jobId: jobId, createdAt: DateTime.now());
    detail = detail.copyWith(savedJob: s);
    return s;
  }
  @override Future<void> unsave(String jobId) async { detail = detail.copyWith(savedJob: null); }
}

class FakeApplicationsRepository implements ApplicationsRepository {
  @override Future<ApplicationsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      const ApplicationsPageDto(items: [], nextCursor: null);
  @override Future<ApplicationDto> withdraw(String id) async => ApplicationDto(
    id: id, applicantId: 'p', jobId: 'j1', status: 'withdrawn', source: 'feed',
    createdAt: DateTime.now(), withdrawnAt: DateTime.now(),
  );
}

class FakeSavedJobsRepository implements SavedJobsRepository {
  @override Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      const SavedJobsPageDto(items: [], nextCursor: null);
}

class FakeMeRepository implements MeRepository {
  @override Future<MeDto> fetch() async => MeDto(
    user: MeUserDto(id: 'u1', email: 'u@e.com', displayName: 'U',
        role: 'applicant', createdAt: DateTime(2026, 1, 1)),
    applicant: const ApplicantSummaryDto(id: 'a1', userId: 'u1'),
  );
}
```

- [ ] **Step 2: Create `golden_path_test.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/app.dart';
import 'package:kpa_app/data/auth/auth_repository_impl.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';
import 'package:kpa_app/data/jobs/applications_repository_impl.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:kpa_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/splash/bootstrap_controller.dart';

import '../helpers/fake_repositories.dart';

void main() {
  testWidgets('golden path: signed-in user lands on feed, opens detail, applies', (tester) async {
    final job = JobSummaryDto(id: 'j1', title: 'Senior Engineer', location: 'BLR',
        status: 'open', postedAt: DateTime(2026, 5, 18));
    final employer = const EmployerSummaryDto(id: 'e1', name: 'Acme Co');
    final feedItem = FeedItemDto(
      match: MatchSummaryDto(id: 'm1', totalScore: 0.85, scoreComponents: const {},
          explanation: const ExplanationDto(fit: 'great fit', generator: 'templated', generatorVersion: '1')),
      job: job, employer: employer,
    );

    await tester.pumpWidget(ProviderScope(
      overrides: [
        // Pre-authenticate so we skip the sign-in flow.
        authStateNotifierProvider.overrideWith(() {
          final n = AuthStateNotifier();
          n.state = const SignedIn(userId: 'u1', email: 'u@e.com');
          return n;
        }),
        // Bootstrap returns "go to feed" without calling refresh.
        bootstrapControllerProvider.overrideWith(() => _Bootstrapped()),
        // All repos faked.
        authRepositoryProvider.overrideWithValue(FakeAuthRepository(initial: const SignedIn(userId: 'u1', email: 'u@e.com'))),
        feedRepositoryProvider.overrideWithValue(FakeFeedRepository(items: [feedItem])),
        jobsRepositoryProvider.overrideWithValue(FakeJobsRepository(
          detail: JobDetailDto(job: job, employer: employer, match: feedItem.match),
        )),
        applicationsRepositoryProvider.overrideWithValue(FakeApplicationsRepository()),
        savedJobsRepositoryProvider.overrideWithValue(FakeSavedJobsRepository()),
        meRepositoryProvider.overrideWithValue(FakeMeRepository()),
      ],
      child: const KpaApp(),
    ));
    await tester.pumpAndSettle();

    // Lands on /feed
    expect(find.text('For you'), findsOneWidget);
    expect(find.text('Senior Engineer'), findsOneWidget);

    // Tap the card → navigates to /jobs/j1
    await tester.tap(find.text('Senior Engineer'));
    await tester.pumpAndSettle();

    expect(find.text('Why this match'), findsOneWidget);
    expect(find.text('Apply'), findsOneWidget);

    // Tap Apply
    await tester.tap(find.text('Apply'));
    await tester.pumpAndSettle();

    // Action bar should now show Withdraw
    expect(find.text('Withdraw'), findsOneWidget);
    expect(find.text('Apply'), findsNothing);
  });
}

class _Bootstrapped extends BootstrapController {
  @override Future<BootstrapOutcome> build() async => BootstrapOutcome.feed;
}
```

- [ ] **Step 3: Run the integration test**

```bash
cd app
flutter test test/integration/
```

Expected: 1 test passes.

- [ ] **Step 4: Commit**

```bash
git add app/test/integration/ app/test/helpers/
git commit -m "$(cat <<'EOF'
test(app): integration test — golden path

Mocks all six repos via Riverpod overrides + uses _Bootstrapped to
skip real refresh. Walks the full route stack: feed → detail → Apply
tap → action bar flips to Withdraw. ~150 lines incl. fakes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 13 — CI + docs

### Task 36: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/app.yml` (at repo root, not under `app/`)

- [ ] **Step 1: Create `.github/workflows/app.yml`**

```yaml
name: app
on:
  pull_request:
    paths: ['app/**']
  push:
    branches: [main]
    paths: ['app/**']

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: app
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          channel: stable
          flutter-version: 3.27.x
          cache: true
      - run: flutter pub get
      - run: dart run build_runner build --delete-conflicting-outputs
      - run: dart format --set-exit-if-changed lib test
      - run: flutter analyze
      - run: flutter test --coverage
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add .github/workflows/app.yml
git commit -m "$(cat <<'EOF'
ci(app): add app workflow — analyze + format + test on PRs

Triggers on PR + main pushes touching app/**. Pins Flutter 3.27.x
stable; runs build_runner before analyze so generated files are
present; dart format --set-exit-if-changed enforces formatting;
flutter analyze + flutter test --coverage round it out.

No flutter build web step in v0 (5-10min addition; failure modes
usually platform-config drift caught faster locally).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 37: `app/README.md` + project `CLAUDE.md` additions

**Files:**
- Create: `app/README.md`
- Modify: `CLAUDE.md` (at repo root — append a Flutter app section)

- [ ] **Step 1: Create `app/README.md`**

```markdown
# KPA — Flutter app

iOS + Android + Web client for the KPA platform. Built on the foundation laid out in `docs/superpowers/specs/2026-05-21-flutter-app-shell-design.md`.

## Stack

- Flutter 3.27.x (stable channel)
- Riverpod 2.6 (codegen)
- freezed 2.5, dio 5.7, go_router 14.6
- google_sign_in 6.2 + google_sign_in_web 0.12 for auth
- flutter_secure_storage 9.2 for refresh-token persistence

## First-time setup

```bash
cd app
flutter pub get
dart run build_runner build --delete-conflicting-outputs
```

Copy `.env.example` → `.env` and fill in `KPA_GOOGLE_WEB_CLIENT_ID` + `KPA_API_BASE_URL` (defaults work for local dev against `http://localhost:8000`).

### iOS one-time setup

Open `ios/Runner.xcworkspace` in Xcode. Select the `Runner` project, then under *Info → Configurations*, set:
- Debug config file → `Runner/Debug.xcconfig`
- Release config file → `Runner/Release.xcconfig`

Copy `ios/Runner/Debug.xcconfig.example` → `ios/Runner/Debug.xcconfig` (gitignored) and fill in real values from Google Cloud Console.

## Run

The backend must be running on `http://localhost:8000` first (see `api/README.md`).

```bash
# iOS simulator
flutter run -d ios \
  --dart-define-from-file=.env

# Android emulator
flutter run -d emulator-5554 \
  --dart-define=KPA_API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define-from-file=.env

# Web
sed "s|{{GOOGLE_WEB_CLIENT_ID}}|$KPA_GOOGLE_WEB_CLIENT_ID|g" web/index.template.html > web/index.html
flutter run -d chrome --dart-define-from-file=.env
```

Note Android needs `http://10.0.2.2:8000` (emulator's host loopback alias) instead of `localhost`.

## Test

```bash
flutter test                       # all tests
flutter test test/unit/            # unit only
flutter test test/widget/          # widget only
flutter test test/integration/     # the golden-path integration test
```

## Lint + format

```bash
dart format lib test
flutter analyze
```

CI (`.github/workflows/app.yml`) enforces both on every PR touching `app/**`.

## Architecture

Pragmatic Clean Architecture — `lib/data/` + `lib/domain/` + `lib/presentation/` + `lib/core/`. Repository interfaces live in `domain/`; impls in `data/`; Riverpod providers + screens in `presentation/`. Cross-layer infrastructure (env validation, typed exceptions, logger) in `core/`.

See `docs/superpowers/specs/2026-05-21-flutter-app-shell-design.md` for the design doc.
```

- [ ] **Step 2: Append to root `CLAUDE.md`**

Open `/Users/ahamadshah/ahamed_personal/kpa/CLAUDE.md` and append a new section after the existing content:

```markdown

## Flutter app (`app/`)

The applicant-facing iOS + Android + Web client lives in `app/` as a sibling of `api/`. Architecture follows Pragmatic Clean Architecture — `lib/data/` + `lib/domain/` + `lib/presentation/` + `lib/core/`. State management is Riverpod 2.6 with code-gen; HTTP is dio 5.7; routing is go_router 14.6 with `StatefulShellRoute.indexedStack` for the four-tab bottom nav.

### Day-to-day commands

```bash
# from app/
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # after touching @freezed / @riverpod / @JsonSerializable
flutter run -d chrome --dart-define-from-file=.env
flutter test
flutter analyze
dart format lib test
```

### Non-obvious bits

- **Refresh-on-401 interceptor** (`lib/data/api/refresh_on_401_interceptor.dart`) is the single most important piece of code; single-flight via `Completer<String>?` so concurrent 401s never stampede the refresh endpoint. Tests in `test/unit/data/api/refresh_on_401_interceptor_test.dart` are the canonical specification — keep them passing.

- **`AccessTokenHolder`** (`lib/data/api/access_token_holder.dart`) is a mutable singleton that bridges dio (below Riverpod's reach) and the rest of the app. The Riverpod `accessTokenNotifierProvider` mirrors it for UI consumers; never let them diverge.

- **dio_provider depends on a presentation-layer notifier** (`authStateNotifierProvider`) to push `SignedOut` on refresh failure. Documented inline as the one allowed exception to data/→presentation/ purity. Don't replicate this pattern — it's a load-bearing convenience for this single edge case.

- **Pragmatic CA cheat:** `data/<feature>/*_dto.dart` files are referenced from `lib/domain/<feature>/` via `export` directives. Domain consumers import the `*Dto` types using a `domain/` path; the underlying definition lives in `data/`. Strict CA would forbid this; we accept it because the alternative (duplicate Entity + DTO + mapper trio) adds ~120 LOC per feature.

- **No mutation of the feed on apply/save/withdraw/unsave.** Each mutation invalidates the corresponding list controller (`applicationsControllerProvider` / `savedControllerProvider`) + the `jobDetailControllerProvider(id)`, never the feed. The feed is treated as immutable-for-the-session per spec §State management.

- **Per-tab navigation stacks** via `StatefulShellRoute.indexedStack`. `/jobs/:id` is defined as a child route under each of the four tab branches — tapping a job from Feed pushes onto the Feed stack, tapping from Saved pushes onto Saved. Don't promote `/jobs/:id` to a top-level route; you'd lose per-tab persistence.

- **iOS xcconfig + Android debug manifest overlay** carry the per-platform Google Sign-In configuration. xcconfig files with real client IDs are gitignored; `.example` templates are committed.

- **`--dart-define`, no flavors.** `KPA_API_BASE_URL` and `KPA_GOOGLE_WEB_CLIENT_ID` are required at compile time; `Env.validateOrThrow()` runs in `main()` before `runApp`. Flavors deferred until per-env app icons / bundle IDs are actually needed.

- **Light theme only in v0; dark plumbed but disabled.** `MaterialApp.router(themeMode: ThemeMode.light)`. Flip to `ThemeMode.system` + populate the dark branch of `buildTheme` when dark mode ships.

- **No `dio_smart_retry`, no toast plugin, no analytics, no Sentry.** All deferred to follow-up plans per spec §Non-goals.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add app/README.md CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: app README + CLAUDE.md additions for Flutter foundation

app/README.md covers setup, run commands per platform, test/lint/format,
architecture overview, link to the spec. CLAUDE.md gains a 'Flutter app'
section with the non-obvious invariants future Claudes need to know
(refresh interceptor, holder bridge, dio→presentation exception,
Pragmatic CA cheat, no-feed-mutation rule, per-tab stacks, platform
configs, --dart-define).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Plan complete

All 37 tasks land the foundation + the seven thin screens + platform configs + CI + docs. After Task 37 commits cleanly, the branch is ready for:

```bash
git push -u origin feat/app-shell-foundation
gh pr create --base main \
  --title "App shell foundation: auth + feed + job detail" \
  --body "Implements docs/superpowers/specs/2026-05-21-flutter-app-shell-design.md."
```

---

## Self-review notes

**Spec coverage:** Every section of the spec maps to at least one task —

| Spec section | Task(s) |
|---|---|
| §Stack decisions (Riverpod, dio+freezed, go_router, layered CA) | Tasks 2, 3 (deps + config) |
| §Architecture — project layout | Tasks 1, 4-30 (one task per concern) |
| §Architecture — auth lifecycle (interceptors, single-flight) | Tasks 11, 13, 15, 16 |
| §Architecture — repositories (6 interfaces, impl) | Tasks 10, 16, 17, 18, 19, 20, 21 |
| §Architecture — state management patterns | Tasks 24-30 (each screen) |
| §Primitive widgets | Tasks 8, 9 |
| §Theming + tokens | Task 7 |
| §Platform specifics (iOS / Android / Web) | Tasks 31, 32, 33 |
| §Build configuration (--dart-define, no flavors) | Tasks 3, 4 |
| §Screens (7 total) | Tasks 24, 25, 26, 27, 28, 29, 30 |
| §Testing strategy (5 priorities) | Repository tests in Tasks 17-21; interceptor in Task 13; provider tests embedded with screens; widget smoke per screen; integration in Task 35 |
| §CI | Task 36 |
| §Non-goals (notifications UI, resume UX, dark mode, etc.) | Not addressed by design — call-outs in app/README.md + CLAUDE.md addition |

**Type consistency check:** Method names match across tasks — `fetchPage`, `fetchById`, `applyTo`, `save`, `unsave`, `withdraw`, `signInWithGoogle`, `refreshSession`, `signOut`. Provider names match — `feedControllerProvider`, `applicationsControllerProvider`, `savedControllerProvider`, `jobDetailControllerProvider(id)`, `applyToJobControllerProvider(id)`, etc. DTOs reference each other consistently (`JobSummaryDto` defined in feed_dto, imported by jobs_dto).

**Placeholder scan:** No "TBD" / "TODO" / "implement later" / "similar to Task N" references.

**Known integration sequencing wart:** Tasks 27 / 28 / 29 have a forward-reference cycle — the JobDetail mutation controllers (Task 27) `ref.invalidate` providers that don't exist until Tasks 28 (applications) and 29 (saved). The plan handles this by instructing the engineer to comment out those lines in Task 27 and un-comment them in Tasks 28 / 29. A cleaner alternative would be to write the controllers in Task 28 / 29 first, but doing the mutation controllers all together in Task 27 keeps the JobDetail surface cohesive in one task. Trade accepted.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-22-flutter-app-shell.md`.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best when tasks are mostly independent (which they largely are here, modulo the Task 27/28/29 forward-reference wart called out above).

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints. Best if you want to watch each task land in real time and adjust mid-flight.

**Which approach?**
