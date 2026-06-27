import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/presentation/widgets/arrive.dart';

Widget _wrap(Widget child, {bool disableAnimations = false}) => MediaQuery(
      data: MediaQueryData(disableAnimations: disableAnimations),
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: Scaffold(body: child),
      ),
    );

void main() {
  testWidgets('reduced motion renders child immediately, fully opaque',
      (tester) async {
    await tester.pumpWidget(
      _wrap(const Arrive(index: 3, child: Text('hi')), disableAnimations: true),
    );
    // No pumpAndSettle needed — should be visible on first frame.
    expect(find.text('hi'), findsOneWidget);
    final opacity = tester.widget<Opacity>(
      find.ancestor(of: find.text('hi'), matching: find.byType(Opacity)),
    );
    expect(opacity.opacity, 1.0);
  });

  testWidgets('with motion, child settles to visible', (tester) async {
    await tester.pumpWidget(_wrap(const Arrive(index: 0, child: Text('hi'))));
    await tester.pumpAndSettle();
    expect(find.text('hi'), findsOneWidget);
    final opacity = tester.widget<Opacity>(
      find.ancestor(of: find.text('hi'), matching: find.byType(Opacity)),
    );
    expect(opacity.opacity, 1.0);
  });
}
