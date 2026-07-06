# Applicant Feed → Home Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the applicant Feed screen into a home summary — a "new matches since last visit" headline plus a 3-tile row (Applications count, Saved count, Match profile status) — replacing `FeedNudgeBanner`, with no new tab and no backend changes.

**Architecture:** Two new independent Riverpod providers (`FeedVisitRepository` for a local last-seen timestamp, `FeedSummaryController` for client-summed Applications/Saved counts, mirroring the existing `RecruiterDashboardController` pattern exactly) feed a new `FeedSummaryRow` widget. `FeedScreen` gains a one-shot visit-stamp in `initState` and computes the new-matches headline from data it already loads.

**Tech Stack:** Flutter, Riverpod 4.x (`@riverpod` codegen via `build_runner`), `go_router`, `shared_preferences`.

## Global Constraints

- No backend changes — this is Flutter-only (`app/`).
- Counts above 100 are an accepted MVP approximation (documented, not silently wrong) — same precedent as `RecruiterDashboardController`.
- "New matches" is computed only from whatever `FeedController` has currently loaded (first page, ordered by match score, not recency) — an accepted, documented approximation, not a global truth.
- Follow the existing repo convention: abstract interface in `data/<feature>/<repo>_repository.dart`, impl + `@Riverpod` provider in `data/<feature>/<repo>_repository_impl.dart`.
- After touching any `@riverpod`/`@freezed`/`@JsonSerializable` file, run `dart run build_runner build --delete-conflicting-outputs` from `app/`.
- Widget tests use `ThemeData.light(useMaterial3: true)`, never `buildTheme()` (network font fetch).
- Run `dart format lib test`, `flutter analyze`, and the relevant `flutter test` files after every task.

---

### Task 1: `FeedVisitRepository` — persisted last-seen-feed timestamp

**Files:**
- Create: `app/lib/data/feed/feed_visit_repository.dart`
- Create: `app/lib/data/feed/feed_visit_repository_impl.dart`
- Test: `app/test/unit/data/feed/feed_visit_repository_test.dart`

**Interfaces:**
- Produces: `abstract class FeedVisitRepository { Future<DateTime?> getLastSeenAt(); Future<void> setLastSeenAt(DateTime at); }`, provider `feedVisitRepositoryProvider` (generated from `@Riverpod(keepAlive: true) FeedVisitRepository feedVisitRepository(Ref ref)`).

- [ ] **Step 1: Write the abstract repository**

`app/lib/data/feed/feed_visit_repository.dart`:

```dart
/// Tracks when the applicant last opened Feed, so the home summary can show
/// "N new matches since your last visit." Returns `null` from
/// [getLastSeenAt] on first-ever call (no stored baseline) — callers must
/// treat that as "0 new," never as "everything is new."
abstract class FeedVisitRepository {
  Future<DateTime?> getLastSeenAt();
  Future<void> setLastSeenAt(DateTime at);
}
```

- [ ] **Step 2: Write the impl + provider**

`app/lib/data/feed/feed_visit_repository_impl.dart`:

```dart
import 'package:jobify_app/data/feed/feed_visit_repository.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'feed_visit_repository_impl.g.dart';

const _kFeedLastSeenAtKey = 'jobify_feed_last_seen_at';

class FeedVisitRepositoryImpl implements FeedVisitRepository {
  @override
  Future<DateTime?> getLastSeenAt() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_kFeedLastSeenAtKey);
    if (stored == null) return null;
    return DateTime.tryParse(stored);
  }

  @override
  Future<void> setLastSeenAt(DateTime at) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kFeedLastSeenAtKey, at.toIso8601String());
  }
}

@Riverpod(keepAlive: true)
FeedVisitRepository feedVisitRepository(Ref ref) => FeedVisitRepositoryImpl();
```

- [ ] **Step 3: Write the failing test**

`app/test/unit/data/feed/feed_visit_repository_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_visit_repository_impl.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('getLastSeenAt returns null when never set', () async {
    final repo = FeedVisitRepositoryImpl();
    expect(await repo.getLastSeenAt(), isNull);
  });

  test('setLastSeenAt then getLastSeenAt round-trips', () async {
    final repo = FeedVisitRepositoryImpl();
    final now = DateTime.parse('2026-07-06T10:00:00.000Z');
    await repo.setLastSeenAt(now);
    expect(await repo.getLastSeenAt(), now);
  });

  test('a later setLastSeenAt overwrites the earlier value', () async {
    final repo = FeedVisitRepositoryImpl();
    await repo.setLastSeenAt(DateTime.parse('2026-07-01T00:00:00.000Z'));
    await repo.setLastSeenAt(DateTime.parse('2026-07-06T00:00:00.000Z'));
    expect(
      await repo.getLastSeenAt(),
      DateTime.parse('2026-07-06T00:00:00.000Z'),
    );
  });
}
```

