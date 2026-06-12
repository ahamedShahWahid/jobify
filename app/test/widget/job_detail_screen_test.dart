import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_screen.dart';

class _FakeJobsRepo implements JobsRepository {
  _FakeJobsRepo(this.detail);
  final JobDetailDto detail;
  @override
  Future<JobDetailDto> fetchById(String id) async => detail;
  @override
  Future<ApplicationDto> applyTo(
    String id, {
    ApplicationSource source = ApplicationSource.feed,
  }) async =>
      ApplicationDto(
        id: 'a1',
        jobId: id,
        status: ApplicationStatus.applied,
        source: source,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );
  @override
  Future<SavedJobDto> save(String id) async => SavedJobDto(
        id: 's1',
        jobId: id,
        createdAt: DateTime.now(),
      );
  @override
  Future<void> unsave(String id) async {}
}

JobDetailDto _detail({ApplicationDto? app, SavedJobDto? saved}) => JobDetailDto(
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
      savedJob: saved,
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
  testWidgets('shows Apply button when no application', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const JobDetailScreen(jobId: 'j1'),
        repo: _FakeJobsRepo(_detail()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Apply'), findsOneWidget);
    expect(find.text('Withdraw'), findsNothing);
  });

  testWidgets('shows Withdraw when applied', (tester) async {
    final app = ApplicationDto(
      id: 'a1',
      jobId: 'j1',
      status: ApplicationStatus.applied,
      source: ApplicationSource.feed,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
    await tester.pumpWidget(
      _wrap(
        const JobDetailScreen(jobId: 'j1'),
        repo: _FakeJobsRepo(_detail(app: app)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Withdraw'), findsOneWidget);
  });

  testWidgets('shows filled heart when saved', (tester) async {
    final s = SavedJobDto(
      id: 's1',
      jobId: 'j1',
      createdAt: DateTime.now(),
    );
    await tester.pumpWidget(
      _wrap(
        const JobDetailScreen(jobId: 'j1'),
        repo: _FakeJobsRepo(_detail(saved: s)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.bookmark), findsOneWidget);
  });

  testWidgets('renders explanation card', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const JobDetailScreen(jobId: 'j1'),
        repo: _FakeJobsRepo(_detail()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Why this match'), findsOneWidget);
    expect(find.text('great fit'), findsOneWidget);
  });
}
