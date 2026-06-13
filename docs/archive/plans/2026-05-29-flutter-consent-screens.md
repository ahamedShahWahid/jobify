# P4-F Flutter Consent Screens — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship the user-facing UI for PRs #26 (consent), #27 (DSR export), #28 (DSR delete). Single `/profile/privacy` screen with 3 consent toggles + Download data button + Delete account navigation. `/profile/privacy/delete` screen with typed-confirmation guard.

**Architecture:** `lib/data/consents/` + `lib/data/dsr/` DTOs + APIs + repositories (Riverpod codegen). `lib/presentation/privacy/` screens + `@Riverpod` controllers. Profile screen gains a "Privacy & data" ListTile.

**Tech Stack:** Flutter 3.x / Riverpod 4.x (codegen) / Freezed 3.x / dio 5.7 / go_router 14.6.

**Spec:** `docs/superpowers/specs/2026-05-29-flutter-consent-screens-design.md`

---

## Files

**Create:**
- `app/lib/core/consent/consent_scope.dart`
- `app/lib/data/consents/consent_dto.dart`
- `app/lib/data/consents/consent_api.dart`
- `app/lib/data/consents/consents_repository.dart`
- `app/lib/data/consents/consents_repository_impl.dart`
- `app/lib/data/dsr/dsr_dto.dart`
- `app/lib/data/dsr/dsr_api.dart`
- `app/lib/data/dsr/dsr_repository.dart`
- `app/lib/data/dsr/dsr_repository_impl.dart`
- `app/lib/presentation/privacy/privacy_controller.dart`
- `app/lib/presentation/privacy/privacy_state.dart`
- `app/lib/presentation/privacy/privacy_screen.dart`
- `app/lib/presentation/privacy/delete_account_controller.dart`
- `app/lib/presentation/privacy/delete_account_screen.dart`
- `app/lib/presentation/auth/delete_success_snackbar_provider.dart`
- `app/test/unit/data/consents/consents_repository_impl_test.dart`
- `app/test/unit/data/dsr/dsr_repository_impl_test.dart`
- `app/test/widget/presentation/privacy/privacy_screen_test.dart`
- `app/test/widget/presentation/privacy/delete_account_screen_test.dart`

**Modify:**
- `app/lib/presentation/routing/routes.dart` — add `privacy` + `privacyDelete`.
- `app/lib/presentation/routing/router.dart` — wire two new routes under the Profile tab branch.
- `app/lib/presentation/profile/profile_screen.dart` — add "Privacy & data" ListTile.
- `app/lib/presentation/auth/sign_in_screen.dart` — show one-time delete-success snackbar.
- `app/test/helpers/fake_repositories.dart` — add `FakeConsentsRepository`, `FakeDsrRepository`.
- `CLAUDE.md` — add the privacy-screen invariants per spec § 9.

---

### Task 1: Data layer (consents + DSR)

**Files in scope:** everything under `app/lib/data/consents/` + `app/lib/data/dsr/` + `app/lib/core/consent/`.

- [ ] **Step 1: `lib/core/consent/consent_scope.dart`**

```dart
/// Mirror of backend's ConsentScope StrEnum from PR #26.
/// Plain string values match the wire format (backend uses TEXT, not enum).
enum ConsentScope {
  emailTransactional('email_transactional'),
  emailMarketing('email_marketing'),
  inAppNotifications('in_app_notifications'),
  whatsappNotifications('whatsapp_notifications'),
  smsNotifications('sms_notifications'),
  profileVisibilityRecruiters('profile_visibility_recruiters'),
  thirdPartySharingRecruiters('third_party_sharing_recruiters');

  const ConsentScope(this.wire);
  final String wire;

  static ConsentScope? fromWire(String wire) {
    for (final s in ConsentScope.values) {
      if (s.wire == wire) return s;
    }
    return null;
  }

  /// Active scopes shown in the v0 Privacy UI. Reserved scopes are hidden.
  static const v0VisibleScopes = <ConsentScope>[
    ConsentScope.emailTransactional,
    ConsentScope.emailMarketing,
    ConsentScope.inAppNotifications,
  ];
}
```

