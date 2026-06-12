import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/recruiter/job_applicants_screen.dart';

import '../helpers/fake_recruiter_jobs_repository.dart';

Widget _wrap(FakeRecruiterJobsRepository repo) => ProviderScope(
      overrides: [recruiterJobsRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: const JobApplicantsScreen(jobId: 'j1'),
      ),
    );

void main() {
  testWidgets('empty state when no applicants', (tester) async {
    await tester.pumpWidget(_wrap(FakeRecruiterJobsRepository()));
    await tester.pumpAndSettle();

    expect(find.text('No applicants yet'), findsOneWidget);
  });

  testWidgets('renders an applicant with score, fit, and download button',
      (tester) async {
    final repo = FakeRecruiterJobsRepository(
      applicantsPage: ApplicantsOfJobPageDto(
        items: [fakeApplicantOfJob()],
      ),
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('Alice Candidate'), findsOneWidget);
    expect(find.text('82%'), findsOneWidget); // JobifyScoreBadge for 0.82
    expect(find.text('Strong skills match.'), findsOneWidget);
    expect(
      find.widgetWithText(OutlinedButton, 'Download résumé'),
      findsOneWidget,
    );
  });

  testWidgets('falls back to email when display name is null', (tester) async {
    final repo = FakeRecruiterJobsRepository(
      applicantsPage: ApplicantsOfJobPageDto(
        items: [fakeApplicantOfJob(displayName: null)],
      ),
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('alice@example.com'), findsOneWidget);
  });
}
