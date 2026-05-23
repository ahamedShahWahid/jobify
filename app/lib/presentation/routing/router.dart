// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:kpa_app/presentation/applications/applications_screen.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/auth/sign_in_screen.dart';
import 'package:kpa_app/presentation/feed/feed_screen.dart';
import 'package:kpa_app/presentation/job_detail/job_detail_screen.dart';
import 'package:kpa_app/presentation/profile/profile_screen.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/saved/saved_screen.dart';
import 'package:kpa_app/presentation/splash/splash_screen.dart';
import 'package:kpa_app/presentation/widgets/kpa_shell_scaffold.dart';

part 'router.g.dart';

/// Bridges Riverpod's AuthState changes into GoRouter's `refreshListenable`.
class _AuthChangeNotifier extends ChangeNotifier {
  _AuthChangeNotifier(Ref ref) {
    ref.listen<AuthState>(
      authStateProvider,
      (_, __) => notifyListeners(),
    );
  }
}

@Riverpod(keepAlive: true)
GoRouter router(Ref ref) {
  final authNotifier = _AuthChangeNotifier(ref);

  return GoRouter(
    initialLocation: Routes.splash,
    refreshListenable: authNotifier,
    redirect: (context, state) {
      final auth = ref.read(authStateProvider);
      final loc = state.matchedLocation;

      // Splash is reachable only on cold start. Its controller pushes the
      // user to /feed or /signin.
      if (loc == Routes.splash) return null;

      if (auth is SignedOut) {
        return loc == Routes.signIn ? null : Routes.signIn;
      }
      if (auth is SignedIn && loc == Routes.signIn) {
        return Routes.feed;
      }
      return null;
    },
    routes: [
      GoRoute(
        path: Routes.splash,
        builder: (_, __) => const SplashScreen(),
      ),
      GoRoute(
        path: Routes.signIn,
        builder: (_, __) => const SignInScreen(),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => KpaShellScaffold(shell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.feed,
                builder: (_, __) => const FeedScreen(),
                routes: [
                  GoRoute(
                    path: 'jobs/:id',
                    builder: (_, s) =>
                        JobDetailScreen(jobId: s.pathParameters['id']!),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.saved,
                builder: (_, __) => const SavedScreen(),
                routes: [
                  GoRoute(
                    path: 'jobs/:id',
                    builder: (_, s) =>
                        JobDetailScreen(jobId: s.pathParameters['id']!),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.applications,
                builder: (_, __) => const ApplicationsScreen(),
                routes: [
                  GoRoute(
                    path: 'jobs/:id',
                    builder: (_, s) =>
                        JobDetailScreen(jobId: s.pathParameters['id']!),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.profile,
                builder: (_, __) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
}
