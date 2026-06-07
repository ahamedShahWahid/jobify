import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_screen.dart';

import '../helpers/fake_recruiter_jobs_repository.dart';

Widget _wrap(FakeRecruiterJobsRepository repo) => ProviderScope(
      overrides: [recruiterJobsRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: const RecruiterJobsScreen(),
      ),
    );

void main() {
  testWidgets('empty state prompts to post a role', (tester) async {
    await tester.pumpWidget(_wrap(FakeRecruiterJobsRepository()));
    await tester.pumpAndSettle();

    expect(find.text('No jobs yet'), findsOneWidget);
    expect(find.text('Post your first role'), findsOneWidget);
  });

  testWidgets('renders a job card with title and counts', (tester) async {
    final repo = FakeRecruiterJobsRepository(
      jobsPage: RecruiterJobsPageDto(
        items: [
          fakeRecruiterJob(
            id: 'j1',
            title: 'Flutter Engineer',
            applicantCount: 4,
            surfacedMatchCount: 7,
          ),
        ],
      ),
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('Flutter Engineer'), findsOneWidget);
    expect(find.text('4'), findsOneWidget);
    expect(find.text('7'), findsOneWidget);
    expect(find.text('Open'), findsOneWidget);
  });

  testWidgets('show-closed toggle is present and flips', (tester) async {
    final repo = FakeRecruiterJobsRepository(
      jobsPage: RecruiterJobsPageDto(
        items: [fakeRecruiterJob(id: 'j1')],
      ),
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    final toggle = find.byType(SwitchListTile);
    expect(toggle, findsOneWidget);
    expect(tester.widget<SwitchListTile>(toggle).value, isFalse);

    await tester.tap(toggle);
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(toggle).value, isTrue);
  });
}
