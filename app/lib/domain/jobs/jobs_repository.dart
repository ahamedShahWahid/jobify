import 'job_detail.dart';

abstract interface class JobsRepository {
  Future<JobDetailDto> fetchById(String jobId);
  Future<ApplicationDto> applyTo(String jobId, {String source = 'feed'});
  Future<SavedJobDto> save(String jobId);
  Future<void> unsave(String jobId);
}