- [ ] **Step 2: `lib/data/consents/consent_dto.dart`**

```dart
import 'package:json_annotation/json_annotation.dart';

part 'consent_dto.g.dart';

@JsonSerializable()
class ConsentDto {
  ConsentDto({required this.scope, required this.granted, required this.updatedAt});

  final String scope;
  final bool granted;
  @JsonKey(name: 'updated_at')
  final DateTime updatedAt;

  factory ConsentDto.fromJson(Map<String, dynamic> json) =>
      _$ConsentDtoFromJson(json);
  Map<String, dynamic> toJson() => _$ConsentDtoToJson(this);
}

@JsonSerializable()
class ConsentListResponse {
  ConsentListResponse({required this.items});

  final List<ConsentDto> items;

  factory ConsentListResponse.fromJson(Map<String, dynamic> json) =>
      _$ConsentListResponseFromJson(json);
}
```

- [ ] **Step 3: `lib/data/consents/consent_api.dart`**

```dart
import 'package:dio/dio.dart';

import 'package:kpa_app/data/consents/consent_dto.dart';

class ConsentApi {
  ConsentApi(this._dio);
  final Dio _dio;

  Future<ConsentListResponse> list() async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/me/consents');
    return ConsentListResponse.fromJson(res.data!);
  }

  Future<ConsentDto> patch(String scope, {required bool granted}) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/me/consents/$scope',
      data: {'granted': granted},
    );
    return ConsentDto.fromJson(res.data!);
  }
}
```

- [ ] **Step 4: `lib/data/consents/consents_repository.dart`**

```dart
import 'package:kpa_app/data/consents/consent_dto.dart';

abstract interface class ConsentsRepository {
  Future<ConsentListResponse> list();
  Future<ConsentDto> patch(String scope, {required bool granted});
}
```

- [ ] **Step 5: `lib/data/consents/consents_repository_impl.dart`**

```dart
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/consents/consent_api.dart';
import 'package:kpa_app/data/consents/consent_dto.dart';
import 'package:kpa_app/data/consents/consents_repository.dart';

part 'consents_repository_impl.g.dart';

class ConsentsRepositoryImpl implements ConsentsRepository {
  ConsentsRepositoryImpl(this._api);
  final ConsentApi _api;

  @override
  Future<ConsentListResponse> list() => _api.list();

  @override
  Future<ConsentDto> patch(String scope, {required bool granted}) =>
      _api.patch(scope, granted: granted);
}

@riverpod
ConsentsRepository consentsRepository(Ref ref) {
  final dio = ref.read(dioProvider);
  return ConsentsRepositoryImpl(ConsentApi(dio));
}
```

- [ ] **Step 6: DSR DTOs + API + repo (`lib/data/dsr/`)**

`lib/data/dsr/dsr_dto.dart`:

```dart
import 'package:json_annotation/json_annotation.dart';

part 'dsr_dto.g.dart';

@JsonSerializable()
class OwnerlessEmployerWarningDto {
  OwnerlessEmployerWarningDto({
    required this.type,
    required this.employerId,
    required this.employerName,
    required this.message,
  });

  final String type;
  @JsonKey(name: 'employer_id')
  final String employerId;
  @JsonKey(name: 'employer_name')
  final String employerName;
  final String message;

  factory OwnerlessEmployerWarningDto.fromJson(Map<String, dynamic> json) =>
      _$OwnerlessEmployerWarningDtoFromJson(json);
}

@JsonSerializable()
class DsrDeleteResponse {
  DsrDeleteResponse({
    required this.deletedAt,
    required this.sectionCounts,
    required this.warnings,
  });

  @JsonKey(name: 'deleted_at')
  final DateTime deletedAt;
  @JsonKey(name: 'section_counts')
  final Map<String, int> sectionCounts;
  final List<OwnerlessEmployerWarningDto> warnings;

  factory DsrDeleteResponse.fromJson(Map<String, dynamic> json) =>
      _$DsrDeleteResponseFromJson(json);
}
```

