import 'package:kpa_app/data/jobs/applications_repository_impl.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/presentation/applications/applications_controller.dart';
import 'package:kpa_app/presentation/job_detail/job_detail_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'withdraw_application_controller.g.dart';

@riverpod
class WithdrawApplicationController
    extends _$WithdrawApplicationController {
  @override
  FutureOr<ApplicationDto?> build(String applicationId) => null;

  Future<void> submit({required String jobId}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final app = await ref
          .read(applicationsRepositoryProvider)
          .withdraw(applicationId);
      ref
        ..invalidate(applicationsControllerProvider)
        ..invalidate(jobDetailControllerProvider(jobId));
      return app;
    });
  }
}
