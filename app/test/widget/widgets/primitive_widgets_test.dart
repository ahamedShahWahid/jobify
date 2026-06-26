import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
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

  testWidgets('JobifyScoreBadge renders rounded percent in mono',
      (tester) async {
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.857)));
    expect(find.text('86%'), findsOneWidget);
  });

  test('JobifyScoreBadge.isStrong gates on 0.80', () {
    expect(JobifyScoreBadge.isStrong(0.79), isFalse);
    expect(JobifyScoreBadge.isStrong(0.80), isTrue);
    expect(JobifyScoreBadge.isStrong(0.95), isTrue);
  });

  testWidgets('strong match uses brand blue, weak uses inkSoft',
      (tester) async {
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.95)));
    final strong = tester.widget<Text>(find.text('95%'));
    expect(strong.style?.color, JobifyColors.brandBlueLight);

    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.5)));
    final weak = tester.widget<Text>(find.text('50%'));
    expect(weak.style?.color, JobifyColors.inkSoftLight);
  });
}