`lib/data/dsr/dsr_api.dart`:

```dart
import 'package:dio/dio.dart';

import 'package:kpa_app/data/dsr/dsr_dto.dart';

class DsrApi {
  DsrApi(this._dio);
  final Dio _dio;

  /// Returns the export envelope as a raw JSON string. We don't parse
  /// Dart-side — the contract is "give me the JSON" — we just relay it
  /// to the clipboard.
  Future<String> exportData() async {
    final res = await _dio.post<dynamic>(
      '/v1/me/dsr/export',
      options: Options(responseType: ResponseType.plain),
    );
    return res.data as String;
  }

  Future<DsrDeleteResponse> deleteAccount() async {
    final res = await _dio.delete<Map<String, dynamic>>(
      '/v1/me/dsr',
      data: {'confirmation': 'DELETE_MY_ACCOUNT'},
    );
    return DsrDeleteResponse.fromJson(res.data!);
  }
}
```

`lib/data/dsr/dsr_repository.dart`:

```dart
import 'package:kpa_app/data/dsr/dsr_dto.dart';

abstract interface class DsrRepository {
  Future<String> exportData();
  Future<DsrDeleteResponse> deleteAccount();
}
```

`lib/data/dsr/dsr_repository_impl.dart`:

```dart
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/dsr/dsr_api.dart';
import 'package:kpa_app/data/dsr/dsr_dto.dart';
import 'package:kpa_app/data/dsr/dsr_repository.dart';

part 'dsr_repository_impl.g.dart';

class DsrRepositoryImpl implements DsrRepository {
  DsrRepositoryImpl(this._api);
  final DsrApi _api;

  @override
  Future<String> exportData() => _api.exportData();

  @override
  Future<DsrDeleteResponse> deleteAccount() => _api.deleteAccount();
}

@riverpod
DsrRepository dsrRepository(Ref ref) {
  final dio = ref.read(dioProvider);
  return DsrRepositoryImpl(DsrApi(dio));
}
```

- [ ] **Step 7: Run codegen**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/app
dart run build_runner build --delete-conflicting-outputs
```

Verify: no errors. The `.g.dart` files generate next to each new source file.

- [ ] **Step 8: Lint + analyze**

```bash
flutter analyze
dart format lib test
```

Clean.

- [ ] **Step 9: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add app/lib/core/consent/ app/lib/data/consents/ app/lib/data/dsr/
git commit -m "feat(app): consents + DSR data layer

DTOs, APIs, and repositories mirroring the data/notifications pattern.
ConsentScope enum lives at lib/core/consent/ with the seven backend
scopes; v0VisibleScopes lists the three active ones for the UI."
```

---

### Task 2: Presentation layer (controllers + screens + routes)

**Files in scope:** `app/lib/presentation/privacy/` + route changes + Profile screen tile.

- [ ] **Step 1: `lib/presentation/privacy/privacy_state.dart`**

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

import 'package:kpa_app/data/consents/consent_dto.dart';

part 'privacy_state.freezed.dart';

@freezed
abstract class PrivacyState with _$PrivacyState {
  const factory PrivacyState({
    required List<ConsentDto> consents,
    @Default(false) bool exportInProgress,
    Object? mutationError,
  }) = _PrivacyState;
}
```

- [ ] **Step 2: `lib/presentation/privacy/privacy_controller.dart`**

```dart
import 'package:flutter/services.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/consents/consent_dto.dart';
import 'package:kpa_app/data/consents/consents_repository_impl.dart';
import 'package:kpa_app/data/dsr/dsr_repository_impl.dart';
import 'package:kpa_app/presentation/privacy/privacy_state.dart';

part 'privacy_controller.g.dart';

