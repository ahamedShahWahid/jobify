import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
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
  testWidgets('row shows current stage and menu changes it', (tester) async {
    final repo = FakeRecruiterJobsRepository(
      applicantsPage: ApplicantsOfJobPageDto(items: [fakeApplicantOfJob()]),
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('Applied'), findsOneWidget);

    await tester.tap(find.byTooltip('Change stage').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Shortlisted').last);
    await tester.pumpAndSettle();

    expect(repo.stagesSet, isNotEmpty); // recorded call
    expect(repo.stagesSet.last, ('j1', 'app1', ApplicationStage.shortlisted));
    expect(find.text('Shortlisted'), findsWidgets); // optimistic label
  });

  testWidgets('failure reverts the label and shows a snackbar', (tester) async {
    final repo = FakeRecruiterJobsRepository(
      applicantsPage: ApplicantsOfJobPageDto(items: [fakeApplicantOfJob()]),
    )..setStageError = 'boom';
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Change stage').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Interview').last);
    await tester.pumpAndSettle();

    expect(find.text('Applied'), findsWidgets); // reverted
    expect(find.textContaining("Couldn't update"), findsOneWidget);
  });

  testWidgets('withdrawn-slug failure shows the candidate-withdrew snackbar',
      (tester) async {
    final repo = FakeRecruiterJobsRepository(
      applicantsPage: ApplicantsOfJobPageDto(items: [fakeApplicantOfJob()]),
    )..setStageError = 'application_withdrawn';
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Change stage').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Offer').last);
    await tester.pumpAndSettle();

    expect(find.text('Applied'), findsWidgets); // reverted
    expect(find.text('Candidate withdrew'), findsOneWidget);
  });
}
