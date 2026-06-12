import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';

abstract interface class JobsRepository {
  Future<JobDetailDto> fetchById(String jobId);
  Future<ApplicationDto> applyTo(
    String jobId, {
    ApplicationSource source = ApplicationSource.feed,
  });
  Future<SavedJobDto> save(String jobId);
  Future<void> unsave(String jobId);
}
