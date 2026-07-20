import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_repository.dart';
import 'package:jobify_app/data/feed/feed_repository_impl.dart';
import 'package:jobify_app/data/feed/feed_visit_repository.dart';
import 'package:jobify_app/data/feed/feed_visit_repository_impl.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
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
import 'package:jobify_app/presentation/feed/feed_item_card.dart';
import 'package:jobify_app/presentation/feed/feed_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/fake_repositories.dart';

class _FakeFeedRepo implements FeedRepository {
  _FakeFeedRepo(this.page);
  final FeedPageDto page;
  @override
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async => page;
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

/// Resume fetch that never resolves (loading) or always throws (error) —
/// in both cases the nudge banner must NOT render: it only decides from
/// resolved data.
class _PendingResumeRepo implements ResumeRepository {
  @override
  Future<ResumeDto?> current() => Completer<ResumeDto?>().future;
  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async =>
      throw UnimplementedError();
}

class _ThrowingResumeRepo implements ResumeRepository {
  @override
  Future<ResumeDto?> current() async => throw Exception('boom');
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

class _FakeFeedVisitRepo implements FeedVisitRepository {
  _FakeFeedVisitRepo(this._lastSeenAt);
  final DateTime? _lastSeenAt;
  @override
  Future<DateTime?> getLastSeenAt() async => _lastSeenAt;
  @override
  Future<void> setLastSeenAt(DateTime at) async {}
}

// FeedScreen now renders FeedSummaryRow, which reads
// applicationsRepositoryProvider/savedJobsRepositoryProvider — without a
// fake override these hit the real (dio) repos and fail/hang in tests.
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
  @override
  Future<List<StageEventDto>> fetchTimeline(String applicationId) async =>
      throw UnimplementedError();
}

class _FakeSavedJobsRepo implements SavedJobsRepository {
  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      const SavedJobsPageDto(items: []);
}

final _completeResumeDto = ResumeDto(
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

// `ResumeDto` isn't const-constructible (its `createdAt` is a `DateTime`),
// so `_completeResumeDto` is a plain `final`, not a compile-time constant —
// it cannot be used directly as a default parameter value. Use a private
// sentinel to distinguish "caller didn't pass `resume`" (→ default to
// complete) from "caller explicitly passed `resume: null`" (→ no resume).
const Object _unsetResume = Object();

Widget _wrap(
  Widget child, {
  required FeedRepository repo,
  Object? resume = _unsetResume,
  PreferencesDto prefs = _completePrefs,
  ResumeRepository? resumeRepo,
  JobsRepository? jobsRepo,
}) {
  final resolvedResume = identical(resume, _unsetResume)
      ? _completeResumeDto
      : resume as ResumeDto?;
  return ProviderScope(
    overrides: [
      feedRepositoryProvider.overrideWithValue(repo),
      resumeRepositoryProvider
          .overrideWithValue(resumeRepo ?? _FakeResumeRepo(resolvedResume)),
      preferencesRepositoryProvider.overrideWithValue(_FakePrefsRepo(prefs)),
      applicationsRepositoryProvider.overrideWithValue(_FakeApplicationsRepo()),
      savedJobsRepositoryProvider.overrideWithValue(_FakeSavedJobsRepo()),
      if (jobsRepo != null) jobsRepositoryProvider.overrideWithValue(jobsRepo),
    ],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: child,
    ),
  );
}

FeedItemDto _cardItem({String? caveat}) => FeedItemDto(
      match: MatchSummaryDto(
        id: 'm1',
        totalScore: 0.85,
        scoreComponents: const {},
        explanation: ExplanationDto(
          fit: 'Your Django work lines up.',
          generator: MatchGenerator.templated,
          generatorVersion: '1',
          caveat: caveat,
        ),
      ),
      job: JobSummaryDto(
        id: 'j1',
        title: 'Backend Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
    );

Widget _wrapCard(FeedItemDto item) => MediaQuery(
      data: const MediaQueryData(disableAnimations: true),
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: Scaffold(
          body: FeedItemCard(
            job: item.job,
            employer: item.employer,
            match: item.match,
            explanation: item.match.explanation,
            onTap: () {},
          ),
        ),
      ),
    );

/// Two open-job feed items (ids j1/j2) for the thumbs-feedback tests — a
/// dedicated helper rather than reusing `_cardItem` (which single-card tests
/// depend on staying at its current shape).
List<FeedItemDto> _thumbTestItems() => [
      FeedItemDto(
        match: const MatchSummaryDto(
          id: 'm1',
          totalScore: 0.8,
          scoreComponents: {},
        ),
        job: JobSummaryDto(
          id: 'j1',
          title: 'Backend Engineer',
          locations: const ['BLR'],
          status: JobStatus.open,
          postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
        ),
        employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
      ),
      FeedItemDto(
        match: const MatchSummaryDto(
          id: 'm2',
          totalScore: 0.7,
          scoreComponents: {},
        ),
        job: JobSummaryDto(
          id: 'j2',
          title: 'Frontend Engineer',
          locations: const ['MUM'],
          status: JobStatus.open,
          postedAt: DateTime.parse('2026-05-19T00:00:00Z'),
        ),
        employer: const EmployerSummaryDto(id: 'e2', name: 'Beta Co'),
      ),
    ];

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('renders empty state when no items', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(
          const FeedPageDto(items: []),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining("We're still looking"), findsOneWidget);
  });

  testWidgets('renders feed item cards', (tester) async {
    final item = FeedItemDto(
      match: const MatchSummaryDto(
        id: 'm1',
        totalScore: 0.8,
        scoreComponents: {},
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
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(
          FeedPageDto(items: [item]),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Engineer'), findsOneWidget);
    expect(find.text('ACME CO'), findsOneWidget);
    expect(find.text("You're all caught up"), findsOneWidget);
  });

  testWidgets('card leads with the match sentence and shows the caveat',
      (tester) async {
    await tester.pumpWidget(
      _wrapCard(_cardItem(caveat: '3 yrs vs 5 required')),
    );
    await tester.pumpAndSettle();
    expect(find.text('Your Django work lines up.'), findsOneWidget);
    expect(find.textContaining('3 yrs vs 5 required'), findsOneWidget);
  });

  testWidgets('no caveat line when caveat is null', (tester) async {
    await tester.pumpWidget(_wrapCard(_cardItem()));
    await tester.pumpAndSettle();
    expect(find.text('Your Django work lines up.'), findsOneWidget);
    expect(find.textContaining('vs'), findsNothing);
  });

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

  testWidgets(
      'shows new-matches headline when a match surfaced after last visit',
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
          applicationsRepositoryProvider
              .overrideWithValue(_FakeApplicationsRepo()),
          savedJobsRepositoryProvider.overrideWithValue(_FakeSavedJobsRepo()),
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

  testWidgets(
      'no new-matches headline on first-ever visit (no stored timestamp)',
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
          applicationsRepositoryProvider
              .overrideWithValue(_FakeApplicationsRepo()),
          savedJobsRepositoryProvider.overrideWithValue(_FakeSavedJobsRepo()),
          feedVisitRepositoryProvider
              .overrideWithValue(_FakeFeedVisitRepo(null)),
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

  group('thumbs feedback', () {
    testWidgets('thumb-down removes the card and shows Undo snackbar',
        (tester) async {
      final items = _thumbTestItems();
      final fakeJobsRepo = FakeJobsRepository(
        detail: JobDetailDto(job: items[0].job, employer: items[0].employer),
      );
      await tester.pumpWidget(
        _wrap(
          const FeedScreen(),
          repo: _FakeFeedRepo(FeedPageDto(items: items)),
          jobsRepo: fakeJobsRepo,
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Not interested').first);
      await tester.pumpAndSettle();

      expect(find.byType(FeedItemCard), findsOneWidget);
      expect(find.text('Hidden from your feed'), findsOneWidget);
      expect(find.text('Undo'), findsOneWidget);
      expect(fakeJobsRepo.ratedDown, contains('j1'));
    });

    testWidgets('thumb-down restores the card when the API call fails',
        (tester) async {
      final items = _thumbTestItems();
      final fakeJobsRepo = FakeJobsRepository(
        detail: JobDetailDto(job: items[0].job, employer: items[0].employer),
      )..rateMatchError = 'boom';
      await tester.pumpWidget(
        _wrap(
          const FeedScreen(),
          repo: _FakeFeedRepo(FeedPageDto(items: items)),
          jobsRepo: fakeJobsRepo,
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Not interested').first);
      await tester.pumpAndSettle();

      expect(find.byType(FeedItemCard), findsNWidgets(2)); // rolled back
    });

    testWidgets('thumb-up fills the icon and keeps the card', (tester) async {
      final items = _thumbTestItems();
      final fakeJobsRepo = FakeJobsRepository(
        detail: JobDetailDto(job: items[0].job, employer: items[0].employer),
      );
      await tester.pumpWidget(
        _wrap(
          const FeedScreen(),
          repo: _FakeFeedRepo(FeedPageDto(items: items)),
          jobsRepo: fakeJobsRepo,
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Good match').first);
      await tester.pumpAndSettle();

      expect(find.byType(FeedItemCard), findsNWidgets(2));
      expect(find.byIcon(Icons.thumb_up), findsOneWidget); // filled variant
      expect(fakeJobsRepo.ratedUp, contains('j1'));
    });

    testWidgets('tapping Undo clears the feedback and refetches the card list',
        (tester) async {
      final items = _thumbTestItems();
      final fakeJobsRepo = FakeJobsRepository(
        detail: JobDetailDto(job: items[0].job, employer: items[0].employer),
      );
      await tester.pumpWidget(
        _wrap(
          const FeedScreen(),
          repo: _FakeFeedRepo(FeedPageDto(items: items)),
          jobsRepo: fakeJobsRepo,
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Not interested').first);
      await tester.pumpAndSettle();
      // Optimistically hidden.
      expect(find.byType(FeedItemCard), findsOneWidget);

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      expect(fakeJobsRepo.clearedFeedback, contains('j1'));
      // undoDown() refetches page 1 from the (unfiltered) fake feed repo, so
      // the card comes back — proves this is a real refetch, not just a
      // local state patch.
      expect(find.byType(FeedItemCard), findsNWidgets(2));
      // Clear succeeded — no error snackbar should have been shown.
      expect(find.text("Couldn't save your rating"), findsNothing);
    });
  });
}
