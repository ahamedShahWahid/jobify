import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_summary_controller.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_controller.dart';
import 'package:jobify_app/presentation/saved/saved_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'save_job_controller.g.dart';

@riverpod
class SaveJobController extends _$SaveJobController {
  @override
  FutureOr<SavedJobDto?> build(String jobId) => null;

  Future<void> submit() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(jobsRepositoryProvider);
      final sv = await repo.save(jobId);
      ref
        ..invalidate(savedControllerProvider)
        ..invalidate(jobDetailControllerProvider(jobId))
        // See apply_to_job_controller.dart for why the Feed home-summary
        // needs its own explicit invalidation here.
        ..invalidate(feedSummaryControllerProvider);
      return sv;
    });
  }
}
