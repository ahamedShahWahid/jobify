import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_screen.dart';

import '../helpers/fake_repositories.dart';

JobDetailDto _detail({MatchFeedbackRating? myFeedback}) => JobDetailDto(
      job: JobSummaryDto(
        id: 'j1',
        title: 'Senior Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
      match: MatchSummaryDto(
        id: 'm1',
        totalScore: 0.82,
        scoreComponents: const {},
        explanation: const ExplanationDto(
          fit: 'great fit',
          generator: MatchGenerator.templated,
          generatorVersion: '1',
        ),
        myFeedback: myFeedback,
      ),
    );

Widget _wrap(Widget child, {required JobsRepository repo}) {
  return ProviderScope(
    overrides: [jobsRepositoryProvider.overrideWithValue(repo)],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: child,
    ),
  );
}

void main() {
  testWidgets('rating row renders and persists a thumbs-up', (tester) async {
    final fakeJobsRepo = FakeJobsRepository(detail: _detail());
    await tester.pumpWidget(
      _wrap(const JobDetailScreen(jobId: 'j1'), repo: fakeJobsRepo),
    );
    await tester.pumpAndSettle();

    expect(find.text('Was this match right for you?'), findsOneWidget);

    await tester.tap(find.byTooltip('Good match'));
    await tester.pumpAndSettle();

    expect(fakeJobsRepo.ratedUp, contains('j1'));
  });

  testWidgets('detail shows current rating state (down)', (tester) async {
    final fakeJobsRepo = FakeJobsRepository(
      detail: _detail(myFeedback: MatchFeedbackRating.down),
    );
    await tester.pumpWidget(
      _wrap(const JobDetailScreen(jobId: 'j1'), repo: fakeJobsRepo),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.thumb_down), findsOneWidget);
    expect(find.byIcon(Icons.thumb_up_outlined), findsOneWidget);
  });

  testWidgets('tapping the active thumb clears the rating', (tester) async {
    final fakeJobsRepo = FakeJobsRepository(
      detail: _detail(myFeedback: MatchFeedbackRating.up),
    );
    await tester.pumpWidget(
      _wrap(const JobDetailScreen(jobId: 'j1'), repo: fakeJobsRepo),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Good match'));
    await tester.pumpAndSettle();

    expect(fakeJobsRepo.clearedFeedback, contains('j1'));
    expect(find.byIcon(Icons.thumb_up_outlined), findsOneWidget);
  });
}