- [ ] **Step 4: Run test to verify it fails (missing generated file)**

Run: `cd app && flutter test test/unit/data/feed/feed_visit_repository_test.dart`
Expected: FAIL — `feed_visit_repository_impl.g.dart` not found.

- [ ] **Step 5: Generate code**

Run: `cd app && dart run build_runner build --delete-conflicting-outputs`
Expected: build succeeds, creates `app/lib/data/feed/feed_visit_repository_impl.g.dart`.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd app && flutter test test/unit/data/feed/feed_visit_repository_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 7: Format, analyze, commit**

```bash
cd app
dart format lib/data/feed test/unit/data/feed
flutter analyze lib/data/feed/feed_visit_repository.dart lib/data/feed/feed_visit_repository_impl.dart
git add lib/data/feed/feed_visit_repository.dart lib/data/feed/feed_visit_repository_impl.dart lib/data/feed/feed_visit_repository_impl.g.dart test/unit/data/feed/feed_visit_repository_test.dart
git commit -m "feat(app): add FeedVisitRepository for last-seen-feed timestamp"
```

---

### Task 2: `FeedSummaryController` — client-summed Applications/Saved counts

**Files:**
- Create: `app/lib/presentation/feed/feed_summary_controller.dart`
- Test: `app/test/unit/presentation/feed/feed_summary_controller_test.dart`

**Interfaces:**
- Consumes: `ApplicationsRepository.fetchPage({String? cursor, int limit = 20})` → `Future<ApplicationsPageDto>` (`app/lib/data/jobs/applications_repository.dart`); `SavedJobsRepository.fetchPage({String? cursor, int limit = 20})` → `Future<SavedJobsPageDto>` (`app/lib/data/jobs/saved_jobs_repository.dart`); providers `applicationsRepositoryProvider`, `savedJobsRepositoryProvider` (`app/lib/data/jobs/applications_repository_impl.dart`, `app/lib/data/jobs/saved_jobs_repository_impl.dart`).
- Produces: `class FeedSummary { final int applicationsCount; final bool applicationsApprox; final int savedCount; final bool savedApprox; }`, provider `feedSummaryControllerProvider` (`AsyncValue<FeedSummary>`).

- [ ] **Step 1: Write the failing test**

`app/test/unit/presentation/feed/feed_summary_controller_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_summary_controller.dart';

class _FakeApplicationsRepo implements ApplicationsRepository {
  _FakeApplicationsRepo(this._page);
  final ApplicationsPageDto _page;

  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      _page;

  @override
  Future<ApplicationDto> withdraw(String applicationId) async =>
      throw UnimplementedError();
}

class _FakeSavedJobsRepo implements SavedJobsRepository {
  _FakeSavedJobsRepo(this._page);
  final SavedJobsPageDto _page;

  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      _page;
}

const _job = JobSummaryDto(
  id: 'j1',
  title: 'Engineer',
  locations: ['BLR'],
  status: JobStatus.open,
);
const _employer = EmployerSummaryDto(id: 'e1', name: 'Acme Co');

ApplicationListItemDto _application(String id) => ApplicationListItemDto(
      application: ApplicationDto(
        id: id,
        jobId: 'j1',
        status: ApplicationStatus.applied,
        source: ApplicationSource.feed,
        createdAt: DateTime.parse('2026-05-18T00:00:00Z'),
        updatedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      job: _job,
      employer: _employer,
    );

SavedJobListItemDto _saved(String id) => SavedJobListItemDto(
      saved: SavedJobDto(
        id: id,
        jobId: 'j1',
        createdAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      job: _job,
      employer: _employer,
    );

void main() {
  test('counts items and reports no approximation when nextCursor is null',
      () async {
    final container = ProviderContainer(
      overrides: [
        applicationsRepositoryProvider.overrideWithValue(
          _FakeApplicationsRepo(
            ApplicationsPageDto(
              items: [_application('a1'), _application('a2')],
            ),
          ),
        ),
        savedJobsRepositoryProvider.overrideWithValue(
          _FakeSavedJobsRepo(SavedJobsPageDto(items: [_saved('s1')])),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary = await container.read(feedSummaryControllerProvider.future);
    expect(summary.applicationsCount, 2);
    expect(summary.applicationsApprox, isFalse);
    expect(summary.savedCount, 1);
    expect(summary.savedApprox, isFalse);
  });

  test('reports approximation when nextCursor is present', () async {
    final container = ProviderContainer(
      overrides: [
        applicationsRepositoryProvider.overrideWithValue(
          _FakeApplicationsRepo(
            ApplicationsPageDto(
              items: [_application('a1')],
              nextCursor: 'cursor-1',
            ),
          ),
        ),
        savedJobsRepositoryProvider.overrideWithValue(
          _FakeSavedJobsRepo(const SavedJobsPageDto(items: [])),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary = await container.read(feedSummaryControllerProvider.future);
    expect(summary.applicationsApprox, isTrue);
    expect(summary.savedApprox, isFalse);
  });

  test('empty pages yield an all-zero summary', () async {
    final container = ProviderContainer(
      overrides: [
        applicationsRepositoryProvider.overrideWithValue(
          _FakeApplicationsRepo(const ApplicationsPageDto(items: [])),
        ),
        savedJobsRepositoryProvider.overrideWithValue(
          _FakeSavedJobsRepo(const SavedJobsPageDto(items: [])),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary = await container.read(feedSummaryControllerProvider.future);
    expect(summary.applicationsCount, 0);
    expect(summary.savedCount, 0);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/unit/presentation/feed/feed_summary_controller_test.dart`