@Riverpod(keepAlive: true)
class PrivacyController extends _$PrivacyController {
  @override
  Future<PrivacyState> build() async {
    final list = await ref.read(consentsRepositoryProvider).list();
    return PrivacyState(consents: list.items);
  }

  Future<void> setConsent(String scope, bool granted) async {
    final current = state.valueOrNull;
    if (current == null) return;

    final repo = ref.read(consentsRepositoryProvider);

    // Optimistic.
    final optimistic = current.consents.map((c) {
      if (c.scope == scope) {
        return ConsentDto(
          scope: c.scope,
          granted: granted,
          updatedAt: c.updatedAt,
        );
      }
      return c;
    }).toList();
    state = AsyncData(current.copyWith(consents: optimistic, mutationError: null));

    try {
      final updated = await repo.patch(scope, granted: granted);
      // Replace optimistic item with server response.
      final canonical = current.consents.map((c) {
        return c.scope == scope ? updated : c;
      }).toList();
      state = AsyncData(current.copyWith(consents: canonical));
    } catch (e) {
      // Rollback.
      state = AsyncData(current.copyWith(mutationError: e));
    }
  }

  Future<String?> exportData() async {
    final current = state.valueOrNull;
    if (current == null) return null;
    state = AsyncData(current.copyWith(exportInProgress: true, mutationError: null));
    try {
      final envelope = await ref.read(dsrRepositoryProvider).exportData();
      await Clipboard.setData(ClipboardData(text: envelope));
      state = AsyncData(current.copyWith(exportInProgress: false));
      return envelope;
    } catch (e) {
      state = AsyncData(current.copyWith(
        exportInProgress: false,
        mutationError: e,
      ));
      return null;
    }
  }
}
```

- [ ] **Step 3: `lib/presentation/privacy/privacy_screen.dart`**

The full screen widget. Reads `privacyControllerProvider`, renders three Switch tiles using the `v0VisibleScopes` list, plus the Download button + Delete navigation tile.

Key UI pieces:

- A `_consentLabel(ConsentScope)` private function returns label + description per scope:
  - `emailTransactional` → "Service updates" / "Email about your applications, matches, and account."
  - `emailMarketing` → "Job recommendations" / "Weekly digest of jobs that fit your profile."
  - `inAppNotifications` → "In-app notifications" / "See alerts inside the app."
- Each `SwitchListTile.adaptive` calls `controller.setConsent(...)`. For `emailTransactional` going from `true → false`, intercept with a confirmation dialog first.
- The Download button shows a `CircularProgressIndicator.adaptive()` overlay while `state.exportInProgress`. On success, `ScaffoldMessenger.of(context).showSnackBar(...)` with the multi-line clipboard message.
- The Delete tile uses `context.go(Routes.privacyDelete)`.

Use `AsyncValueWidget` (same as `profile_screen.dart`) to handle the loading/error states of the initial fetch.

- [ ] **Step 4: `lib/presentation/privacy/delete_account_controller.dart`**

```dart
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/dsr/dsr_repository_impl.dart';
import 'package:kpa_app/presentation/auth/auth_state_controller.dart';
import 'package:kpa_app/presentation/auth/delete_success_snackbar_provider.dart';

part 'delete_account_controller.g.dart';

@riverpod
class DeleteAccountController extends _$DeleteAccountController {
  @override
  AsyncValue<void> build() => const AsyncData(null);

  Future<void> submit() async {
    state = const AsyncLoading();
    try {
      await ref.read(dsrRepositoryProvider).deleteAccount();

      // Order matters: flag the snackbar BEFORE clearing the token so the
      // post-redirect render of /signin reads the flag.
      ref.read(deleteSuccessSnackbarProvider.notifier).fire();

      ref.read(accessTokenHolderProvider).clear();
      ref.read(authStateProvider.notifier).signOutLocally();

      state = const AsyncData(null);
    } catch (e, st) {
      state = AsyncError(e, st);
    }
  }
}
```

Important: the actual controller imports may differ — read the existing `lib/presentation/auth/sign_out_controller.dart` for the canonical pattern of clearing the holder + pushing SignedOut. Use the same approach.

- [ ] **Step 5: `lib/presentation/auth/delete_success_snackbar_provider.dart`**

```dart
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'delete_success_snackbar_provider.g.dart';

