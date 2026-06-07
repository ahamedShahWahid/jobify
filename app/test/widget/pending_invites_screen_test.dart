import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:kpa_app/presentation/invites/pending_invites_screen.dart';

import '../helpers/fake_employer_team_repository.dart';
import '../helpers/fake_repositories.dart';

Widget _wrap(FakeEmployerTeamRepository repo) => ProviderScope(
      overrides: [
        employerTeamRepositoryProvider.overrideWithValue(repo),
        authRepositoryProvider.overrideWithValue(FakeAuthRepository()),
      ],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: const PendingInvitesScreen(),
      ),
    );

void main() {
  testWidgets('empty state when no invitations', (tester) async {
    await tester.pumpWidget(_wrap(FakeEmployerTeamRepository()));
    await tester.pumpAndSettle();
    expect(find.text('No invitations'), findsOneWidget);
  });

  testWidgets('renders an invite card with Accept/Decline', (tester) async {
    final repo = FakeEmployerTeamRepository(
      myInvites: [fakeMyInvite(employerName: 'Globex')],
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('Globex'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Accept'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Decline'), findsOneWidget);
  });

  testWidgets('accept forwards to the repository', (tester) async {
    final repo = FakeEmployerTeamRepository(
      myInvites: [fakeMyInvite(id: 'inv42')],
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, 'Accept'));
    await tester.pumpAndSettle();
    expect(repo.acceptedId, 'inv42');
  });

  testWidgets('decline forwards to the repository', (tester) async {
    final repo = FakeEmployerTeamRepository(
      myInvites: [fakeMyInvite(id: 'inv7')],
    );
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(TextButton, 'Decline'));
    await tester.pumpAndSettle();
    expect(repo.declinedId, 'inv7');
  });
}