Expected: FAIL — `feed_summary_controller.dart` not found.

- [ ] **Step 3: Write minimal implementation**

`app/lib/presentation/feed/feed_summary_controller.dart`:

```dart
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'feed_summary_controller.g.dart';

/// Client-summed Applications/Saved counts for the Feed home summary.
/// Independent fetch (not a reuse of ApplicationsController/SavedController)
/// — mirrors RecruiterDashboardController's own independence from
/// RecruiterJobsController, so a limit change here never affects the real
/// Applications/Saved tab screens. `limit: 100` + the `*Approx` flag is the
/// same MVP-documented approximation RecruiterDashboardController uses.
class FeedSummary {
  const FeedSummary({
    required this.applicationsCount,
    required this.applicationsApprox,
    required this.savedCount,
    required this.savedApprox,
  });

  final int applicationsCount;
  final bool applicationsApprox;
  final int savedCount;
  final bool savedApprox;
}

@riverpod
class FeedSummaryController extends _$FeedSummaryController {
  @override
  Future<FeedSummary> build() async {
    final applicationsFuture =
        ref.read(applicationsRepositoryProvider).fetchPage(limit: 100);
    final savedFuture =
        ref.read(savedJobsRepositoryProvider).fetchPage(limit: 100);
    final applications = await applicationsFuture;
    final saved = await savedFuture;
    return FeedSummary(
      applicationsCount: applications.items.length,
      applicationsApprox: applications.nextCursor != null,
      savedCount: saved.items.length,
      savedApprox: saved.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
```

- [ ] **Step 4: Generate code**

Run: `cd app && dart run build_runner build --delete-conflicting-outputs`
Expected: build succeeds, creates `app/lib/presentation/feed/feed_summary_controller.g.dart`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd app && flutter test test/unit/presentation/feed/feed_summary_controller_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 6: Format, analyze, commit**

```bash
cd app
dart format lib/presentation/feed/feed_summary_controller.dart test/unit/presentation/feed/feed_summary_controller_test.dart
flutter analyze lib/presentation/feed/feed_summary_controller.dart
git add lib/presentation/feed/feed_summary_controller.dart lib/presentation/feed/feed_summary_controller.g.dart test/unit/presentation/feed/feed_summary_controller_test.dart
git commit -m "feat(app): add FeedSummaryController for applications/saved counts"
```

---

### Task 3: `FeedSummaryRow` widget

**Files:**
- Create: `app/lib/presentation/feed/feed_summary_row.dart`
- Test: `app/test/widget/feed_summary_row_test.dart`

