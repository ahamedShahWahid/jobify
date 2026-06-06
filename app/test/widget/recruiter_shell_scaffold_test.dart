import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_dashboard_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_employer_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_profile_screen.dart';
import 'package:kpa_app/presentation/widgets/kpa_recruiter_shell_scaffold.dart';

void main() {
  testWidgets('recruiter shell shows four tabs and switches branches',
      (tester) async {
    final router = GoRouter(
      initialLocation: '/recruiter/dashboard',
      routes: [
        StatefulShellRoute.indexedStack(
          builder: (_, __, shell) => KpaRecruiterShellScaffold(shell: shell),
          branches: [
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/dashboard',
                  builder: (_, __) => const RecruiterDashboardScreen(),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/jobs',
                  builder: (_, __) => const RecruiterJobsScreen(),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/employer',
                  builder: (_, __) => const RecruiterEmployerScreen(),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/recruiter/profile',
                  builder: (_, __) => const RecruiterProfileScreen(),
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
    expect(find.text('Recruiter Dashboard'), findsOneWidget);

    await tester.tap(find.text('Jobs'));
    await tester.pumpAndSettle();
    expect(find.text('Recruiter Jobs'), findsOneWidget);
  });
}
