import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'feed_summary_controller.g.dart';

/// Client-summed Applications/Saved counts for the Feed home summary.
/// Independent fetch (not a reuse of ApplicationsController/SavedController)
/// — mirrors RecruiterDashboardController's own independence from
/// RecruiterJobsController, so a limit change here never affects the real
/// Applications/Saved tab screens. `limit: 100` + the `*Approx` flag is the
/// same MVP-documented approximation RecruiterDashboardController uses.
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
    final applicationsFuture =
        ref.read(applicationsRepositoryProvider).fetchPage(limit: 100);
    final savedFuture =
        ref.read(savedJobsRepositoryProvider).fetchPage(limit: 100);
    final applications = await applicationsFuture;
    final saved = await savedFuture;
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
