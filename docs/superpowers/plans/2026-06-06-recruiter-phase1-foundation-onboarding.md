# Recruiter Phase 1 — Role-Aware Foundation + Onboarding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Flutter app role-aware (applicant vs recruiter shells) and let an applicant become a recruiter in-app via an employer-creation flow that re-renders into the recruiter shell live.

**Architecture:** Surface `UserRole` into the auth state so the `GoRouter` redirect branches synchronously. Two coexisting `StatefulShellRoute` subtrees (applicant under `/feed…`, recruiter under `/recruiter/…`) in one keep-alive router; the redirect gates access by role. A new `employers` data-layer feature backs the onboarding form (`POST /v1/employers`), and on success a `/v1/me` refresh flips the role and the redirect moves the user into the recruiter shell.

**Tech Stack:** Flutter, Riverpod 4.x (codegen), go_router 14.6, dio 5.7, json_serializable. Backend is unchanged in this phase (`POST /v1/employers` + `GET /v1/employers/me` already exist).

**Source spec:** `docs/superpowers/specs/2026-06-06-recruiter-employer-experience-design.md` (R1 §2, R2 §3).

---

## File Structure

**Create:**
- `app/lib/data/auth/user_role.dart` — `UserRole` enum (wire-format, with `unknown` sentinel).
- `app/lib/data/employers/employer_dto.dart` — mirrors `EmployerRead`.
- `app/lib/data/employers/employers_api.dart` — dio calls for `/v1/employers`.
- `app/lib/data/employers/employer_repository.dart` — abstract interface.
- `app/lib/data/employers/employer_repository_impl.dart` — impl + provider.
- `app/lib/presentation/auth/current_role_provider.dart` — derives `UserRole?` from auth state.
- `app/lib/presentation/routing/role_redirect.dart` — pure role-routing decision (unit-testable).
- `app/lib/presentation/widgets/kpa_recruiter_shell_scaffold.dart` — recruiter bottom-nav scaffold.
- `app/lib/presentation/recruiter/recruiter_dashboard_screen.dart` — placeholder (filled in Phase 2/R3).
- `app/lib/presentation/recruiter/recruiter_jobs_screen.dart` — placeholder.
- `app/lib/presentation/recruiter/recruiter_employer_screen.dart` — placeholder.
- `app/lib/presentation/recruiter/recruiter_profile_screen.dart` — placeholder.
- `app/lib/presentation/onboarding/employer_onboarding_controller.dart` — submit logic.
- `app/lib/presentation/onboarding/employer_onboarding_screen.dart` — the form.

**Modify:**
- `app/lib/data/auth/auth_state.dart` — add `role` to `SignedIn`.
- `app/lib/data/auth/auth_repository_impl.dart` — set `role` at both `SignedIn(...)` sites.
- `app/lib/presentation/routing/routes.dart` — recruiter + onboarding path constants.
- `app/lib/presentation/routing/router.dart` — recruiter subtree + role-aware redirect.
- `app/lib/presentation/profile/profile_screen.dart` — role-gated "I'm hiring" CTA.

**Test:**
- `app/test/unit/data/auth/user_role_test.dart`
- `app/test/unit/data/auth/auth_repository_impl_test.dart` (extend)
- `app/test/unit/data/employers/employer_dto_test.dart`
- `app/test/unit/data/employers/employer_repository_impl_test.dart`
- `app/test/unit/presentation/routing/role_redirect_test.dart`
- `app/test/unit/presentation/onboarding/employer_onboarding_controller_test.dart`
- `app/test/widget/recruiter_shell_scaffold_test.dart`
- `app/test/widget/employer_onboarding_screen_test.dart`

**Commands (run from `app/`):**
- Codegen after touching `@JsonSerializable`/`@JsonEnum`/`@riverpod`: `dart run build_runner build --delete-conflicting-outputs`
- Test one file: `flutter test test/unit/data/auth/user_role_test.dart`
- Analyze: `flutter analyze`

---

## Task 1: `UserRole` data-layer enum

**Files:**
- Create: `app/lib/data/auth/user_role.dart`
- Test: `app/test/unit/data/auth/user_role_test.dart`

- [ ] **Step 1: Write the enum**

```dart
// app/lib/data/auth/user_role.dart
import 'package:json_annotation/json_annotation.dart';

/// Mirrors the backend UserRole StrEnum (api/src/kpa/db/models.py:UserRole).
/// `unknown` is the forward-compat sentinel for a wire value this client
/// does not yet know about — never sent, only parsed.
@JsonEnum(alwaysCreate: true)
enum UserRole {
  @JsonValue('applicant')
  applicant,
  @JsonValue('recruiter')
  recruiter,
  @JsonValue('admin')
  admin,
  @JsonValue('unknown')
  unknown;

  /// Parse a wire string; anything unrecognized → [UserRole.unknown].
  static UserRole fromWire(String raw) => switch (raw) {
        'applicant' => UserRole.applicant,
        'recruiter' => UserRole.recruiter,
        'admin' => UserRole.admin,
        _ => UserRole.unknown,
      };

  /// True for roles that use the recruiter shell (recruiter + admin).
  bool get usesRecruiterShell =>
      this == UserRole.recruiter || this == UserRole.admin;
}
```

- [ ] **Step 2: Write the failing test**

