import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:kpa_app/domain/jobs/jobs_repository.dart';
import 'package:kpa_app/presentation/job_detail/job_detail_screen.dart';

class _FakeJobsRepo implements JobsRepository {
  _FakeJobsRepo(this.detail);
  final JobDetailDto detail;
  @override
  Future<JobDetailDto> fetchById(String id) async => detail;
  @override
  Future<ApplicationDto> applyTo(String id, {String source = 'feed'}) async =>
      ApplicationDto(
        id: 'a1',
        applicantId: 'ap1',
        jobId: id,
        status: 'applied',
        source: source,
        createdAt: DateTime.now(),
      );
  @override
  Future<SavedJobDto> save(String id) async => SavedJobDto(
        id: 's1',
        applicantId: 'ap1',
        jobId: id,
        createdAt: DateTime.now(),
      );
  @override
  Future<void> unsave(String id) async {}
}

JobDetailDto _detail({ApplicationDto? app, SavedJobDto? saved}) =>
    JobDetailDto(
      job: JobSummaryDto(
        id: 'j1',
        title: 'Senior Engineer',
        location: 'BLR',
        status: 'open',
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
      match: MatchSummaryDto(
        id: 'm1',
        totalScore: 0.82,
        scoreComponents: const {},
        explanation: const ExplanationDto(
          fit: 'great fit',
          generator: 'templated',
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
      applicantId: 'ap1',
      jobId: 'j1',
      status: 'applied',
      source: 'feed',
      createdAt: DateTime.now(),
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
      applicantId: 'ap1',
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
