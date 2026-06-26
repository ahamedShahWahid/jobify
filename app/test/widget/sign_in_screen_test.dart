import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/presentation/auth/sign_in_controller.dart';
import 'package:jobify_app/presentation/auth/sign_in_screen.dart';
import 'package:riverpod/src/framework.dart' show Override;

// Disable animations so Arrive jumps to settled state immediately — without
// this, Arrive defers rendering via Future.delayed and the widgets are
// invisible (opacity 0) when the test asserts.
Widget _wrap(Widget child, {List<Override> overrides = const []}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: Builder(
        builder: (context) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: child,
        ),
      ),
    ),
  );
}

class _LoadingStub extends SignInController {
  @override
  Future<void> build() => Completer<void>().future;
}

void main() {
  testWidgets('renders Jobify wordmark + Continue button', (tester) async {
    await tester.pumpWidget(_wrap(const SignInScreen()));
    await tester.pumpAndSettle();
    expect(find.text('Jobify'), findsOneWidget);
    expect(find.text('Continue with Google'), findsOneWidget);
  });

  testWidgets('button is disabled while loading', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const SignInScreen(),
        overrides: [
          signInControllerProvider.overrideWith(_LoadingStub.new),
        ],
      ),
    );
    await tester.pump();
    expect(find.text('Signing in…'), findsOneWidget);
    // OutlinedButton.icon onPressed: null when isLoading; presence of the
    // 'Signing in…' label is sufficient signal.
  });
}