```dart
// app/test/unit/data/auth/user_role_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/user_role.dart';

void main() {
  test('fromWire maps known roles', () {
    expect(UserRole.fromWire('applicant'), UserRole.applicant);
    expect(UserRole.fromWire('recruiter'), UserRole.recruiter);
    expect(UserRole.fromWire('admin'), UserRole.admin);
  });

  test('fromWire maps unknown values to the sentinel', () {
    expect(UserRole.fromWire('superuser'), UserRole.unknown);
    expect(UserRole.fromWire(''), UserRole.unknown);
  });

  test('usesRecruiterShell true for recruiter and admin only', () {
    expect(UserRole.recruiter.usesRecruiterShell, isTrue);
    expect(UserRole.admin.usesRecruiterShell, isTrue);
    expect(UserRole.applicant.usesRecruiterShell, isFalse);
    expect(UserRole.unknown.usesRecruiterShell, isFalse);
  });
}
```

- [ ] **Step 3: Run codegen + test**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/data/auth/user_role_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 4: Commit**

```bash
git add app/lib/data/auth/user_role.dart app/lib/data/auth/user_role.g.dart app/test/unit/data/auth/user_role_test.dart
git commit -m "feat(app): UserRole data-layer enum with unknown sentinel"
```

---

## Task 2: Add `role` to `SignedIn` and populate it at every construction site

**Files:**
- Modify: `app/lib/data/auth/auth_state.dart`
- Modify: `app/lib/data/auth/auth_repository_impl.dart:81-85` and `:114-118`
- Test: `app/test/unit/data/auth/auth_repository_impl_test.dart` (extend existing)

- [ ] **Step 1: Add the field to `SignedIn`**

In `app/lib/data/auth/auth_state.dart`, add the import and extend `SignedIn`:

```dart
import 'package:kpa_app/data/auth/user_role.dart';
```

```dart
class SignedIn extends AuthState {
  const SignedIn({
    required this.userId,
    required this.email,
    required this.role,
    this.displayName,
  });

  final String userId;
  final String email;
  final UserRole role;
  final String? displayName;
}
```

- [ ] **Step 2: Set `role` at both construction sites**

In `auth_repository_impl.dart`, the OAuth-exchange site (`_exchangeGoogleIdToken`):

```dart
      final signedIn = SignedIn(
        userId: dto.user.id,
        email: dto.user.email,
        role: UserRole.fromWire(dto.user.role),
        displayName: dto.user.displayName,
      );
```

The refresh site (`refreshSession`, which already fetches `/v1/me`):

```dart
      final signedIn = SignedIn(
        userId: meDto.id,
        email: meDto.email,
        role: UserRole.fromWire(meDto.role),
        displayName: meDto.displayName,
      );
```

Add `import 'package:kpa_app/data/auth/user_role.dart';` to `auth_repository_impl.dart` if not present.

- [ ] **Step 3: Extend the existing repo-impl test to assert role propagation**

Append to `app/test/unit/data/auth/auth_repository_impl_test.dart` (inside `main()`). The existing test file already builds an `AuthRepositoryImpl` with mock interceptors; add a test that the OAuth exchange surfaces `role`:

```dart
  test('OAuth exchange populates SignedIn.role from the user payload', () async {
    // Arrange a MockInterceptor returning a recruiter role on the exchange.
    // (Mirror the existing exchange test's setup; only the asserted field is new.)
    final result = await repo.completeWebSignIn('fake-id-token');
    expect(result.role, UserRole.recruiter);
  });
```

Add `import 'package:kpa_app/data/auth/user_role.dart';` to the test. Wire the `MockInterceptor` stub for `/v1/auth/oauth/google` to return `{"access_token":"a","refresh_token":"r","user":{"id":"u1","email":"e@e.com","role":"recruiter"}}` following the file's existing stub style.

- [ ] **Step 4: Run codegen + the auth tests**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/data/auth/auth_repository_impl_test.dart`
Expected: PASS (existing tests + the new role assertion). If any other test constructs `SignedIn(...)` without `role`, the analyzer/test will flag it — add `role: UserRole.applicant` to those fixtures.

- [ ] **Step 5: Fix any remaining `SignedIn(` callers**

Run: `flutter analyze`
Expected: no errors. Fix any "missing required argument 'role'" by passing the role the fixture intends (default `UserRole.applicant`).

- [ ] **Step 6: Commit**

```bash
git add app/lib/data/auth/auth_state.dart app/lib/data/auth/auth_repository_impl.dart app/test/unit/data/auth/auth_repository_impl_test.dart
git commit -m "feat(app): carry UserRole on SignedIn from both sign-in paths"
```

---

## Task 3: `currentRoleProvider`

**Files:**
- Create: `app/lib/presentation/auth/current_role_provider.dart`
- Test: covered indirectly by Task 5 + Task 10 widget tests (a pure derivation; no dedicated unit test needed since it is a one-line selector — but add a trivial test for safety).
- Test: `app/test/unit/presentation/auth/current_role_provider_test.dart`

- [ ] **Step 1: Write the provider**

```dart
// app/lib/presentation/auth/current_role_provider.dart
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'current_role_provider.g.dart';

/// The signed-in user's role, or null when not signed in.
@riverpod
UserRole? currentRole(Ref ref) {
  final auth = ref.watch(authStateProvider);
  return auth is SignedIn ? auth.role : null;
}
```

- [ ] **Step 2: Write the failing test**

```dart
// app/test/unit/presentation/auth/current_role_provider_test.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/auth/current_role_provider.dart';

void main() {
  test('null when signed out, role when signed in', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(container.read(currentRoleProvider), isNull);

    container.read(authStateProvider.notifier).set(
          const SignedIn(userId: 'u1', email: 'e@e.com', role: UserRole.recruiter),
        );
    expect(container.read(currentRoleProvider), UserRole.recruiter);
  });
}
```

- [ ] **Step 3: Run codegen + test**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/presentation/auth/current_role_provider_test.dart`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/auth/current_role_provider.dart app/lib/presentation/auth/current_role_provider.g.dart app/test/unit/presentation/auth/current_role_provider_test.dart
git commit -m "feat(app): currentRoleProvider derives role from auth state"
```

---

## Task 4: Route constants + recruiter shell scaffold + placeholder screens

**Files:**
- Modify: `app/lib/presentation/routing/routes.dart`
- Create: `app/lib/presentation/widgets/kpa_recruiter_shell_scaffold.dart`
- Create: `app/lib/presentation/recruiter/recruiter_dashboard_screen.dart`
- Create: `app/lib/presentation/recruiter/recruiter_jobs_screen.dart`
- Create: `app/lib/presentation/recruiter/recruiter_employer_screen.dart`
- Create: `app/lib/presentation/recruiter/recruiter_profile_screen.dart`
- Test: `app/test/widget/recruiter_shell_scaffold_test.dart`

- [ ] **Step 1: Add route constants**

Append to `app/lib/presentation/routing/routes.dart` inside `abstract final class Routes`:

```dart
  // Onboarding (applicant → recruiter).
  static const onboardingEmployer = '/onboarding/employer';

  // Recruiter shell.
  static const recruiterDashboard = '/recruiter/dashboard';
  static const recruiterJobs = '/recruiter/jobs';
  static const recruiterEmployer = '/recruiter/employer';
  static const recruiterProfile = '/recruiter/profile';
