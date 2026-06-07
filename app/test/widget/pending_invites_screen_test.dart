import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/auth_repository.dart';
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:kpa_app/presentation/invites/pending_invites_screen.dart';

import '../helpers/fake_employer_team_repository.dart';
import '../helpers/fake_repositories.dart';

/// A FakeAuthRepository whose post-accept session refresh fails — used to prove
/// accept() still reports success when only refreshSession throws.
class _RefreshFailsAuthRepository extends FakeAuthRepository {
  @override
  Future<SignedIn> refreshSession() async => throw Exception('refresh down');
}

Widget _wrap(
  FakeEmployerTeamRepository repo, {
  AuthRepository? auth,
}) =>
    ProviderScope(
      overrides: [
        employerTeamRepositoryProvider.overrideWithValue(repo),
        authRepositoryProvider.overrideWithValue(auth ?? FakeAuthRepository()),
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

  testWidgets('accept still succeeds when the post-accept refresh fails',
      (tester) async {
    final repo = FakeEmployerTeamRepository(
      myInvites: [fakeMyInvite(id: 'inv9', employerName: 'Globex')],
    );
    await tester.pumpWidget(_wrap(repo, auth: _RefreshFailsAuthRepository()));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, 'Accept'));
    await tester.pumpAndSettle();

    // The accept call landed and the user sees success, despite refresh fail.
    expect(repo.acceptedId, 'inv9');
    expect(find.text('You joined Globex.'), findsOneWidget);
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
