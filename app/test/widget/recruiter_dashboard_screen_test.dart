import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/recruiter_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/recruiter/recruiter_dashboard_screen.dart';

import '../helpers/fake_recruiter_jobs_repository.dart';

Widget _wrap(FakeRecruiterJobsRepository repo) => ProviderScope(
      overrides: [recruiterJobsRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: const RecruiterDashboardScreen(),
      ),
    );

void main() {
  testWidgets('shows empty CTA when there are no jobs', (tester) async {
    await tester.pumpWidget(_wrap(FakeRecruiterJobsRepository()));
    await tester.pumpAndSettle();

    expect(find.text('Post your first job'), findsOneWidget);
  });

  testWidgets('renders summary counts and recent jobs', (tester) async {
    final repo = FakeRecruiterJobsRepository(
      jobsPage: RecruiterJobsPageDto(
        items: [
          fakeRecruiterJob(
            id: 'j1',
            title: 'Backend Engineer',
            applicantCount: 5,
            surfacedMatchCount: 3,
          ),
          fakeRecruiterJob(
            id: 'j2',
            status: 'closed',
            applicantCount: 20,
            surfacedMatchCount: 10,
          ),
        ],
      ),
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    // Summary numbers chosen so none collides with a job card's counts
    // (cards render 5, 3, 20, 10).
    // openJobs = 1 (j2 is closed)
    expect(find.text('Open jobs'), findsOneWidget);
    expect(find.text('1'), findsOneWidget);
    // totalApplicants = 25, totalSurfacedMatches = 13
    expect(find.text('25'), findsOneWidget);
    expect(find.text('13'), findsOneWidget);
    expect(find.text('Recent jobs'), findsOneWidget);
    expect(find.text('Backend Engineer'), findsOneWidget);
  });
}
