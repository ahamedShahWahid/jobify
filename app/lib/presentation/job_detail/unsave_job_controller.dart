import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_summary_controller.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_controller.dart';
import 'package:jobify_app/presentation/saved/saved_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'unsave_job_controller.g.dart';

@riverpod
class UnsaveJobController extends _$UnsaveJobController {
  @override
  FutureOr<void> build(String jobId) async {}

  Future<void> submit() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(jobsRepositoryProvider);
      await repo.unsave(jobId);
      ref
        ..invalidate(savedControllerProvider)
        ..invalidate(jobDetailControllerProvider(jobId))
        // See apply_to_job_controller.dart for why the Feed home-summary
        // needs its own explicit invalidation here.
        ..invalidate(feedSummaryControllerProvider);
    });
  }
}
