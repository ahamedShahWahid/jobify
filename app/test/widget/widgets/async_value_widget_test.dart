import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';

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
  testWidgets('renders loading by default', (tester) async {
    await tester.pumpWidget(
      _wrap(
        AsyncValueWidget<int>(
          value: const AsyncValue.loading(),
          data: (d) => Text('$d'),
        ),
      ),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('renders data when AsyncValue.data', (tester) async {
    await tester.pumpWidget(
      _wrap(
        AsyncValueWidget<int>(
          value: const AsyncValue.data(42),
          data: (d) => Text('$d'),
        ),
      ),
    );
    expect(find.text('42'), findsOneWidget);
  });

  testWidgets('renders JobifyErrorView with typed exception copy on error',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        AsyncValueWidget<int>(
          value: AsyncValue.error(
            const NetworkException(),
            StackTrace.current,
          ),
          data: (d) => Text('$d'),
        ),
      ),
    );
    expect(find.textContaining("Couldn't reach Jobify"), findsOneWidget);
  });

  testWidgets('renders empty when isEmpty predicate matches', (tester) async {
    await tester.pumpWidget(
      _wrap(
        AsyncValueWidget<List<int>>(
          value: const AsyncValue.data(<int>[]),
          isEmpty: (d) => d.isEmpty,
          empty: () => const Text('NOTHING'),
          data: (d) => Text('${d.length}'),
        ),
      ),
    );
    expect(find.text('NOTHING'), findsOneWidget);
  });

  testWidgets('renders data when isEmpty predicate is false', (tester) async {
    await tester.pumpWidget(
      _wrap(
        AsyncValueWidget<List<int>>(
          value: const AsyncValue.data(<int>[1, 2]),
          isEmpty: (d) => d.isEmpty,
          empty: () => const Text('NOTHING'),
          data: (d) => Text('${d.length}'),
        ),
      ),
    );
    expect(find.text('2'), findsOneWidget);
  });
}
