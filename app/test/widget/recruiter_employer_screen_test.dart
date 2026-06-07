import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/recruiter/active_employer_provider.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_employer_screen.dart';

import '../helpers/fake_employer_team_repository.dart';

EmployerDto _employer() => EmployerDto(
      id: 'e1',
      name: 'Acme Corp',
      gst: '22AAAAA0000A1Z5',
      createdAt: DateTime.utc(2026),
    );

Widget _wrap(
  FakeEmployerTeamRepository repo, {
  required String myUserId,
}) =>
    ProviderScope(
      overrides: [
        employerTeamRepositoryProvider.overrideWithValue(repo),
        recruiterEmployersProvider.overrideWith((ref) async => [_employer()]),
        authStateProvider.overrideWithValue(
          SignedIn(
            userId: myUserId,
            email: 'me@x.com',
            role: UserRole.recruiter,
          ),
        ),
      ],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: const RecruiterEmployerScreen(),
      ),
    );

void main() {
  testWidgets('owner sees roster, invite form, and member menus',
      (tester) async {
    final repo = FakeEmployerTeamRepository(
      members: [
        fakeMember(userId: 'u1', role: 'owner', displayName: 'Olivia Owner'),
        fakeMember(userId: 'u2', displayName: 'Mona Member'),
      ],
      invites: [fakeInvite(email: 'pending@example.com')],
    );
    await tester.pumpWidget(_wrap(repo, myUserId: 'u1'));
    await tester.pumpAndSettle();

    expect(find.text('Acme Corp'), findsOneWidget);
    expect(find.text('Olivia Owner'), findsOneWidget);
    expect(find.text('Mona Member'), findsOneWidget);
    // Owner-only invite form.
    expect(find.widgetWithText(FilledButton, 'Send'), findsOneWidget);
    // Member menus (one per row).
    expect(find.byType(PopupMenuButton<String>), findsNWidgets(2));
    // Pending invite shown.
    expect(find.text('pending@example.com'), findsOneWidget);
  });

  testWidgets('member sees read-only roster (no invite form, no menus)',
      (tester) async {
    final repo = FakeEmployerTeamRepository(
      members: [
        fakeMember(userId: 'u1', role: 'owner', displayName: 'Olivia Owner'),
        fakeMember(userId: 'u2', displayName: 'Mona Member'),
      ],
    );
    await tester.pumpWidget(_wrap(repo, myUserId: 'u2'));
    await tester.pumpAndSettle();

    expect(find.text('Olivia Owner'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Send'), findsNothing);
    expect(find.byType(PopupMenuButton<String>), findsNothing);
  });

  testWidgets('owner can submit an invite', (tester) async {
    final repo = FakeEmployerTeamRepository(
      members: [fakeMember(userId: 'u1', role: 'owner')],
    );
    await tester.pumpWidget(_wrap(repo, myUserId: 'u1'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextField, 'Email'),
      'newbie@example.com',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Send'));
    await tester.pumpAndSettle();

    expect(repo.createdInvite, isNotNull);
    expect(repo.createdInvite!.email, 'newbie@example.com');
    expect(repo.createdInvite!.role, 'member');
  });
}
