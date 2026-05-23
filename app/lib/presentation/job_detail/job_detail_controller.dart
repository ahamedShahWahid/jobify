import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'job_detail_controller.g.dart';

@riverpod
class JobDetailController extends _$JobDetailController {
  @override
  Future<JobDetailDto> build(String jobId) async {
    return ref.read(jobsRepositoryProvider).fetchById(jobId);
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
