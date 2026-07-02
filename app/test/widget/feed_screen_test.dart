import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_repository.dart';
import 'package:jobify_app/data/feed/feed_repository_impl.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
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

void main() {
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

  testWidgets('shows upload nudge when no resume', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        resume: null,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Upload your résumé'), findsOneWidget);
  });

  testWidgets('shows preferences nudge when resume exists but incomplete',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        prefs: _incompletePrefs,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining("what you're looking for"), findsOneWidget);
  });

  testWidgets('no banner while the resume fetch is still pending',
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
    expect(find.textContaining('Upload your résumé'), findsNothing);
    expect(find.textContaining("what you're looking for"), findsNothing);
  });

  testWidgets('no banner when the resume fetch throws', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
        prefs: _incompletePrefs,
        resumeRepo: _ThrowingResumeRepo(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Upload your résumé'), findsNothing);
    expect(find.textContaining("what you're looking for"), findsNothing);
  });

  testWidgets('no banner when resume and preferences are complete',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(const FeedPageDto(items: [])),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Upload your résumé'), findsNothing);
    expect(find.textContaining("what you're looking for"), findsNothing);
  });
}