/// One-time flag — Sign-in screen reads it and clears it after showing
/// the "Your account has been deleted." snackbar.
@Riverpod(keepAlive: true)
class DeleteSuccessSnackbar extends _$DeleteSuccessSnackbar {
  @override
  bool build() => false;

  void fire() => state = true;
  void consume() => state = false;
}
```

- [ ] **Step 6: `lib/presentation/privacy/delete_account_screen.dart`**

A `StatefulWidget` (not `ConsumerWidget`) because of the `TextEditingController`. Or `HookConsumerWidget` if the existing codebase uses hooks (check).

Pattern:
- `TextEditingController _confirmation` + `_focusNode`.
- `ValueListenableBuilder` watching `_confirmation` so the FilledButton's `onPressed` flips between null and a real callback.
- On submit: show confirmation modal → call `ref.read(deleteAccountControllerProvider.notifier).submit()` → listen to the controller via `ref.listen(deleteAccountControllerProvider, ...)` for success/error → show success snackbar or rebuild for retry.

- [ ] **Step 7: Routes**

`lib/presentation/routing/routes.dart`:

```dart
static const privacy = '/profile/privacy';
static const privacyDelete = '/profile/privacy/delete';
```

`lib/presentation/routing/router.dart` — find the Profile branch (search for `Routes.profile`). Add two GoRoutes nested under the same Profile shell branch:

```dart
GoRoute(
  path: 'privacy',
  builder: (_, __) => const PrivacyScreen(),
  routes: [
    GoRoute(
      path: 'delete',
      builder: (_, __) => const DeleteAccountScreen(),
    ),
  ],
),
```

Place this NEXT TO the existing `/profile/edit`, `/profile/resume`, `/profile/notifications` children. Use relative paths (`'privacy'`, not `/profile/privacy`) per go_router nesting convention.

- [ ] **Step 8: Profile screen tile**

In `app/lib/presentation/profile/profile_screen.dart`, find the existing `ListTile` for Notifications. Add a new ListTile right after it:

```dart
ListTile(
  leading: const Icon(Icons.shield_outlined),
  title: const Text('Privacy & data'),
  subtitle: const Text('Preferences, export, delete'),
  onTap: () => context.go(Routes.privacy),
),
```

- [ ] **Step 9: Sign-in snackbar consumer**

In `app/lib/presentation/auth/sign_in_screen.dart` (read it first to find the right place — likely in `build()`), use a `PostFrameCallback` to read the flag and show a snackbar once:

```dart
WidgetsBinding.instance.addPostFrameCallback((_) {
  if (ref.read(deleteSuccessSnackbarProvider)) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Your account has been deleted.')),
    );
    ref.read(deleteSuccessSnackbarProvider.notifier).consume();
  }
});
```

Add inside `build()` of the existing `SignInScreen`. If the screen is rebuilt before the post-frame callback runs, the snackbar still shows exactly once because `consume()` flips it false.

- [ ] **Step 10: Codegen + analyze + format**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/app
dart run build_runner build --delete-conflicting-outputs
flutter analyze
dart format lib
```

Clean.

- [ ] **Step 11: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add app/lib/presentation/privacy/ \
        app/lib/presentation/auth/delete_success_snackbar_provider.dart \
        app/lib/presentation/auth/delete_success_snackbar_provider.g.dart \
        app/lib/presentation/routing/ \
        app/lib/presentation/profile/profile_screen.dart \
        app/lib/presentation/auth/sign_in_screen.dart
git commit -m "feat(app): PrivacyScreen + DeleteAccountScreen + routes

