import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/consents/consents_repository_impl.dart';
import 'package:jobify_app/data/dsr/dsr_repository_impl.dart';
import 'package:jobify_app/presentation/privacy/privacy_screen.dart';

import '../../../helpers/fake_repositories.dart';

Widget _buildApp({
  required FakeConsentsRepository consents,
  required FakeDsrRepository dsr,
}) {
  return ProviderScope(
    overrides: [
      consentsRepositoryProvider.overrideWithValue(consents),
      dsrRepositoryProvider.overrideWithValue(dsr),
    ],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: const PrivacyScreen(),
    ),
  );
}

void main() {
  testWidgets('renders three v0-visible consent toggles', (tester) async {
    final fakeConsents = FakeConsentsRepository();
    await tester.pumpWidget(
      _buildApp(
        consents: fakeConsents,
        dsr: FakeDsrRepository(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Service updates'), findsOneWidget);
    expect(find.text('Job recommendations'), findsOneWidget);
    expect(find.text('In-app notifications'), findsOneWidget);
    // Reserved scopes are deliberately hidden.
    expect(find.text('WhatsApp notifications'), findsNothing);
    expect(find.text('whatsapp_notifications'), findsNothing);
  });

  testWidgets('toggling email_marketing calls patch()', (tester) async {
    final fakeConsents = FakeConsentsRepository();
    await tester.pumpWidget(
      _buildApp(
        consents: fakeConsents,
        dsr: FakeDsrRepository(),
      ),
    );
    await tester.pumpAndSettle();

    // Tap the SwitchListTile by its key — tapping anywhere on the tile fires
    // the onChanged callback.
    await tester.tap(find.byKey(const Key('toggle-email_marketing')));
    await tester.pumpAndSettle();

    expect(fakeConsents.patchCallCount, 1);
  });

  testWidgets('toggling email_transactional OFF shows confirmation dialog',
      (tester) async {
    final fakeConsents = FakeConsentsRepository();
    await tester.pumpWidget(
      _buildApp(
        consents: fakeConsents,
        dsr: FakeDsrRepository(),
      ),
    );
    await tester.pumpAndSettle();

    // email_transactional is ON by default (granted: true). Tapping toggles it
    // OFF, which should trigger the confirmation dialog.
    await tester.tap(find.byKey(const Key('toggle-email_transactional')));
    await tester.pumpAndSettle();

    expect(find.text('Turn off service emails?'), findsOneWidget);
    // PATCH must NOT be called until the user confirms.
    expect(fakeConsents.patchCallCount, 0);
  });
}