**Interfaces:**
- Consumes: `feedSummaryControllerProvider` (Task 2); `resumeControllerProvider` → `AsyncValue<ResumeDto?>` (`app/lib/presentation/resume/resume_controller.dart`); `preferencesControllerProvider` → `AsyncValue<PreferencesDto>` with `.isComplete` (`app/lib/presentation/preferences/preferences_controller.dart`); `Routes.applications`, `Routes.saved`, `Routes.resume`, `Routes.preferences`, `Routes.profile` (`app/lib/presentation/routing/routes.dart`); `JobifyColors.caveatLight`/`caveatDark` (`app/lib/presentation/theme/jobify_colors.dart`); `JobifyRadii.borderRadiusXl` (`app/lib/presentation/theme/jobify_radii.dart`); `JobifyTypography.mono` (`app/lib/presentation/theme/jobify_typography.dart`); `JobifySpacing` (`app/lib/presentation/theme/jobify_spacing.dart`).
- Produces: `class FeedSummaryRow extends ConsumerWidget` — no constructor params, drop-in replacement for `const FeedNudgeBanner()`.

- [ ] **Step 1: Write the failing test**

`app/test/widget/feed_summary_row_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/data/resume/resume_parse_status.dart';
import 'package:jobify_app/data/resume/resume_repository.dart';
import 'package:jobify_app/data/resume/resume_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_summary_row.dart';

class _FakeApplicationsRepo implements ApplicationsRepository {
  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      const ApplicationsPageDto(items: []);
  @override
  Future<ApplicationDto> withdraw(String applicationId) async =>
      throw UnimplementedError();
}

class _FakeSavedJobsRepo implements SavedJobsRepository {
  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      const SavedJobsPageDto(items: []);
}

class _FakeResumeRepo implements ResumeRepository {
  _FakeResumeRepo(this._current);
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

class _FakePrefsRepo implements PreferencesRepository {
  _FakePrefsRepo(this._dto);
  final PreferencesDto _dto;
  @override
  Future<PreferencesDto> fetch() async => _dto;
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async => _dto;
}

final _resume = ResumeDto(
  id: 'r1',
  applicantId: 'a1',
  originalFilename: 'cv.pdf',
  contentType: 'application/pdf',
  sizeBytes: 1,
  parseStatus: ResumeParseStatus.parsed,
  createdAt: DateTime(2026),
);

const _completePrefs = PreferencesDto(
  desiredRole: DesiredRole.softwareEngineering,
  locations: ['Pune'],
  expectedCtc: '1800000.00',
);

const _incompletePrefs =
    PreferencesDto(desiredRole: null, locations: [], expectedCtc: null);

Future<void> _pump(
  WidgetTester tester, {
  ResumeDto? resume,
  PreferencesDto prefs = _completePrefs,
}) async {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, __) => const FeedSummaryRow()),
      GoRoute(path: '/applications', builder: (_, __) => const Text('Apps')),
      GoRoute(path: '/saved', builder: (_, __) => const Text('Saved')),
      GoRoute(path: '/profile', builder: (_, __) => const Text('Profile')),
      GoRoute(
        path: '/profile/resume',
        builder: (_, __) => const Text('Resume'),
      ),
      GoRoute(
        path: '/profile/preferences',
        builder: (_, __) => const Text('Preferences'),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        applicationsRepositoryProvider.overrideWithValue(
          _FakeApplicationsRepo(),
        ),
        savedJobsRepositoryProvider.overrideWithValue(_FakeSavedJobsRepo()),
        resumeRepositoryProvider.overrideWithValue(_FakeResumeRepo(resume)),
        preferencesRepositoryProvider
            .overrideWithValue(_FakePrefsRepo(prefs)),
      ],
      child: MaterialApp.router(
        theme: ThemeData.light(useMaterial3: true),
        routerConfig: router,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows upload-résumé prompt when no résumé', (tester) async {
    await _pump(tester, resume: null);
    expect(find.text('Upload résumé'), findsOneWidget);
  });

  testWidgets('shows finish-profile prompt when résumé exists but prefs incomplete',
      (tester) async {
    await _pump(tester, resume: _resume, prefs: _incompletePrefs);
    expect(find.text('Finish your profile'), findsOneWidget);
  });

  testWidgets('shows complete state when résumé and prefs are complete',
      (tester) async {
    await _pump(tester, resume: _resume, prefs: _completePrefs);
    expect(find.text('Profile complete'), findsOneWidget);
  });

  testWidgets('tapping Applications tile navigates to /applications',
      (tester) async {
    await _pump(tester, resume: _resume);
    await tester.tap(find.text('Applications'));
    await tester.pumpAndSettle();
    expect(find.text('Apps'), findsOneWidget);
  });

  testWidgets('tapping Saved tile navigates to /saved', (tester) async {
    await _pump(tester, resume: _resume);
    await tester.tap(find.text('Saved'));
    await tester.pumpAndSettle();
    expect(find.text('Saved'), findsOneWidget);
  });

  testWidgets('tapping upload-résumé prompt navigates to /profile/resume',
      (tester) async {
    await _pump(tester, resume: null);
    await tester.tap(find.text('Upload résumé'));
    await tester.pumpAndSettle();
    expect(find.text('Resume'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/widget/feed_summary_row_test.dart`