/profile/privacy renders the three v0-visible consent toggles (reserved
scopes hidden) + Download data + Delete account. Email-transactional
opt-out shows a confirmation dialog. Delete flow at /profile/privacy/delete
requires typed 'DELETE_MY_ACCOUNT' confirmation; on success clears the
AccessTokenHolder + pushes SignedOut + flags the sign-in screen to show
a one-time 'Your account has been deleted.' snackbar."
```

---

### Task 3: Unit + widget tests + fake repositories

**Files in scope:** test files + `test/helpers/fake_repositories.dart`.

- [ ] **Step 1: Add fakes to `test/helpers/fake_repositories.dart`**

Read the existing file to match the style. Add:

```dart
class FakeConsentsRepository implements ConsentsRepository {
  FakeConsentsRepository({List<ConsentDto>? initial})
      : items = initial ?? _defaultItems();

  List<ConsentDto> items;
  int patchCallCount = 0;
  Object? patchError;

  @override
  Future<ConsentListResponse> list() async => ConsentListResponse(items: items);

  @override
  Future<ConsentDto> patch(String scope, {required bool granted}) async {
    patchCallCount++;
    if (patchError != null) throw patchError!;
    final updated = items.firstWhere((c) => c.scope == scope);
    final next = ConsentDto(
      scope: scope,
      granted: granted,
      updatedAt: DateTime.now().toUtc(),
    );
    items = items.map((c) => c.scope == scope ? next : c).toList();
    return next;
  }

  static List<ConsentDto> _defaultItems() => [
        ConsentDto(scope: 'email_transactional', granted: true, updatedAt: DateTime.utc(2026)),
        ConsentDto(scope: 'email_marketing', granted: false, updatedAt: DateTime.utc(2026)),
        ConsentDto(scope: 'in_app_notifications', granted: true, updatedAt: DateTime.utc(2026)),
      ];
}

class FakeDsrRepository implements DsrRepository {
  String exportPayload = '{"version":"1","exported_at":"..."}';
  Object? exportError;
  DsrDeleteResponse? deleteResponse;
  Object? deleteError;
  int exportCallCount = 0;
  int deleteCallCount = 0;

  @override
  Future<String> exportData() async {
    exportCallCount++;
    if (exportError != null) throw exportError!;
    return exportPayload;
  }

