import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_controller.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'match_feedback_controller.g.dart';

/// Rates / clears the match rating from job detail.
///
/// DELIBERATE exception to the "never invalidate the feed on mutation" rule
/// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
/// kept-alive feed list must refetch or it keeps showing the hidden job.
@riverpod
class MatchFeedbackController extends _$MatchFeedbackController {
  @override
  FutureOr<void> build(String jobId) {}

  Future<void> rate(MatchFeedbackRating rating) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(jobsRepositoryProvider).rateMatch(jobId, rating);
      ref
        ..invalidate(jobDetailControllerProvider(jobId))
        ..invalidate(feedControllerProvider);
    });
  }

  Future<void> clear() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(jobsRepositoryProvider).clearMatchFeedback(jobId);
      ref
        ..invalidate(jobDetailControllerProvider(jobId))
        ..invalidate(feedControllerProvider);
    });
  }
}