Expected: FAIL — `feed_summary_row.dart` not found.

- [ ] **Step 3: Write minimal implementation**

`app/lib/presentation/feed/feed_summary_row.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/feed/feed_summary_controller.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/resume/resume_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';

/// Feed's home-summary row: Applications count / Saved count / match-profile
/// status. Replaces FeedNudgeBanner — the match-profile tile owns the same
/// résumé/preferences signal the banner used to, so there's one place that
/// decides "is your profile ready," not two.
class FeedSummaryRow extends ConsumerWidget {
  const FeedSummaryRow({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(feedSummaryControllerProvider);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(
          child: _CountTile(
            icon: Icons.send_outlined,
            label: 'Applications',
            value: summary.whenOrNull(
              data: (s) => s.applicationsApprox
                  ? '${s.applicationsCount}+'
                  : '${s.applicationsCount}',
            ),
            isError: summary.hasError,
            onTap: () => context.go(Routes.applications),
          ),
        ),
        const SizedBox(width: JobifySpacing.sm),
        Expanded(
          child: _CountTile(
            icon: Icons.bookmark_outline,
            label: 'Saved',
            value: summary.whenOrNull(
              data: (s) =>
                  s.savedApprox ? '${s.savedCount}+' : '${s.savedCount}',
            ),
            isError: summary.hasError,
            onTap: () => context.go(Routes.saved),
          ),
        ),
        const SizedBox(width: JobifySpacing.sm),
        const Expanded(child: _MatchProfileTile()),
      ],
    );
  }
}

class _CountTile extends StatelessWidget {
  const _CountTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.isError,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final String? value;
  final bool isError;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: JobifyRadii.borderRadiusXl,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(JobifySpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
              const SizedBox(height: JobifySpacing.sm),
              if (isError)
                Icon(Icons.refresh, size: 18, color: theme.colorScheme.error)
              else
                Text(
                  value ?? '—',
                  style: JobifyTypography.mono(
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.onSurface,
                  ),
                ),
              const SizedBox(height: JobifySpacing.xs),
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Watches the same two providers FeedNudgeBanner used to. Only decides from
/// resolved data — never renders off a loading or failed fetch (a bare
/// `.value == null` would flash the wrong state on every cold load).
class _MatchProfileTile extends ConsumerWidget {
  const _MatchProfileTile();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resumeState = ref.watch(resumeControllerProvider);
    final prefsState = ref.watch(preferencesControllerProvider);
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final caveat = isDark ? JobifyColors.caveatDark : JobifyColors.caveatLight;
    final quiet = theme.colorScheme.onSurfaceVariant;

    if (!resumeState.hasValue || !prefsState.hasValue) {
      return _tile(
        context,
        icon: Icons.badge_outlined,
        label: 'Profile',
        color: quiet,
        onTap: () => context.go(Routes.profile),
      );
    }
    final resume = resumeState.value;
    if (resume == null) {
      return _tile(
        context,
        icon: Icons.upload_file_outlined,
        label: 'Upload résumé',
        color: caveat,
        onTap: () => context.push(Routes.resume),
      );
    }
    if (!prefsState.requireValue.isComplete) {
      return _tile(
        context,
        icon: Icons.badge_outlined,
        label: 'Finish your profile',
        color: caveat,
        onTap: () => context.push(Routes.preferences, extra: resume),
      );
    }
    return _tile(
      context,
      icon: Icons.check_circle_outline,
      label: 'Profile complete',
      color: quiet,
      onTap: () => context.go(Routes.profile),
    );
  }

  Widget _tile(
    BuildContext context, {
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: JobifyRadii.borderRadiusXl,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(JobifySpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 20, color: color),
              const SizedBox(height: JobifySpacing.sm),
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/widget/feed_summary_row_test.dart`
Expected: PASS (6 tests).

- [ ] **Step 5: Format, analyze, commit**