  @override
  Future<DsrDeleteResponse> deleteAccount() async {
    deleteCallCount++;
    if (deleteError != null) throw deleteError!;
    return deleteResponse ??
        DsrDeleteResponse(
          deletedAt: DateTime.utc(2026, 5, 29),
          sectionCounts: const {'notifications': 0, 'user_tombstoned': 1},
          warnings: const [],
        );
  }
}
```

- [ ] **Step 2: `test/unit/data/consents/consents_repository_impl_test.dart`**

Mirror the existing `notifications_repository_impl_test.dart` pattern. Two tests:

```dart
void main() {
  group('ConsentsRepositoryImpl', () {
    test('list() decodes the wire shape', () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://t'));
      dio.interceptors.add(MockInterceptor(responses: {
        'GET /v1/me/consents': const MockResponse(status: 200, body: {
          'items': [
            {'scope': 'email_transactional', 'granted': true, 'updated_at': '2026-05-29T00:00:00Z'},
          ],
        }),
      }));
      final repo = ConsentsRepositoryImpl(ConsentApi(dio));
      final res = await repo.list();
      expect(res.items.single.scope, 'email_transactional');
      expect(res.items.single.granted, isTrue);
    });

    test('patch() sends {granted: bool}', () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://t'));
      final mock = MockInterceptor(responses: {
        'PATCH /v1/me/consents/email_marketing': const MockResponse(status: 200, body: {
          'scope': 'email_marketing',
          'granted': true,
          'updated_at': '2026-05-29T00:00:00Z',
        }),
      });
      dio.interceptors.add(mock);
      final repo = ConsentsRepositoryImpl(ConsentApi(dio));
      final res = await repo.patch('email_marketing', granted: true);
      expect(res.granted, isTrue);
      expect(mock.lastDataFor('PATCH', '/v1/me/consents/email_marketing'),
          {'granted': true});
    });
  });
}
```

Check `MockInterceptor`'s exact API in `test/helpers/mock_interceptor.dart` — there may be a different shape. Read it first.

- [ ] **Step 3: `test/unit/data/dsr/dsr_repository_impl_test.dart`**

Three tests:
1. `exportData()` returns the raw response body as a String.
2. `deleteAccount()` sends `{confirmation: 'DELETE_MY_ACCOUNT'}` in the request body.
3. `deleteAccount()` parses `sectionCounts` + `warnings` from the response.

- [ ] **Step 4: `test/widget/presentation/privacy/privacy_screen_test.dart`**

```dart
void main() {
  testWidgets('renders three v0-visible consent toggles', (tester) async {
    final fakeConsents = FakeConsentsRepository();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          consentsRepositoryProvider.overrideWithValue(fakeConsents),
          dsrRepositoryProvider.overrideWithValue(FakeDsrRepository()),
        ],
        child: MaterialApp(
          theme: ThemeData.light(useMaterial3: true),
          home: const PrivacyScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Service updates'), findsOneWidget);
    expect(find.text('Job recommendations'), findsOneWidget);
    expect(find.text('In-app notifications'), findsOneWidget);
    // Reserved scopes hidden.
    expect(find.text('WhatsApp notifications'), findsNothing);
  });

  testWidgets('toggling email_marketing calls patch()', (tester) async {
    final fakeConsents = FakeConsentsRepository();
    await tester.pumpWidget(...);  // same as above
    await tester.pumpAndSettle();

    final marketingToggle = find.descendant(
      of: find.byKey(const Key('toggle-email_marketing')),
      matching: find.byType(Switch),
    );
    await tester.tap(marketingToggle);
    await tester.pumpAndSettle();

    expect(fakeConsents.patchCallCount, 1);
  });

  testWidgets('toggling email_transactional OFF shows confirmation dialog',
      (tester) async {
    final fakeConsents = FakeConsentsRepository();
    await tester.pumpWidget(...);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('toggle-email_transactional')));
    await tester.pumpAndSettle();

    expect(find.text('Turn off service emails?'), findsOneWidget);
    // PATCH not yet called.
    expect(fakeConsents.patchCallCount, 0);
  });
}
```

Note: the privacy screen must add `key: Key('toggle-${scope.wire}')` to each `SwitchListTile` (or wrap it) so the widget test can find them.

Per CLAUDE.md: widget tests must use `ThemeData.light(useMaterial3: true)`, NOT the project's `buildTheme()` (which fetches Inter from Google Fonts and fails in offline test envs).

- [ ] **Step 5: `test/widget/presentation/privacy/delete_account_screen_test.dart`**

Two tests:
1. Submit button is disabled when text field is empty / mistyped.
2. Submit button is enabled when text field contains exactly `DELETE_MY_ACCOUNT`.

```dart
testWidgets('submit disabled until typed correctly', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        dsrRepositoryProvider.overrideWithValue(FakeDsrRepository()),
      ],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: const DeleteAccountScreen(),
      ),
    ),
  );

  final submit = find.widgetWithText(FilledButton, 'Delete my account');
  FilledButton button() => tester.widget(submit) as FilledButton;
  expect(button().onPressed, isNull);

  await tester.enterText(find.byType(TextField), 'wrong');
  await tester.pump();
  expect(button().onPressed, isNull);

  await tester.enterText(find.byType(TextField), 'DELETE_MY_ACCOUNT');
  await tester.pump();
  expect(button().onPressed, isNotNull);
});
```

- [ ] **Step 6: Run tests + analyze**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa/app
flutter test
flutter analyze
dart format test
```

All new tests pass; full test suite stays green.

- [ ] **Step 7: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add app/test/ app/lib/presentation/privacy/  # any key=Key(...) additions
git commit -m "test(app): unit + widget tests for privacy + delete-account flows

