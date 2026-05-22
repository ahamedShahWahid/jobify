import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_error_view.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';
import 'package:kpa_app/presentation/widgets/kpa_score_badge.dart';

// NOTE: tests use ThemeData.light() instead of buildTheme() because
// buildTheme triggers google_fonts to fetch Inter, which fails in
// offline test environments. Production wraps in buildTheme.
Widget _wrap(Widget child) {
  return MaterialApp(
    theme: ThemeData.light(useMaterial3: true),
    home: Scaffold(body: child),
  );
}

void main() {
  testWidgets('KpaLoadingView renders an adaptive spinner', (tester) async {
    await tester.pumpWidget(
      _wrap(const KpaLoadingView(message: 'Loading…')),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Loading…'), findsOneWidget);
  });

  testWidgets('KpaErrorView with NetworkException shows network copy',
      (tester) async {
    await tester.pumpWidget(
      _wrap(const KpaErrorView(error: NetworkException(message: 'oops'))),
    );
    expect(find.textContaining("Couldn't reach KPA"), findsOneWidget);
  });

  testWidgets('KpaErrorView with onRetry shows the button', (tester) async {
    var taps = 0;
    await tester.pumpWidget(
      _wrap(
        KpaErrorView(
          error: const NetworkException(),
          onRetry: () => taps++,
        ),
      ),
    );
    await tester.tap(find.text('Try again'));
    expect(taps, 1);
  });

  testWidgets('KpaEmptyState renders headline + body + action',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        KpaEmptyState(
          headline: 'Nothing here',
          body: 'Try something else',
          primaryAction: FilledButton(
            onPressed: () {},
            child: const Text('Go'),
          ),
        ),
      ),
    );
    expect(find.text('Nothing here'), findsOneWidget);
    expect(find.text('Try something else'), findsOneWidget);
    expect(find.text('Go'), findsOneWidget);
  });

  testWidgets('KpaScoreBadge renders rounded percent', (tester) async {
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.857)));
    expect(find.text('86%'), findsOneWidget);
  });

  testWidgets('KpaScoreBadge bands by score', (tester) async {
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.5)));
    expect(find.text('50%'), findsOneWidget);
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.7)));
    expect(find.text('70%'), findsOneWidget);
    await tester.pumpWidget(_wrap(const KpaScoreBadge(score: 0.95)));
    expect(find.text('95%'), findsOneWidget);
  });
}