```bash
cd app
dart format lib/presentation/feed/feed_summary_row.dart test/widget/feed_summary_row_test.dart
flutter analyze lib/presentation/feed/feed_summary_row.dart
git add lib/presentation/feed/feed_summary_row.dart test/widget/feed_summary_row_test.dart
git commit -m "feat(app): add FeedSummaryRow widget (applications/saved/profile status)"
```

---

### Task 4: Wire into `FeedScreen` — visit stamp + new-matches headline + swap banner

**Files:**
- Modify: `app/lib/presentation/feed/feed_screen.dart`
- Modify: `app/test/widget/feed_screen_test.dart`

**Interfaces:**
- Consumes: `feedVisitRepositoryProvider` (Task 1); `FeedSummaryRow` (Task 3); `FeedItemDto.match.surfacedAt` → `DateTime?` (`app/lib/data/feed/feed_dto.dart` — nested under `MatchSummaryDto`, not directly on `FeedItemDto`).

- [ ] **Step 1: Update the failing/changing tests first**

Open `app/test/widget/feed_screen_test.dart`. Replace the six banner-related tests (the last six `testWidgets` blocks, from `'shows upload nudge when no resume'` through `'no banner when resume and preferences are complete'`) with:

```dart
  testWidgets('shows upload prompt when no resume', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        resume: null,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Upload résumé'), findsOneWidget);
  });

  testWidgets('shows finish-profile prompt when resume exists but incomplete',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        prefs: _incompletePrefs,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Finish your profile'), findsOneWidget);
  });

  testWidgets('shows neutral profile tile while the resume fetch is pending',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        prefs: _incompletePrefs,
        resumeRepo: _PendingResumeRepo(),
      ),
    );
    await tester.pump();
    await tester.pump();
    expect(find.text('Upload résumé'), findsNothing);
    expect(find.text('Finish your profile'), findsNothing);
    expect(find.text('Profile complete'), findsNothing);
    expect(find.text('Profile'), findsOneWidget);
  });

  testWidgets('shows neutral profile tile when the resume fetch throws',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        prefs: _incompletePrefs,
        resumeRepo: _ThrowingResumeRepo(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Upload résumé'), findsNothing);
    expect(find.text('Finish your profile'), findsNothing);
    expect(find.text('Profile'), findsOneWidget);
  });

  testWidgets('shows complete state when resume and preferences are complete',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Profile complete'), findsOneWidget);
  });
```

Then add two new tests for the new-matches headline at the end of `main()`, and one new fake above `main()`:

```dart
class _FakeFeedVisitRepo implements FeedVisitRepository {
  _FakeFeedVisitRepo(this._lastSeenAt);
  final DateTime? _lastSeenAt;
  @override
  Future<DateTime?> getLastSeenAt() async => _lastSeenAt;
  @override
  Future<void> setLastSeenAt(DateTime at) async {}
}
```

(place this class next to the other fakes, above `final _completeResumeDto = ...`)

```dart
  testWidgets('shows new-matches headline when a match surfaced after last visit',
      (tester) async {
    final item = FeedItemDto(
      match: MatchSummaryDto(
        id: 'm1',
        totalScore: 0.8,
        scoreComponents: const {},
        surfacedAt: DateTime.parse('2026-07-06T12:00:00Z'),
      ),
      job: JobSummaryDto(
        id: 'j1',
        title: 'Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          feedRepositoryProvider
              .overrideWithValue(_FakeFeedRepo(FeedPageDto(items: [item]))),
          resumeRepositoryProvider
              .overrideWithValue(_FakeResumeRepo(_completeResumeDto)),
          preferencesRepositoryProvider
              .overrideWithValue(_FakePrefsRepo(_completePrefs)),
          feedVisitRepositoryProvider.overrideWithValue(
            _FakeFeedVisitRepo(DateTime.parse('2026-07-06T00:00:00Z')),
          ),
        ],
        child: MaterialApp(
          theme: ThemeData.light(useMaterial3: true),
          home: const FeedScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('1 new match'), findsOneWidget);
  });

  testWidgets('no new-matches headline on first-ever visit (no stored timestamp)',
      (tester) async {
    final item = FeedItemDto(
      match: MatchSummaryDto(
        id: 'm1',
        totalScore: 0.8,
        scoreComponents: const {},
        surfacedAt: DateTime.parse('2026-07-06T12:00:00Z'),
      ),
      job: JobSummaryDto(
        id: 'j1',
        title: 'Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          feedRepositoryProvider
              .overrideWithValue(_FakeFeedRepo(FeedPageDto(items: [item]))),
          resumeRepositoryProvider
              .overrideWithValue(_FakeResumeRepo(_completeResumeDto)),
          preferencesRepositoryProvider
              .overrideWithValue(_FakePrefsRepo(_completePrefs)),
          feedVisitRepositoryProvider.overrideWithValue(_FakeFeedVisitRepo(null)),
        ],
        child: MaterialApp(
          theme: ThemeData.light(useMaterial3: true),
          home: const FeedScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('new match'), findsNothing);
  });
```

