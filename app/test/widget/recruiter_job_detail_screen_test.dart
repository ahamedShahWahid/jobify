import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/recruiter/recruiter_job_detail_screen.dart';

import '../helpers/fake_recruiter_jobs_repository.dart';

Widget _wrap(FakeRecruiterJobsRepository repo, String jobId) {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, __) => RecruiterJobDetailScreen(jobId: jobId),
      ),
    ],
  );
  return ProviderScope(
    overrides: [recruiterJobsRepositoryProvider.overrideWithValue(repo)],
    child: MaterialApp.router(
      theme: ThemeData.light(useMaterial3: true),
      routerConfig: router,
    ),
  );
}

void main() {
  testWidgets('fetches the job by id and renders its description '
      '(PERF-09: list rows have no description to render)', (tester) async {
    final repo = FakeRecruiterJobsRepository(
      getJobResult: fakeRecruiterJob(id: 'job-1', title: 'Staff Engineer'),
    );

    await tester.pumpWidget(_wrap(repo, 'job-1'));
    await tester.pumpAndSettle();

    expect(repo.getJobCalledWith, 'job-1');
    expect(find.text('Staff Engineer'), findsOneWidget);
    expect(find.text('A great role doing great things.'), findsOneWidget);
  });
}
