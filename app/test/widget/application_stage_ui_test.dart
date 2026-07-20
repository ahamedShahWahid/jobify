import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/data/notifications/notification_dto.dart';
import 'package:jobify_app/presentation/applications/applications_screen.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_screen.dart';
import 'package:jobify_app/presentation/notifications/notification_title.dart';
import 'package:riverpod/src/framework.dart' show Override;

import '../helpers/fake_repositories.dart';

Widget _wrap(
  Widget child, {
  ApplicationsRepository? applicationsRepo,
  JobsRepository? jobsRepo,
}) {
  final overrides = <Override>[
    if (applicationsRepo != null)
      applicationsRepositoryProvider.overrideWithValue(applicationsRepo),
    if (jobsRepo != null) jobsRepositoryProvider.overrideWithValue(jobsRepo),
  ];
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: child,
    ),
  );
}

ApplicationListItemDto _item({
  required String id,
  required ApplicationStage stage,
}) =>
    ApplicationListItemDto(
      application: ApplicationDto(
        id: id,
        jobId: 'j1',
        status: ApplicationStatus.applied,
        source: ApplicationSource.feed,
        stage: stage,
        createdAt: DateTime(2026, 5),
        updatedAt: DateTime(2026, 5),
      ),
      job: JobSummaryDto(
        id: 'j1',
        title: 'QA Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime(2026, 4),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme'),
    );

JobDetailDto _detail({ApplicationDto? app}) => JobDetailDto(
      job: JobSummaryDto(
        id: 'j1',
        title: 'Senior Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
      match: const MatchSummaryDto(
        id: 'm1',
        totalScore: 0.82,
        scoreComponents: {},
        explanation: ExplanationDto(
          fit: 'great fit',
          generator: MatchGenerator.templated,
          generatorVersion: '1',
        ),
      ),
      application: app,
    );

void main() {
  testWidgets('applications row shows the stage label, not raw status',
      (tester) async {
    final repo = FakeApplicationsRepository()
      ..fetchPageOverride = ApplicationsPageDto(
        items: [_item(id: 'a1', stage: ApplicationStage.interview)],
      );
    await tester.pumpWidget(
      _wrap(const ApplicationsScreen(), applicationsRepo: repo),
    );
    await tester.pumpAndSettle();
    expect(find.text('Interview'), findsOneWidget);
  });

  testWidgets('rejected renders as "Not selected"', (tester) async {
    final repo = FakeApplicationsRepository()
      ..fetchPageOverride = ApplicationsPageDto(
        items: [_item(id: 'a2', stage: ApplicationStage.rejected)],
      );
    await tester.pumpWidget(
      _wrap(const ApplicationsScreen(), applicationsRepo: repo),
    );
    await tester.pumpAndSettle();
    expect(find.text('Not selected'), findsOneWidget);
  });

  testWidgets('job detail shows the timeline when events exist',
      (tester) async {
    final app = ApplicationDto(
      id: 'a1',
      jobId: 'j1',
      status: ApplicationStatus.applied,
      source: ApplicationSource.feed,
      stage: ApplicationStage.shortlisted,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
    final applicationsRepo = FakeApplicationsRepository()
      ..timelines['a1'] = [
        StageEventDto(
          fromStage: ApplicationStage.applied,
          toStage: ApplicationStage.shortlisted,
          createdAt: DateTime(2026, 5, 2),
        ),
      ];
    final jobsRepo = FakeJobsRepository(detail: _detail(app: app));
    await tester.pumpWidget(
      _wrap(
        const JobDetailScreen(jobId: 'j1'),
        applicationsRepo: applicationsRepo,
        jobsRepo: jobsRepo,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Shortlisted'), findsWidgets);
  });

  testWidgets('timeline fetch error degrades to the chip alone',
      (tester) async {
    final app = ApplicationDto(
      id: 'a1',
      jobId: 'j1',
      status: ApplicationStatus.applied,
      source: ApplicationSource.feed,
      stage: ApplicationStage.shortlisted,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
    final applicationsRepo = FakeApplicationsRepository()
      ..fetchTimelineError = Exception('boom');
    final jobsRepo = FakeJobsRepository(detail: _detail(app: app));
    await tester.pumpWidget(
      _wrap(
        const JobDetailScreen(jobId: 'j1'),
        applicationsRepo: applicationsRepo,
        jobsRepo: jobsRepo,
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Timeline'), findsNothing);
  });

  test('notificationTitle handles application_stage_changed', () {
    final n = NotificationDto(
      id: 'n1',
      kind: 'application_stage_changed',
      channel: 'in_app',
      status: 'pending',
      payload: const {'job_title': 'QA Engineer', 'stage': 'shortlisted'},
      sendAfter: DateTime.utc(2026, 7, 19),
      createdAt: DateTime.utc(2026, 7, 19),
    );
    expect(notificationTitle(n), 'Shortlisted for QA Engineer');
  });
}
