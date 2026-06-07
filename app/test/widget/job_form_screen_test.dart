import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:kpa_app/presentation/recruiter/active_employer_provider.dart';
import 'package:kpa_app/presentation/recruiter/job_form_screen.dart';

import '../helpers/fake_recruiter_jobs_repository.dart';

EmployerDto _employer() => EmployerDto(
      id: 'e1',
      name: 'Acme Corp',
      createdAt: DateTime.utc(2026),
    );

Widget _wrap(FakeRecruiterJobsRepository repo) {
  final router = GoRouter(
    routes: [GoRoute(path: '/', builder: (_, __) => const JobFormScreen())],
  );
  return ProviderScope(
    overrides: [
      recruiterJobsRepositoryProvider.overrideWithValue(repo),
      recruiterEmployersProvider.overrideWith((ref) async => [_employer()]),
    ],
    child: MaterialApp.router(
      theme: ThemeData.light(useMaterial3: true),
      routerConfig: router,
    ),
  );
}

Future<void> _fillValid(WidgetTester tester) async {
  await tester.enterText(
    find.widgetWithText(TextFormField, 'Title'),
    'QA Lead',
  );
  await tester.enterText(
    find.widgetWithText(TextFormField, 'Description'),
    'We need a thorough QA lead for our growing team.',
  );
  await tester.enterText(
    find.widgetWithText(TextField, 'Add location'),
    'Bengaluru',
  );
  await tester.tap(find.byIcon(Icons.add));
  await tester.pump();
}

void main() {
  testWidgets('max-below-min experience blocks submit', (tester) async {
    final repo = FakeRecruiterJobsRepository();
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    await _fillValid(tester);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Min exp (yrs)'),
      '5',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Max exp (yrs)'),
      '2',
    );
    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(find.text('Must be ≥ min'), findsOneWidget);
    expect(repo.createdBody, isNull);
  });

  testWidgets('valid form submits a create body', (tester) async {
    final repo = FakeRecruiterJobsRepository();
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    await _fillValid(tester);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Min exp (yrs)'),
      '1',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Max exp (yrs)'),
      '4',
    );
    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(repo.createdBody, isNotNull);
    expect(repo.createdBody!['title'], 'QA Lead');
    expect(repo.createdBody!['employer_id'], 'e1');
    expect(repo.createdBody!['locations'], ['Bengaluru']);
    expect(repo.createdBody!['min_exp_years'], 1);
    expect(repo.createdBody!['max_exp_years'], 4);
  });
}
