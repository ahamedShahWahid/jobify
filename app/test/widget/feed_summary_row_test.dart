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
          _FakeApplicationsRepo(),
        ),
        savedJobsRepositoryProvider.overrideWithValue(_FakeSavedJobsRepo()),
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
}
