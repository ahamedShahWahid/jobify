import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
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

/// Mirrors the `_ThrowingResumeRepo`/`_PendingResumeRepo` pattern in
/// feed_screen_test.dart — used to exercise the count tiles' `isError`
/// degradation (a quiet retry icon, per the design spec's "never blocks
/// the match-profile tile or the job list beneath" requirement).
///
/// Both this repo and `_ThrowingSavedJobsRepo` below can safely be made to
/// throw together: `FeedSummaryController.build()` uses `Future.wait`, which
/// attaches a listener to every future in the list synchronously when it's
/// called — so neither rejection is ever left unobserved, even when both
/// fetches reject. (Previously, with sequential awaits, a first-fetch
/// rejection could leave the second in-flight future with no listener
/// attached — an unhandled-rejection hazard, since fixed.) `FeedSummary` is
/// a single combined async value, so either fetch failing puts BOTH count
/// tiles into their shared error state.
class _ThrowingApplicationsRepo implements ApplicationsRepository {
  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      throw Exception('boom');
  @override
  Future<ApplicationDto> withdraw(String applicationId) async =>
      throw UnimplementedError();
}

/// See `_ThrowingApplicationsRepo` above — safe to combine with it now that
/// `FeedSummaryController.build()` uses `Future.wait`.
class _ThrowingSavedJobsRepo implements SavedJobsRepository {
  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      throw Exception('boom');
}

/// Fails its first `fetchPage` call, then succeeds — lets a test drive the
/// error tile's retry path (tap → `ref.invalidate` → re-fetch → recovery)
/// without needing new shared test infrastructure.
class _FlakyApplicationsRepo implements ApplicationsRepository {
  int callCount = 0;
  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async {
    callCount++;
    if (callCount == 1) throw Exception('boom');
    return const ApplicationsPageDto(items: []);
  }

  @override
  Future<ApplicationDto> withdraw(String applicationId) async =>
      throw UnimplementedError();
}

/// See `_FlakyApplicationsRepo` above.
class _FlakySavedJobsRepo implements SavedJobsRepository {
  int callCount = 0;
  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async {
    callCount++;
    if (callCount == 1) throw Exception('boom');
    return const SavedJobsPageDto(items: []);
  }
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
  ApplicationsRepository? applicationsRepo,
  SavedJobsRepository? savedJobsRepo,
}) async {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, __) => const Scaffold(body: FeedSummaryRow()),
      ),
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
          applicationsRepo ?? _FakeApplicationsRepo(),
        ),
        savedJobsRepositoryProvider.overrideWithValue(
          savedJobsRepo ?? _FakeSavedJobsRepo(),
        ),
        resumeRepositoryProvider.overrideWithValue(_FakeResumeRepo(resume)),
        preferencesRepositoryProvider.overrideWithValue(_FakePrefsRepo(prefs)),
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
    await _pump(tester);
    expect(find.text('Upload résumé'), findsOneWidget);
  });

  testWidgets(
      'shows finish-profile prompt when résumé exists but prefs incomplete',
      (tester) async {
    await _pump(tester, resume: _resume, prefs: _incompletePrefs);
    expect(find.text('Finish your profile'), findsOneWidget);
  });

  testWidgets('shows complete state when résumé and prefs are complete',
      (tester) async {
    await _pump(tester, resume: _resume);
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
    await _pump(tester);
    await tester.tap(find.text('Upload résumé'));
    await tester.pumpAndSettle();
    expect(find.text('Resume'), findsOneWidget);
  });

  testWidgets(
      'shows a retry icon on both count tiles when BOTH repos throw, '
      'without blocking the match-profile tile', (tester) async {
    await _pump(
      tester,
      resume: _resume,
      applicationsRepo: _ThrowingApplicationsRepo(),
      savedJobsRepo: _ThrowingSavedJobsRepo(),
    );

    // Applications + Saved tiles degrade to a quiet retry icon, not a crash
    // — proven safe for both repos rejecting together by the Future.wait fix
    // (see _ThrowingApplicationsRepo's doc comment).
    expect(find.byIcon(Icons.refresh), findsNWidgets(2));
    // Value text ('—' placeholder or a count) never renders for either
    // errored tile.
    expect(find.text('—'), findsNothing);

    // The row itself, and the independent match-profile tile, still build.
    expect(find.text('Applications'), findsOneWidget);
    expect(find.text('Saved'), findsOneWidget);
    expect(find.text('Profile complete'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'tapping an errored count tile retries (not navigates) and recovers '
      'to a real count', (tester) async {
    final applicationsRepo = _FlakyApplicationsRepo();
    final savedJobsRepo = _FlakySavedJobsRepo();
    await _pump(
      tester,
      resume: _resume,
      applicationsRepo: applicationsRepo,
      savedJobsRepo: savedJobsRepo,
    );

    // Both repos rejected on the first fetch — both tiles start errored.
    expect(find.byIcon(Icons.refresh), findsNWidgets(2));

    await tester.tap(find.byIcon(Icons.refresh).first);
    await tester.pumpAndSettle();

    // Tapping an errored tile invoked `onRetry` (ref.invalidate), not
    // `onTap` (navigation): we're still on the Feed row (no push to
    // /applications or /saved), and the provider's re-fetch — this time
    // succeeding — recovered both tiles to a real count instead of leaving
    // them on the retry icon.
    expect(find.text('Applications'), findsOneWidget);
    expect(find.text('Saved'), findsOneWidget);
    expect(find.byIcon(Icons.refresh), findsNothing);
    expect(find.text('0'), findsNWidgets(2));
    expect(applicationsRepo.callCount, 2);
    expect(savedJobsRepo.callCount, 2);
  });
}
