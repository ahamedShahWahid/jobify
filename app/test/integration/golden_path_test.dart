import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/app.dart';
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';
import 'package:kpa_app/data/feed/match_generator.dart';
import 'package:kpa_app/data/jobs/applications_repository_impl.dart';
import 'package:kpa_app/data/jobs/job_status.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:kpa_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/splash/bootstrap_controller.dart';

import '../helpers/fake_repositories.dart';

class _SignedInAuthStateNotifier extends AuthStateNotifier {
  @override
  AuthState build() =>
      const SignedIn(userId: 'u1', email: 'u@e.com', role: UserRole.applicant, displayName: 'U');
}

class _Bootstrapped extends BootstrapController {
  @override
  Future<BootstrapOutcome> build() async => BootstrapOutcome.feed;
}

void main() {
  testWidgets(
    'golden path: signed-in user lands on feed, opens detail, applies',
    (tester) async {
      final job = JobSummaryDto(
        id: 'j1',
        title: 'Senior Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime(2026, 5, 18),
      );
      const employer = EmployerSummaryDto(id: 'e1', name: 'Acme Co');
      const match = MatchSummaryDto(
        id: 'm1',
        totalScore: 0.85,
        scoreComponents: {},
        explanation: ExplanationDto(
          fit: 'great fit',
          generator: MatchGenerator.templated,
          generatorVersion: '1',
        ),
      );
      final feedItem = FeedItemDto(
        match: match,
        job: job,
        employer: employer,
      );
      final detail = JobDetailDto(
        job: job,
        employer: employer,
        match: match,
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            // Bootstrap returns 'go to feed' immediately — no token/refresh.
            bootstrapControllerProvider.overrideWith(_Bootstrapped.new),
            // Auth state starts as SignedIn so the router doesn't redirect to
            // /signin.
            authStateProvider.overrideWith(_SignedInAuthStateNotifier.new),
            authRepositoryProvider.overrideWithValue(
              FakeAuthRepository(
                initial: const SignedIn(userId: 'u1', email: 'u@e.com', role: UserRole.applicant),
              ),
            ),
            feedRepositoryProvider.overrideWithValue(
              FakeFeedRepository(items: [feedItem]),
            ),
            jobsRepositoryProvider.overrideWithValue(
              FakeJobsRepository(detail: detail),
            ),
            applicationsRepositoryProvider.overrideWithValue(
              FakeApplicationsRepository(),
            ),
            savedJobsRepositoryProvider.overrideWithValue(
              FakeSavedJobsRepository(),
            ),
            meRepositoryProvider.overrideWithValue(FakeMeRepository()),
          ],
          child: const KpaApp(),
        ),
      );
      await tester.pumpAndSettle();

      // After bootstrap resolves to BootstrapOutcome.feed, SplashScreen
      // calls context.go('/feed'), which the router allows because auth is
      // SignedIn.  The feed screen title is 'For you'.
      expect(find.text('For you'), findsOneWidget);
      expect(find.text('Senior Engineer'), findsOneWidget);

      // Tap the job card → navigates to /feed/jobs/j1.
      await tester.tap(find.text('Senior Engineer'));
      await tester.pumpAndSettle();

      // Job detail screen shows the match explanation section and Apply
      // button.
      expect(find.text('Why this match'), findsOneWidget);
      expect(find.text('Apply'), findsOneWidget);

      // Tap Apply — FakeJobsRepository.applyTo mutates _detail; the
      // controller invalidates jobDetailControllerProvider which re-fetches
      // and rebuilds ActionBar with the new ApplicationDto.
      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();

      // Action bar must now show Withdraw and Apply must be gone.
      expect(find.text('Withdraw'), findsOneWidget);
      expect(find.text('Apply'), findsNothing);
    },
  );
}
