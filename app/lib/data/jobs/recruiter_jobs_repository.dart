import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/recruiter_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_api.dart';

abstract interface class RecruiterJobsRepository {
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  });

  /// Full detail for one job, including description (list rows omit it —
  /// see RecruiterJobDto). Always use this to open the edit form, regardless
  /// of how it was reached.
  Future<RecruiterJobDto> getJob(String jobId);

  Future<RecruiterJobDto> createJob(Map<String, dynamic> body);

  Future<RecruiterJobDto> patchJob(String id, Map<String, dynamic> body);

  Future<void> deleteJob(String id);

  Future<ApplicantsOfJobPageDto> listApplicants(
    String jobId, {
    String? cursor,
    int limit = 20,
  });

  Future<ResumeDownload> downloadResume(String applicationId);

  Future<void> setStage(
    String jobId,
    String applicationId,
    ApplicationStage stage,
  );
}
