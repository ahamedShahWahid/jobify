import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/dsr/dsr_repository_impl.dart';
import 'package:kpa_app/presentation/privacy/delete_account_screen.dart';

import '../../../helpers/fake_repositories.dart';

Widget _buildApp() {
  return ProviderScope(
    overrides: [
      dsrRepositoryProvider.overrideWithValue(FakeDsrRepository()),
    ],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: const DeleteAccountScreen(),
    ),
  );
}

void main() {
  testWidgets('submit button is disabled when text field is empty or mistyped',
      (tester) async {
    await tester.pumpWidget(_buildApp());
    await tester.pumpAndSettle();

    // Helper to read the current onPressed from the submit FilledButton.
    FilledButton submitButton() => tester.widget(
          find.ancestor(
            of: find.text('Delete my account'),
            matching: find.byType(FilledButton),
          ),
        );

    // Initially empty — button must be disabled.
    expect(submitButton().onPressed, isNull);

    // Wrong text — still disabled.
    await tester.enterText(find.byType(TextField), 'wrong');
    await tester.pump();
    expect(submitButton().onPressed, isNull);

    // Partially correct — still disabled.
    await tester.enterText(find.byType(TextField), 'DELETE_MY_ACCOUN');
    await tester.pump();
    expect(submitButton().onPressed, isNull);
  });

  testWidgets(
      'submit button is enabled when text field contains exactly '
      'DELETE_MY_ACCOUNT', (tester) async {
    await tester.pumpWidget(_buildApp());
    await tester.pumpAndSettle();

    FilledButton submitButton() => tester.widget(
          find.ancestor(
            of: find.text('Delete my account'),
            matching: find.byType(FilledButton),
          ),
        );

    // Disabled before typing.
    expect(submitButton().onPressed, isNull);

    await tester.enterText(find.byType(TextField), 'DELETE_MY_ACCOUNT');
    await tester.pump();

    // Enabled after exact match.
    expect(submitButton().onPressed, isNotNull);
  });
}