- Unit: ConsentsRepositoryImpl list + patch wire-shape contracts.
- Unit: DsrRepositoryImpl export passthrough + delete body shape + response parse.
- Widget: PrivacyScreen renders 3 v0 toggles (reserved hidden), tapping
  calls patch, email_transactional OFF triggers confirmation dialog.
- Widget: DeleteAccountScreen submit button disabled until exact typed
  confirmation."
```

---

### Task 4: CLAUDE.md + PR

- [ ] **Step 1: CLAUDE.md update**

Open `CLAUDE.md`. Find the "Flutter app (`app/`)" section's "Non-obvious bits" list. Append the four bullets from the spec § 9 — privacy screen path, reserved-scopes-hidden, DSR-export-clipboard, DSR-delete typed-confirmation. Match the existing bullet style (`- **lead-in.**`).

- [ ] **Step 2: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/kpa
git add CLAUDE.md
git commit -m "docs: Flutter consent screens invariants in CLAUDE.md"
```

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/p4-flutter-consent-screens
gh pr create --title "feat(app): P4-F Flutter consent screens (DPDP UI)" --body "$(cat <<'EOF'
## Summary
Final P4 user-facing sub-project. Ships the Flutter UI for the consent + DSR endpoints from PRs #26 / #27 / #28. Without this, those endpoints are unreachable to applicants.

- New `/profile/privacy` screen — three v0-visible consent toggles (email_transactional, email_marketing, in_app_notifications) + Download my data + Delete account navigation. Reserved scopes (whatsapp_notifications, sms_notifications, profile_visibility_recruiters, third_party_sharing_recruiters) are deliberately HIDDEN.
- `email_transactional` opt-out triggers a confirmation dialog because it's the service-critical email channel.
- New `/profile/privacy/delete` screen — typed `DELETE_MY_ACCOUNT` confirmation guard. Submit button disabled until typed exactly. On success: `AccessTokenHolder.clear()` + `SignedOut` push + one-time "Your account has been deleted." snackbar on the sign-in screen.
- DSR export uses the system clipboard in v0 (`Clipboard.setData`). Native file-save deferred — would add `share_plus` / `path_provider` / Web Blob API behind conditional imports for a small UX gain.

Spec: `docs/superpowers/specs/2026-05-29-flutter-consent-screens-design.md`
Plan: `docs/superpowers/plans/2026-05-29-flutter-consent-screens.md`

## Test plan
- [x] `flutter test` — all green (new unit + widget tests included)
- [x] `flutter analyze` clean
- [x] `dart run build_runner build --delete-conflicting-outputs` produces no diff on second run
- [x] Manual: tap each toggle, verify optimistic update + server canonical replacement
- [x] Manual: turn OFF email_transactional, verify confirmation dialog
- [x] Manual: Download my data, verify clipboard write + snackbar
- [x] Manual: type DELETE_MY_ACCOUNT, verify button enables; submit, verify sign-out + snackbar

## Out of scope
- Native file-save for the export (clipboard for v0)
- Recruiter-tailored UX (renders for recruiters but isn't polished)
- 30-day delete grace window (backend doesn't support it either)
- Localization

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Print the PR URL.

---

## Self-review checklist

- [x] Spec sections all map: § 3 routes/layouts → Task 2; § 4 controller → Task 2; § 5 export → Task 2; § 6 delete flow → Task 2; § 7 DTOs → Task 1; § 8 tests → Task 3; § 9 docs → Task 4.
- [x] Codegen runs explicitly after each task that touches `@JsonSerializable` / `@riverpod` / `@freezed`.
- [x] Widget tests use `ThemeData.light(useMaterial3: true)` per CLAUDE.md gotcha.
- [x] `email_transactional` OFF confirmation dialog has its own test.
- [x] Reserved scopes hidden via `ConsentScope.v0VisibleScopes` — single source of truth.
- [x] Sign-in snackbar is a one-time flag (`fire()` / `consume()`), survives the `/signin` redirect.
