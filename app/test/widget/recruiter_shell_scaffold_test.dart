import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/presentation/widgets/jobify_recruiter_shell_scaffold.dart';

/// Trivial branch body so this test stays focused on the shell scaffold's
/// tab bar and branch switching — not the real screens' provider wiring
/// (those are exercised in their own widget tests).
class _Stub extends StatelessWidget {
  const _Stub(this.label);
  final String label;
  @override
  Widget build(BuildContext context) =>
      Scaffold(body: Center(child: Text(label)));
}

void main() {
  testWidgets('recruiter shell shows four tabs and switches branches',
      (tester) async {
    final router = GoRouter(
      initialLocation: '/recruiter/dashboard',
      routes: [
        StatefulShellRoute.indexedStack(
          builder: (_, __, shell) => JobifyRecruiterShellScaffold(shell: shell),
          branches: [
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/dashboard',
                  builder: (_, __) => const _Stub('DASH BODY'),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/jobs',
                  builder: (_, __) => const _Stub('JOBS BODY'),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/employer',
                  builder: (_, __) => const _Stub('EMPLOYER BODY'),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/profile',
                  builder: (_, __) => const _Stub('PROFILE BODY'),
                ),
              ],
            ),
          ],
        ),
      ],
    );

    await tester.pumpWidget(
      MaterialApp.router(
        theme: ThemeData.light(useMaterial3: true),
        routerConfig: router,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Dashboard'), findsOneWidget);
    expect(find.text('Jobs'), findsOneWidget);
    expect(find.text('Employer'), findsOneWidget);
    expect(find.text('DASH BODY'), findsOneWidget);

    await tester.tap(find.text('Jobs'));
    await tester.pumpAndSettle();
    expect(find.text('JOBS BODY'), findsOneWidget);
  });
}