Add the missing imports at the top of the file:

```dart
import 'package:jobify_app/data/feed/feed_visit_repository.dart';
import 'package:jobify_app/data/feed/feed_visit_repository_impl.dart';
```

Note: existing tests using `_wrap(...)` (which doesn't override `feedVisitRepositoryProvider`) will exercise the real `FeedVisitRepositoryImpl` against a real (unmocked in this file) `SharedPreferences` — add `SharedPreferences.setMockInitialValues({});` in a `setUp(() { ... });` at the top of `main()`, and add `import 'package:shared_preferences/shared_preferences.dart';`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app && flutter test test/widget/feed_screen_test.dart`
Expected: FAIL — `FeedSummaryRow`/`feedVisitRepositoryProvider` not found, old banner text no longer present.

- [ ] **Step 3: Modify `feed_screen.dart`**

Replace the full contents of `app/lib/presentation/feed/feed_screen.dart` with:

```dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_visit_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_controller.dart';
import 'package:jobify_app/presentation/feed/feed_item_card.dart';
import 'package:jobify_app/presentation/feed/feed_summary_row.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/arrive.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/bold_header.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';

class FeedScreen extends ConsumerStatefulWidget {
  const FeedScreen({super.key});
  @override
  ConsumerState<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends ConsumerState<FeedScreen> {
  final _scroll = ScrollController();
  DateTime? _lastSeenAt;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(feedControllerProvider.notifier).loadMore();
      }
    });
    unawaited(_stampVisit());
  }

  /// One-shot per screen mount — NOT tied to feedControllerProvider rebuilds
  /// (refresh/loadMore also emit new AsyncValue.data, which would otherwise
  /// re-stamp the visit and make the count only ever reflect the last
  /// pull-to-refresh instead of the last time the app was actually opened).
  Future<void> _stampVisit() async {
    final repo = ref.read(feedVisitRepositoryProvider);
    final prev = await repo.getLastSeenAt();
    if (mounted) setState(() => _lastSeenAt = prev);
    await repo.setLastSeenAt(DateTime.now());
  }

  /// Only counts matches within whatever FeedController has currently
  /// loaded (first page, ordered by match score, not recency) — a
  /// documented MVP approximation, not a global truth.
  int _newMatchesCount(List<FeedItemDto> items) {
    final lastSeenAt = _lastSeenAt;
    if (lastSeenAt == null) return 0;
    return items
        .where((i) => i.match.surfacedAt?.isAfter(lastSeenAt) ?? false)
        .length;
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(feedControllerProvider);
    final newCount =
        value.value != null ? _newMatchesCount(value.value!.items) : 0;
    return BoldScaffold(
      header: BoldHeader(
        title: 'For you',
        subtitle: 'Roles matched to your profile',
        trailing: IconButton(
          icon: const Icon(Icons.refresh),
          tooltip: 'Refresh',
          onPressed: () => ref.read(feedControllerProvider.notifier).refresh(),
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              JobifySpacing.lg,
              JobifySpacing.lg,
              JobifySpacing.lg,
              0,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (newCount > 0) _NewMatchesHeadline(count: newCount),
                const FeedSummaryRow(),
              ],
            ),
          ),
          Expanded(
            child: AsyncValueWidget<FeedState>(
              value: value,
              onRetry: () =>
                  ref.read(feedControllerProvider.notifier).refresh(),
              isEmpty: (s) => s.items.isEmpty,
              empty: () => const JobifyEmptyState(
                headline: "We're still looking for matches",
                body: 'Upload a resume to help us find you better roles.',
                icon: Icons.search_off,
              ),
              data: (s) => RefreshIndicator(
                onRefresh: () =>
                    ref.read(feedControllerProvider.notifier).refresh(),
                child: ListView.separated(
                  controller: _scroll,
                  padding: const EdgeInsets.all(JobifySpacing.lg),
                  itemCount: s.items.length + 1,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: JobifySpacing.md),
                  itemBuilder: (context, i) {
                    if (i == s.items.length) {
                      if (s.isLoadingMore) {
                        return const Padding(
                          padding: EdgeInsets.all(JobifySpacing.lg),
                          child: JobifyLoadingView(),
                        );
                      }
                      if (!s.hasMore) {
                        return Padding(
                          padding: const EdgeInsets.all(JobifySpacing.lg),
                          child: Center(
                            child: Text(
                              "You're all caught up",
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                            ),
                          ),
                        );
                      }
                      return const SizedBox.shrink();
                    }
                    final item = s.items[i];
                    return Arrive(
                      index: i,
                      child: FeedItemCard(
                        job: item.job,
                        employer: item.employer,
                        onTap: () =>
                            context.go('${Routes.feed}/jobs/${item.job.id}'),
                        match: item.match,
                        explanation: item.match.explanation,
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NewMatchesHeadline extends StatelessWidget {
  const _NewMatchesHeadline({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final brand =
        isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight;
    return Padding(
      padding: const EdgeInsets.only(bottom: JobifySpacing.md),
      child: Text(
        count == 1
            ? '1 new match since your last visit'
            : '$count new matches since your last visit',
        style: theme.textTheme.titleMedium?.copyWith(color: brand),
      ),
    );
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd app && flutter test test/widget/feed_screen_test.dart`
Expected: PASS (all tests, including the two new headline tests).

- [ ] **Step 5: Format, analyze, commit**

```bash
cd app
dart format lib/presentation/feed/feed_screen.dart test/widget/feed_screen_test.dart
flutter analyze lib/presentation/feed/feed_screen.dart
git add lib/presentation/feed/feed_screen.dart test/widget/feed_screen_test.dart
git commit -m "feat(app): reshape Feed into a home summary with new-matches headline"
```

---

### Task 5: Remove `FeedNudgeBanner`, fix stale comment, full verification

**Files:**
- Delete: `app/lib/presentation/feed/feed_nudge_banner.dart`
- Modify: `app/lib/presentation/preferences/preferences_controller.dart:18` (comment only)

**Interfaces:**
- None — this task removes dead code and fixes a stale doc comment; no new symbols.

- [ ] **Step 1: Confirm no remaining references**

Run: `cd app && grep -rn "FeedNudgeBanner" lib test`
Expected: no output (Task 4 already removed the only import/usage in `feed_screen.dart`, and `feed_screen_test.dart` never imported the banner class directly).

- [ ] **Step 2: Delete the file**

```bash
cd app
git rm lib/presentation/feed/feed_nudge_banner.dart
```

- [ ] **Step 3: Fix the stale comment in `preferences_controller.dart`**

In `app/lib/presentation/preferences/preferences_controller.dart`, the `submit` method has this comment:

```dart
    // Preserve the loaded value across the submit: this provider is
    // keepAlive and shared (ProfileScreen, FeedNudgeBanner,
    // EditProfileScreen), so a bare AsyncLoading/AsyncError here would
    // radiate a data-less state to every watcher.
```

Change `FeedNudgeBanner` to `FeedSummaryRow`:

```dart
    // Preserve the loaded value across the submit: this provider is
    // keepAlive and shared (ProfileScreen, FeedSummaryRow,
    // EditProfileScreen), so a bare AsyncLoading/AsyncError here would
    // radiate a data-less state to every watcher.
```

- [ ] **Step 4: Full verification pass**

```bash
cd app
dart format --set-exit-if-changed lib test
flutter analyze
flutter test
```

Expected: format reports 0 changed, analyze reports "No issues found!", all tests pass.

- [ ] **Step 5: Commit**

```bash
cd app
git add lib/presentation/preferences/preferences_controller.dart
git commit -m "chore(app): remove superseded FeedNudgeBanner, fix stale comment"
```

---

## Manual verification (after Task 5)

Once the local stack is running (`scripts/start-all.sh --with-flutter` from repo root), sign in as an applicant and open the Feed tab:

1. First-ever sign-in: no "new matches" headline (no stored baseline yet), summary row shows Applications/Saved counts (likely 0) and either "Upload résumé" or "Finish your profile" in amber.
2. Complete résumé + preferences, reload Feed: match-profile tile shows quiet "Profile complete."
3. Force a new match server-side (or seed one with a recent `surfaced_at`), reopen Feed after having visited before: headline "N new matches since your last visit" appears once, then disappears on the next visit.
4. Tap each of the three tiles: Applications → Applications tab; Saved → Saved tab; profile tile → Resume, Preferences, or Profile tab depending on state.
