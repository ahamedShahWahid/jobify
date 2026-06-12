import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/applications/applications_controller.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'apply_to_job_controller.g.dart';

@riverpod
class ApplyToJobController extends _$ApplyToJobController {
  @override
  FutureOr<ApplicationDto?> build(String jobId) => null;

  Future<void> submit({
    ApplicationSource source = ApplicationSource.feed,
  }) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final app =
          await ref.read(jobsRepositoryProvider).applyTo(jobId, source: source);
      ref
        ..invalidate(applicationsControllerProvider)
        ..invalidate(jobDetailControllerProvider(jobId));
      return app;
    });
  }
}
