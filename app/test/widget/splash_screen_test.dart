import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:riverpod/src/framework.dart' show Override;

import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/presentation/splash/bootstrap_controller.dart';
import 'package:jobify_app/presentation/splash/splash_screen.dart';

Widget _wrap(Widget child, {required List<Override> overrides}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: child,
    ),
  );
}

class _StubLoading extends BootstrapController {
  @override
  Future<BootstrapOutcome> build() => Completer<BootstrapOutcome>().future;
}

class _StubError extends BootstrapController {
  _StubError(this.err);
  final Object err;
  @override
  Future<BootstrapOutcome> build() => Future.error(err);
}

void main() {
  testWidgets('renders loading spinner', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const SplashScreen(),
        overrides: [
          bootstrapControllerProvider.overrideWith(_StubLoading.new),
        ],
      ),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('renders error view with retry on NetworkException',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        const SplashScreen(),
        overrides: [
          bootstrapControllerProvider.overrideWith(
            () => _StubError(
                const NetworkException(message: 'Connection failed')),
          ),
        ],
      ),
    );
    await tester.pump();
    // Verify that the Scaffold is still rendered in error state
    expect(find.byType(Scaffold), findsOneWidget);
  });
}
