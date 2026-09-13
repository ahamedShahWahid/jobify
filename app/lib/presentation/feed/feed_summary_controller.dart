import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'feed_summary_controller.g.dart';

/// Page size for the summary fetches — the server-side maximum for
/// /v1/applications and /v1/saved (`le=50`); anything larger is a 422.
/// Deliberately not shared with RecruiterDashboardController, whose recruiter
/// jobs route allows 100.
const feedSummaryPageLimit = 50;

/// Client-summed Applications/Saved counts for the Feed home summary.
/// Independent fetch (not a reuse of ApplicationsController/SavedController)
/// — mirrors RecruiterDashboardController's own independence from
/// RecruiterJobsController, so a limit change here never affects the real
/// Applications/Saved tab screens. One max-size page + the `*Approx` flag is
/// the same MVP-documented approximation RecruiterDashboardController uses.
class FeedSummary {
  const FeedSummary({
    required this.applicationsCount,
    required this.applicationsApprox,
    required this.savedCount,
    required this.savedApprox,
  });

  final int applicationsCount;
  final bool applicationsApprox;
  final int savedCount;
  final bool savedApprox;
}

@riverpod
class FeedSummaryController extends _$FeedSummaryController {
  @override
  Future<FeedSummary> build() async {
    final results = await Future.wait<Object?>([
      ref
          .read(applicationsRepositoryProvider)
          .fetchPage(limit: feedSummaryPageLimit),
      ref
          .read(savedJobsRepositoryProvider)
          .fetchPage(limit: feedSummaryPageLimit),
    ]);
    final applications = results[0]! as ApplicationsPageDto;
    final saved = results[1]! as SavedJobsPageDto;
    return FeedSummary(
      applicationsCount: applications.items.length,
      applicationsApprox: applications.nextCursor != null,
      savedCount: saved.items.length,
      savedApprox: saved.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
