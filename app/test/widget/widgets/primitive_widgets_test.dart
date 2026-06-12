import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_error_view.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';
import 'package:jobify_app/presentation/widgets/jobify_score_badge.dart';

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
  testWidgets('JobifyLoadingView renders an adaptive spinner', (tester) async {
    await tester.pumpWidget(
      _wrap(const JobifyLoadingView(message: 'Loading…')),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Loading…'), findsOneWidget);
  });

  testWidgets('JobifyErrorView with NetworkException shows network copy',
      (tester) async {
    await tester.pumpWidget(
      _wrap(const JobifyErrorView(error: NetworkException(message: 'oops'))),
    );
    expect(find.textContaining("Couldn't reach Jobify"), findsOneWidget);
  });

  testWidgets('JobifyErrorView with onRetry shows the button', (tester) async {
    var taps = 0;
    await tester.pumpWidget(
      _wrap(
        JobifyErrorView(
          error: const NetworkException(),
          onRetry: () => taps++,
        ),
      ),
    );
    await tester.tap(find.text('Try again'));
    expect(taps, 1);
  });

  testWidgets('JobifyEmptyState renders headline + body + action',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        JobifyEmptyState(
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

  testWidgets('JobifyScoreBadge renders rounded percent', (tester) async {
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.857)));
    expect(find.text('86%'), findsOneWidget);
  });

  testWidgets('JobifyScoreBadge bands by score', (tester) async {
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.5)));
    expect(find.text('50%'), findsOneWidget);
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.7)));
    expect(find.text('70%'), findsOneWidget);
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.95)));
    expect(find.text('95%'), findsOneWidget);
  });
}