```

- [ ] **Step 2: Create the four placeholder screens**

Each placeholder renders a labeled `Scaffold` so routes resolve and the scaffold test can find them. Example for the dashboard (repeat with the obvious name/title swaps for jobs/employer/profile):

```dart
// app/lib/presentation/recruiter/recruiter_dashboard_screen.dart
import 'package:flutter/material.dart';

class RecruiterDashboardScreen extends StatelessWidget {
  const RecruiterDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: Text('Recruiter Dashboard')),
    );
  }
}
```

```dart
// app/lib/presentation/recruiter/recruiter_jobs_screen.dart
import 'package:flutter/material.dart';

class RecruiterJobsScreen extends StatelessWidget {
  const RecruiterJobsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('Recruiter Jobs')));
  }
}
```

```dart
// app/lib/presentation/recruiter/recruiter_employer_screen.dart
import 'package:flutter/material.dart';

class RecruiterEmployerScreen extends StatelessWidget {
  const RecruiterEmployerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('Employer')));
  }
}
```

```dart
// app/lib/presentation/recruiter/recruiter_profile_screen.dart
import 'package:flutter/material.dart';

class RecruiterProfileScreen extends StatelessWidget {
  const RecruiterProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('Recruiter Profile')));
  }
}
```

- [ ] **Step 3: Create the recruiter shell scaffold**

Mirror `kpa_shell_scaffold.dart` exactly; only the destinations differ.

```dart
// app/lib/presentation/widgets/kpa_recruiter_shell_scaffold.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class KpaRecruiterShellScaffold extends StatelessWidget {
  const KpaRecruiterShellScaffold({required this.shell, super.key});

  final StatefulNavigationShell shell;

  static const _items = [
    NavigationDestination(
      icon: Icon(Icons.dashboard_outlined),
      selectedIcon: Icon(Icons.dashboard),
      label: 'Dashboard',
    ),
    NavigationDestination(
      icon: Icon(Icons.work_outline),
      selectedIcon: Icon(Icons.work),
      label: 'Jobs',
    ),
    NavigationDestination(
      icon: Icon(Icons.business_outlined),
      selectedIcon: Icon(Icons.business),
      label: 'Employer',
    ),
    NavigationDestination(
      icon: Icon(Icons.person_outline),
      selectedIcon: Icon(Icons.person),
      label: 'Profile',
    ),
  ];

  void _onTap(int i) {
    if (i == shell.currentIndex) {
      shell.goBranch(i, initialLocation: true);
    } else {
      shell.goBranch(i);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: shell,
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

- [ ] **Step 4: Write the failing scaffold widget test**

```dart
// app/test/widget/recruiter_shell_scaffold_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_dashboard_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_employer_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_profile_screen.dart';
import 'package:kpa_app/presentation/widgets/kpa_recruiter_shell_scaffold.dart';

void main() {
  testWidgets('recruiter shell shows four tabs and switches branches',
      (tester) async {
    final router = GoRouter(
      initialLocation: '/recruiter/dashboard',
      routes: [
        StatefulShellRoute.indexedStack(
          builder: (_, __, shell) => KpaRecruiterShellScaffold(shell: shell),
          branches: [
            StatefulShellBranch(routes: [
              GoRoute(
                path: '/recruiter/dashboard',
                builder: (_, __) => const RecruiterDashboardScreen(),
              ),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(
                path: '/recruiter/jobs',
                builder: (_, __) => const RecruiterJobsScreen(),
              ),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(
                path: '/recruiter/employer',
                builder: (_, __) => const RecruiterEmployerScreen(),
              ),
            ]),
            StatefulShellBranch(routes: [
              GoRoute(
                path: '/recruiter/profile',
                builder: (_, __) => const RecruiterProfileScreen(),
              ),
            ]),
          ],
        ),
      ],
    );

    await tester.pumpWidget(
      MaterialApp.router(
        theme: ThemeData.light(useMaterial3: true),
        routerConfig: router,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Dashboard'), findsOneWidget);
    expect(find.text('Jobs'), findsOneWidget);
    expect(find.text('Employer'), findsOneWidget);
    expect(find.text('Recruiter Dashboard'), findsOneWidget);

    await tester.tap(find.text('Jobs'));
    await tester.pumpAndSettle();
    expect(find.text('Recruiter Jobs'), findsOneWidget);
  });
}
```

- [ ] **Step 5: Run the test**

Run: `flutter test test/widget/recruiter_shell_scaffold_test.dart`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/lib/presentation/routing/routes.dart app/lib/presentation/widgets/kpa_recruiter_shell_scaffold.dart app/lib/presentation/recruiter/ app/test/widget/recruiter_shell_scaffold_test.dart
git commit -m "feat(app): recruiter shell scaffold + placeholder screens + route constants"
```

---

## Task 5: Role-aware redirect (pure helper) + recruiter subtree in the router

**Files:**
- Create: `app/lib/presentation/routing/role_redirect.dart`
- Modify: `app/lib/presentation/routing/router.dart`
- Test: `app/test/unit/presentation/routing/role_redirect_test.dart`

- [ ] **Step 1: Write the pure redirect helper**

Extracting the role decision into a pure function (mirrors the existing `safeNextLocation` extraction) keeps it unit-testable without a live router.

```dart
// app/lib/presentation/routing/role_redirect.dart
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/routing/routes.dart';

/// True if [loc] belongs to the recruiter shell subtree.
bool isRecruiterLocation(String loc) => loc.startsWith('/recruiter');

/// True if [loc] is an applicant-shell location (the four applicant tabs
/// and their nested routes). Onboarding is treated as applicant-only.
bool isApplicantShellLocation(String loc) =>
    loc.startsWith(Routes.feed) ||
    loc.startsWith(Routes.saved) ||
    loc.startsWith(Routes.applications) ||
    loc.startsWith(Routes.profile);

/// Returns the path to redirect a SIGNED-IN user to based on their [role] and
/// current [loc], or null to stay put. Caller handles the signed-out case.
String? roleAwareRedirect({required UserRole role, required String loc}) {
  if (role.usesRecruiterShell) {
    // A recruiter on an applicant-only location (incl. onboarding) → dashboard.
    if (isApplicantShellLocation(loc) || loc == Routes.onboardingEmployer) {
      return Routes.recruiterDashboard;
    }
    return null;
  }
  // Applicant on a recruiter location → feed.
  if (isRecruiterLocation(loc)) return Routes.feed;
  return null;
}
```

- [ ] **Step 2: Write the failing test**

```dart
// app/test/unit/presentation/routing/role_redirect_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/routing/role_redirect.dart';
import 'package:kpa_app/presentation/routing/routes.dart';

void main() {
  test('recruiter on applicant route is bounced to dashboard', () {
    expect(
      roleAwareRedirect(role: UserRole.recruiter, loc: Routes.feed),
      Routes.recruiterDashboard,
    );
    expect(
      roleAwareRedirect(role: UserRole.recruiter, loc: '/profile/resume'),
      Routes.recruiterDashboard,
    );
    expect(
      roleAwareRedirect(
          role: UserRole.recruiter, loc: Routes.onboardingEmployer),
      Routes.recruiterDashboard,
    );
  });

  test('recruiter on a recruiter route stays', () {
    expect(
      roleAwareRedirect(
          role: UserRole.recruiter, loc: Routes.recruiterJobs),
      isNull,
    );
  });

  test('applicant on a recruiter route is bounced to feed', () {
    expect(
      roleAwareRedirect(
          role: UserRole.applicant, loc: Routes.recruiterDashboard),
      Routes.feed,
    );
  });

  test('applicant on an applicant route stays', () {
    expect(roleAwareRedirect(role: UserRole.applicant, loc: Routes.feed),
        isNull);
    expect(
        roleAwareRedirect(
            role: UserRole.applicant, loc: Routes.onboardingEmployer),
        isNull);
  });

  test('admin uses the recruiter shell', () {
    expect(roleAwareRedirect(role: UserRole.admin, loc: Routes.feed),
        Routes.recruiterDashboard);
  });
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `flutter test test/unit/presentation/routing/role_redirect_test.dart`
Expected: FAIL until `role_redirect.dart` compiles (it will pass once Step 1's file exists — run after Step 1).
Expected after Step 1 present: PASS.

- [ ] **Step 4: Wire the recruiter subtree + redirect into `router.dart`**

Add imports:

```dart
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/onboarding/employer_onboarding_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_dashboard_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_employer_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_profile_screen.dart';
import 'package:kpa_app/presentation/routing/role_redirect.dart';
import 'package:kpa_app/presentation/widgets/kpa_recruiter_shell_scaffold.dart';
```

In the `redirect` callback, after the existing `SignedOut`/`SignedIn && loc==signIn` blocks and before `return null;`, add the role gate:

```dart
      if (auth is SignedIn) {
        final r = roleAwareRedirect(role: auth.role, loc: loc);
        if (r != null) return r;
      }
```

Add the onboarding route (top-level, alongside `/signin`):

```dart
      GoRoute(
        path: Routes.onboardingEmployer,
        builder: (_, __) => const EmployerOnboardingScreen(),
      ),
```

Add a second `StatefulShellRoute.indexedStack` for the recruiter shell, after the existing applicant `StatefulShellRoute`:

```dart
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) =>
            KpaRecruiterShellScaffold(shell: shell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.recruiterDashboard,
              builder: (_, __) => const RecruiterDashboardScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.recruiterJobs,
              builder: (_, __) => const RecruiterJobsScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.recruiterEmployer,
              builder: (_, __) => const RecruiterEmployerScreen(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: Routes.recruiterProfile,
              builder: (_, __) => const RecruiterProfileScreen(),
            ),
          ]),
        ],
      ),
```

NOTE: `Routes.onboardingEmployer` import of `EmployerOnboardingScreen` requires Task 9 to have created the screen. If executing strictly in order, temporarily stub the onboarding route to `const SizedBox()` and replace it in Task 9. Subagent-driven execution should run Task 9 before wiring this route, OR accept a one-line follow-up edit in Task 9.

- [ ] **Step 5: Run codegen + router tests + analyze**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/presentation/routing/ && flutter analyze`
Expected: role_redirect + safe_next_location tests PASS; no analyzer errors.

- [ ] **Step 6: Commit**

```bash
git add app/lib/presentation/routing/ app/test/unit/presentation/routing/role_redirect_test.dart
git commit -m "feat(app): role-aware redirect + recruiter shell subtree in router"
```

---

## Task 6: `EmployerDto`

**Files:**
- Create: `app/lib/data/employers/employer_dto.dart`
- Test: `app/test/unit/data/employers/employer_dto_test.dart`

- [ ] **Step 1: Write the DTO**

Mirrors `EmployerRead` (`api/src/kpa/routes/employers.py`): `{id, name, gst?, verified_at?, created_at}`.

```dart
// app/lib/data/employers/employer_dto.dart
import 'package:json_annotation/json_annotation.dart';

part 'employer_dto.g.dart';

/// Mirrors EmployerRead (api/src/kpa/routes/employers.py).
@JsonSerializable()
class EmployerDto {
  const EmployerDto({
    required this.id,
    required this.name,
    required this.createdAt,
    this.gst,
    this.verifiedAt,
  });

  factory EmployerDto.fromJson(Map<String, dynamic> json) =>
      _$EmployerDtoFromJson(json);

  final String id;
  final String name;
  final String? gst;

  @JsonKey(name: 'verified_at')
  final DateTime? verifiedAt;

  @JsonKey(name: 'created_at')
  final DateTime createdAt;

  bool get isVerified => verifiedAt != null;

  Map<String, dynamic> toJson() => _$EmployerDtoToJson(this);
}
```

- [ ] **Step 2: Write the failing test**

```dart
// app/test/unit/data/employers/employer_dto_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';

void main() {
  test('parses a verified employer', () {
    final dto = EmployerDto.fromJson({
      'id': 'emp1',
      'name': 'Acme',
      'gst': '22AAAAA0000A1Z5',
      'verified_at': '2026-01-01T00:00:00Z',
      'created_at': '2026-01-01T00:00:00Z',
    });
    expect(dto.name, 'Acme');
    expect(dto.gst, '22AAAAA0000A1Z5');
    expect(dto.isVerified, isTrue);
  });

  test('parses an unverified employer with null gst', () {
    final dto = EmployerDto.fromJson({
      'id': 'emp2',
      'name': 'Beta',
      'gst': null,
      'verified_at': null,
      'created_at': '2026-01-01T00:00:00Z',
    });
    expect(dto.gst, isNull);
    expect(dto.isVerified, isFalse);
  });
}
```

- [ ] **Step 3: Run codegen + test**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/data/employers/employer_dto_test.dart`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/lib/data/employers/employer_dto.dart app/lib/data/employers/employer_dto.g.dart app/test/unit/data/employers/employer_dto_test.dart
git commit -m "feat(app): EmployerDto mirroring EmployerRead"
```

---

## Task 7: Employers API + repository

**Files:**
- Create: `app/lib/data/employers/employers_api.dart`
- Create: `app/lib/data/employers/employer_repository.dart`
- Create: `app/lib/data/employers/employer_repository_impl.dart`
- Test: `app/test/unit/data/employers/employer_repository_impl_test.dart`

- [ ] **Step 1: Write the API class**

```dart
// app/lib/data/employers/employers_api.dart
import 'package:dio/dio.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';

class EmployersApi {
  EmployersApi(this._dio);
  final Dio _dio;

  Future<EmployerDto> create({required String name, String? gst}) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/employers',
      data: {'name': name, if (gst != null && gst.isNotEmpty) 'gst': gst},
    );
    return EmployerDto.fromJson(res.data!);
  }

  Future<List<EmployerDto>> listMine() async {
    final res = await _dio.get<List<dynamic>>('/v1/employers/me');
    return (res.data ?? [])
        .map((e) => EmployerDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
```

- [ ] **Step 2: Write the repository interface**

```dart
// app/lib/data/employers/employer_repository.dart
import 'package:kpa_app/data/employers/employer_dto.dart';

abstract interface class EmployerRepository {
  Future<EmployerDto> createEmployer({required String name, String? gst});
  Future<List<EmployerDto>> listMyEmployers();
}
```

- [ ] **Step 3: Write the impl + provider**

```dart
// app/lib/data/employers/employer_repository_impl.dart
import 'package:dio/dio.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository.dart';
import 'package:kpa_app/data/employers/employers_api.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'employer_repository_impl.g.dart';

class EmployerRepositoryImpl implements EmployerRepository {
  EmployerRepositoryImpl(this._api);
  final EmployersApi _api;

  @override
  Future<EmployerDto> createEmployer({required String name, String? gst}) async {
    try {
      return await _api.create(name: name, gst: gst);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<List<EmployerDto>> listMyEmployers() async {
    try {
      return await _api.listMine();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
EmployerRepository employerRepository(Ref ref) =>
    EmployerRepositoryImpl(EmployersApi(ref.read(dioProvider)));
```

- [ ] **Step 4: Write the failing repo-impl test**

Use the established `MockInterceptor` helper (`test/helpers/mock_interceptor.dart`) the same way `me_repository_impl_test.dart` does.

```dart
// app/test/unit/data/employers/employer_repository_impl_test.dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/employers/employer_repository_impl.dart';
import 'package:kpa_app/data/employers/employers_api.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import '../../../helpers/mock_interceptor.dart';

EmployerRepositoryImpl _repo(MockInterceptor mock) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test'))
    ..interceptors.add(mock);
  return EmployerRepositoryImpl(EmployersApi(dio));
}

void main() {
  test('createEmployer returns the parsed employer on 201', () async {
    final repo = _repo(MockInterceptor((options, handler) {
      handler.resolve(Response(
        requestOptions: options,
        statusCode: 201,
        data: {
          'id': 'emp1',
          'name': 'Acme',
          'gst': null,
          'verified_at': null,
          'created_at': '2026-01-01T00:00:00Z',
        },
      ));
    }));
    final emp = await repo.createEmployer(name: 'Acme');
    expect(emp.id, 'emp1');
    expect(emp.isVerified, isFalse);
  });

  test('createEmployer surfaces 409 employer_name_taken as ApiException',
      () async {
    final repo = _repo(MockInterceptor((options, handler) {
      handler.reject(DioException(
        requestOptions: options,
        response: Response(
          requestOptions: options,
          statusCode: 409,
          data: {'detail': 'employer_name_taken'},
        ),
        type: DioExceptionType.badResponse,
      ));
    }));
    await expectLater(
      repo.createEmployer(name: 'Acme'),
      throwsA(isA<ApiException>()),
    );
  });
}
```

NOTE: confirm the `MockInterceptor` constructor signature in `test/helpers/mock_interceptor.dart` and the exact `ApiException` type/slug surface in `lib/core/error/exceptions.dart` + `error_mapping.dart`; adjust the `throwsA(isA<...>())` matcher and the handler-callback shape to match the helper actually in the repo (the existing `me_repository_impl_test.dart` is the reference).

- [ ] **Step 5: Run codegen + test**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/data/employers/employer_repository_impl_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add app/lib/data/employers/ app/test/unit/data/employers/employer_repository_impl_test.dart
git commit -m "feat(app): employers API + repository (create, listMine)"
```

---

## Task 8: Onboarding controller

**Files:**
- Create: `app/lib/presentation/onboarding/employer_onboarding_controller.dart`
- Test: `app/test/unit/presentation/onboarding/employer_onboarding_controller_test.dart`

- [ ] **Step 1: Write the controller**

On success it creates the employer, then refreshes the session so `SignedIn.role` flips to `recruiter` (the redirect then moves the user into the recruiter shell). Returns the created `EmployerDto`.

```dart
// app/lib/presentation/onboarding/employer_onboarding_controller.dart
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'employer_onboarding_controller.g.dart';

@riverpod
class EmployerOnboardingController extends _$EmployerOnboardingController {
  @override
  FutureOr<EmployerDto?> build() => null;

  /// Create the employer and flip the session role to recruiter.
  /// Throws (surfaced via AsyncValue.error) on API failure so the form can
  /// show the 409 / network message.
  Future<void> submit({required String name, String? gst}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(employerRepositoryProvider);
      final employer = await repo.createEmployer(name: name, gst: gst);
      // Re-fetch /v1/me via refresh so SignedIn.role becomes recruiter and
      // the role-aware redirect re-renders into the recruiter shell.
      await ref.read(authRepositoryProvider).refreshSession();
      return employer;
    });
  }
}
```

- [ ] **Step 2: Write the failing test**

```dart
// app/test/unit/presentation/onboarding/employer_onboarding_controller_test.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/auth_repository.dart';
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository.dart';
import 'package:kpa_app/data/employers/employer_repository_impl.dart';
import 'package:kpa_app/presentation/onboarding/employer_onboarding_controller.dart';

class _FakeEmployerRepo implements EmployerRepository {
  int createCalls = 0;
  @override
  Future<EmployerDto> createEmployer({required String name, String? gst}) async {
    createCalls++;
    return EmployerDto(
      id: 'emp1',
      name: name,
      createdAt: DateTime.utc(2026, 1, 1),
    );
  }

  @override
  Future<List<EmployerDto>> listMyEmployers() async => [];
}

class _ThrowingEmployerRepo implements EmployerRepository {
  @override
  Future<EmployerDto> createEmployer({required String name, String? gst}) async {
    throw const ApiException(slug: 'employer_name_taken', detail: 'taken');
  }

  @override
  Future<List<EmployerDto>> listMyEmployers() async => [];
}

class _FakeAuthRepo implements AuthRepository {
  int refreshCalls = 0;
  @override
  AuthState get current => const SignedOut();
  @override
  Future<SignedIn> refreshSession() async {
    refreshCalls++;
    return const SignedIn(
        userId: 'u1', email: 'e@e.com', role: UserRole.recruiter);
  }

  @override
  Future<SignedIn> signInWithGoogle() => throw UnimplementedError();
  @override
  Future<SignedIn> completeWebSignIn(String idToken) =>
      throw UnimplementedError();
  @override
  Future<String> refreshAccessTokenForInterceptor() =>
      throw UnimplementedError();
  @override
  Future<void> signOut() async {}
}

void main() {
  test('submit creates employer then refreshes session', () async {
    final empRepo = _FakeEmployerRepo();
    final authRepo = _FakeAuthRepo();
    final container = ProviderContainer(overrides: [
      employerRepositoryProvider.overrideWithValue(empRepo),
      authRepositoryProvider.overrideWithValue(authRepo),
    ]);
    addTearDown(container.dispose);

    await container
        .read(employerOnboardingControllerProvider.notifier)
        .submit(name: 'Acme');

    expect(empRepo.createCalls, 1);
    expect(authRepo.refreshCalls, 1);
    expect(
      container.read(employerOnboardingControllerProvider).value?.name,
      'Acme',
    );
  });

  test('submit surfaces API error and does NOT refresh', () async {
    final authRepo = _FakeAuthRepo();
    final container = ProviderContainer(overrides: [
      employerRepositoryProvider.overrideWithValue(_ThrowingEmployerRepo()),
      authRepositoryProvider.overrideWithValue(authRepo),
    ]);
    addTearDown(container.dispose);

    await container
        .read(employerOnboardingControllerProvider.notifier)
        .submit(name: 'Acme');

    expect(container.read(employerOnboardingControllerProvider).hasError,
        isTrue);
    expect(authRepo.refreshCalls, 0);
  });
}
```

NOTE: confirm the `authRepositoryProvider` name/signature in `lib/data/auth/auth_repository_provider.dart` and that `ApiException` takes `slug`/`detail` (see `lib/core/error/exceptions.dart`); adjust the fake + constructor to match.

- [ ] **Step 3: Run codegen + test**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/presentation/onboarding/employer_onboarding_controller_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 4: Commit**

```bash
git add app/lib/presentation/onboarding/employer_onboarding_controller.dart app/lib/presentation/onboarding/employer_onboarding_controller.g.dart app/test/unit/presentation/onboarding/employer_onboarding_controller_test.dart
git commit -m "feat(app): employer onboarding controller (create + role flip)"
```

---

## Task 9: Onboarding screen

**Files:**
- Create: `app/lib/presentation/onboarding/employer_onboarding_screen.dart`
- Test: `app/test/widget/employer_onboarding_screen_test.dart`

- [ ] **Step 1: Write the screen**

```dart
// app/lib/presentation/onboarding/employer_onboarding_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/onboarding/employer_onboarding_controller.dart';

class EmployerOnboardingScreen extends ConsumerStatefulWidget {
  const EmployerOnboardingScreen({super.key});

  @override
  ConsumerState<EmployerOnboardingScreen> createState() =>
      _EmployerOnboardingScreenState();
}

class _EmployerOnboardingScreenState
    extends ConsumerState<EmployerOnboardingScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _gst = TextEditingController();

  @override
  void dispose() {
    _name.dispose();
    _gst.dispose();
    super.dispose();
  }

  String? _validateName(String? v) {
    final s = (v ?? '').trim();
    if (s.length < 2) return 'Enter your company name (min 2 characters)';
    if (s.length > 200) return 'Company name is too long';
    return null;
  }

  String? _validateGst(String? v) {
    final s = (v ?? '').trim();
    if (s.isEmpty) return null; // optional
    if (s.length != 15) return 'GSTIN must be exactly 15 characters';
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    await ref.read(employerOnboardingControllerProvider.notifier).submit(
          name: _name.text.trim(),
          gst: _gst.text.trim().isEmpty ? null : _gst.text.trim(),
        );
    // On success the role flips and the router redirect moves us to the
    // recruiter dashboard; nothing to navigate here.
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(employerOnboardingControllerProvider);
    final isLoading = state.isLoading;

    ref.listen(employerOnboardingControllerProvider, (_, next) {
      if (next.hasError && context.mounted) {
        final err = next.error;
        final msg = err is ApiException && err.slug == 'employer_name_taken'
            ? 'That company name is already registered.'
            : 'Could not create employer. Please try again.';
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(content: Text(msg)));
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Set up your company')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Tell us about your company to start posting jobs.',
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(
                  labelText: 'Company name',
                  border: OutlineInputBorder(),
                ),
                validator: _validateName,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _gst,
                decoration: const InputDecoration(
                  labelText: 'GSTIN (optional)',
                  border: OutlineInputBorder(),
                ),
                validator: _validateGst,
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: isLoading ? null : _submit,
                child: isLoading
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Create company'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Write the failing widget test**

```dart
// app/test/widget/employer_onboarding_screen_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/auth_repository.dart';
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository.dart';
import 'package:kpa_app/data/employers/employer_repository_impl.dart';
import 'package:kpa_app/presentation/onboarding/employer_onboarding_screen.dart';

class _FakeEmployerRepo implements EmployerRepository {
  @override
  Future<EmployerDto> createEmployer({required String name, String? gst}) async =>
      EmployerDto(id: 'e1', name: name, createdAt: DateTime.utc(2026));
  @override
  Future<List<EmployerDto>> listMyEmployers() async => [];
}

class _FakeAuthRepo implements AuthRepository {
  @override
  AuthState get current => const SignedOut();
  @override
  Future<SignedIn> refreshSession() async =>
      const SignedIn(userId: 'u1', email: 'e@e.com', role: UserRole.recruiter);
  @override
  Future<SignedIn> signInWithGoogle() => throw UnimplementedError();
  @override
  Future<SignedIn> completeWebSignIn(String idToken) =>
      throw UnimplementedError();
  @override
  Future<String> refreshAccessTokenForInterceptor() =>
      throw UnimplementedError();
  @override
  Future<void> signOut() async {}
}

void main() {
  testWidgets('validates empty name, then submits', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          employerRepositoryProvider.overrideWithValue(_FakeEmployerRepo()),
          authRepositoryProvider.overrideWithValue(_FakeAuthRepo()),
        ],
        child: const MaterialApp(home: EmployerOnboardingScreen()),
      ),
    );

    await tester.tap(find.text('Create company'));
    await tester.pump();
    expect(find.textContaining('min 2 characters'), findsOneWidget);

    await tester.enterText(
        find.widgetWithText(TextFormField, 'Company name'), 'Acme');
    await tester.tap(find.text('Create company'));
    await tester.pumpAndSettle();
    // No validation error remains.
    expect(find.textContaining('min 2 characters'), findsNothing);
  });
}
```

- [ ] **Step 3: Run codegen + test**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/widget/employer_onboarding_screen_test.dart`
Expected: PASS.

- [ ] **Step 4: Replace the router's onboarding stub (if Task 5 stubbed it)**

If Task 5 used a `const SizedBox()` stub for the onboarding route, replace it now with `const EmployerOnboardingScreen()` and ensure the import is present. Run `flutter analyze`.

- [ ] **Step 5: Commit**

```bash
git add app/lib/presentation/onboarding/employer_onboarding_screen.dart app/lib/presentation/routing/router.dart app/test/widget/employer_onboarding_screen_test.dart
git commit -m "feat(app): employer onboarding screen + route wiring"
```

---

## Task 10: Role-gated "I'm hiring" CTA on the Profile screen

**Files:**
- Modify: `app/lib/presentation/profile/profile_screen.dart`
- Test: `app/test/widget/profile_screen_test.dart` (extend existing)

- [ ] **Step 1: Add the CTA**

In `profile_screen.dart`, read `currentRoleProvider` and render a CTA only for applicants that navigates to onboarding:

```dart
import 'package:go_router/go_router.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/auth/current_role_provider.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
```

Inside the build, where the profile body's children are assembled (add near the top of the list, guarded):

```dart
          if (ref.watch(currentRoleProvider) == UserRole.applicant) ...[
            Card(
              child: ListTile(
                leading: const Icon(Icons.business_center_outlined),
                title: const Text("I'm hiring — post a job"),
                subtitle: const Text('Create your company to start recruiting'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => context.push(Routes.onboardingEmployer),
              ),
            ),
            const SizedBox(height: 12),
          ],
```

NOTE: match the surrounding widget structure in `profile_screen.dart` (it may be a `ListView`/`Column`); insert the guarded block where children are listed. If the screen is a `ConsumerWidget` it already has `ref`; if `ConsumerStatefulWidget`, use `ref` from state.

- [ ] **Step 2: Extend the profile widget test**

Add a test asserting the CTA shows for an applicant. Follow the existing `profile_screen_test.dart` setup (it overrides `meRepositoryProvider`); additionally seed the auth state to an applicant `SignedIn` so `currentRoleProvider` returns applicant:

```dart
  testWidgets('shows the hiring CTA for applicants', (tester) async {
    final container = ProviderContainer(overrides: [
      meRepositoryProvider.overrideWithValue(/* existing fake from this file */),
    ]);
    addTearDown(container.dispose);
    container.read(authStateProvider.notifier).set(
          const SignedIn(userId: 'u1', email: 'e@e.com', role: UserRole.applicant),
        );
    // pump ProfileScreen inside UncontrolledProviderScope (mirror this file's
    // existing harness) and:
    expect(find.text("I'm hiring — post a job"), findsOneWidget);
  });
```

Add imports for `authStateProvider`, `SignedIn`, `UserRole`. Reuse the file's existing fake `MeRepository` and pump harness rather than re-creating them.

- [ ] **Step 3: Run codegen + test**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/widget/profile_screen_test.dart`
Expected: PASS (existing + new).

- [ ] **Step 4: Full suite + analyze**

Run: `flutter test && flutter analyze`
Expected: all tests PASS, zero analyzer issues.

- [ ] **Step 5: Commit**

```bash
git add app/lib/presentation/profile/profile_screen.dart app/test/widget/profile_screen_test.dart
git commit -m "feat(app): role-gated 'I'm hiring' CTA → employer onboarding"
```

---

## Phase 1 Done — Definition of Done

- An applicant sees an "I'm hiring" CTA on Profile; tapping it opens the onboarding form.
- Submitting a valid company name calls `POST /v1/employers`, flips the session role to recruiter, and the role-aware redirect lands the user on `/recruiter/dashboard` (placeholder) with the recruiter bottom-nav — **no app restart**.
- A `409` shows an inline "name already registered" message and does NOT flip the role.
- A recruiter who reopens the app boots straight into the recruiter shell; an applicant who tries a `/recruiter/...` URL is bounced to `/feed`.
- `flutter test` and `flutter analyze` are green.

**Next phases (separate plans, written just-in-time):** Phase 2 = R3 recruiter dashboard + job management; Phase 3 = R4 backend (employer_invites + member/invite endpoints); Phase 4 = R4 Flutter (team management + invites UI).
