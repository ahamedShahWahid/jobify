// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/presentation/applications/applications_screen.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/auth/sign_in_screen.dart';
import 'package:kpa_app/presentation/feed/feed_screen.dart';
import 'package:kpa_app/presentation/job_detail/job_detail_screen.dart';
import 'package:kpa_app/presentation/profile/edit_profile_screen.dart';
import 'package:kpa_app/presentation/notifications/notifications_screen.dart';
import 'package:kpa_app/presentation/privacy/delete_account_screen.dart';
import 'package:kpa_app/presentation/privacy/privacy_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_dashboard_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_employer_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_screen.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_profile_screen.dart';
import 'package:kpa_app/presentation/resume/resume_screen.dart';
import 'package:kpa_app/presentation/profile/profile_screen.dart';
import 'package:kpa_app/presentation/routing/role_redirect.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/saved/saved_screen.dart';
import 'package:kpa_app/presentation/splash/splash_screen.dart';
import 'package:kpa_app/presentation/widgets/kpa_recruiter_shell_scaffold.dart';
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

/// Deep-link preservation across the sign-in flow.
///
/// When a signed-out user opens a protected route (a deep link from a
/// push notification, an OS share, a bookmarked URL on web), we redirect
/// to `/signin?next=<original-location>` and, on successful sign-in,
/// route them to the encoded destination instead of the default `/feed`.
///
/// Open-redirect protection: only same-origin paths are honoured. Any
/// `next` whose decoded form does not start with `/` or starts with `//`
/// (protocol-relative URL) is ignored — falls back to `/feed`.
String? safeNextLocation(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  final decoded = Uri.decodeComponent(raw);
  if (!decoded.startsWith('/')) return null;
  if (decoded.startsWith('//')) return null;
  if (decoded == Routes.signIn) return null;
  return decoded;
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
        if (loc == Routes.signIn) return null;
        // Preserve the original destination as ?next so we can land them
        // back here after sign-in succeeds.
        final next = Uri.encodeComponent(state.uri.toString());
        return '${Routes.signIn}?next=$next';
      }
      if (auth is SignedIn && loc == Routes.signIn) {
        final next = safeNextLocation(state.uri.queryParameters['next']);
        return next ?? Routes.feed;
      }
      if (auth is SignedIn) {
        final r = roleAwareRedirect(role: auth.role, loc: loc);
        if (r != null) return r;
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
      GoRoute(
        path: Routes.onboardingEmployer,
        builder: (_, __) => const SizedBox.shrink(), // TODO(Task 9): replace with const EmployerOnboardingScreen()
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
                routes: [
                  GoRoute(
                    path: 'edit',
                    builder: (_, __) => const EditProfileScreen(),
                  ),
                  GoRoute(
                    path: 'resume',
                    builder: (_, __) => const ResumeScreen(),
                  ),
                  GoRoute(
                    path: 'notifications',
                    builder: (_, __) => const NotificationsScreen(),
                    routes: [
                      GoRoute(
                        path: 'jobs/:id',
                        builder: (_, s) =>
                            JobDetailScreen(jobId: s.pathParameters['id']!),
                      ),
                    ],
                  ),
                  GoRoute(
                    path: 'privacy',
                    builder: (_, __) => const PrivacyScreen(),
                    routes: [
                      GoRoute(
                        path: 'delete',
                        builder: (_, __) => const DeleteAccountScreen(),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
      // Recruiter shell — gated by roleAwareRedirect in the redirect callback.
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) =>
            KpaRecruiterShellScaffold(shell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.recruiterDashboard,
                builder: (_, __) => const RecruiterDashboardScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.recruiterJobs,
                builder: (_, __) => const RecruiterJobsScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.recruiterEmployer,
                builder: (_, __) => const RecruiterEmployerScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.recruiterProfile,
                builder: (_, __) => const RecruiterProfileScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
}
