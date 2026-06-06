import 'package:kpa_app/data/jobs/applicant_of_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_api.dart';

abstract interface class RecruiterJobsRepository {
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  });

  Future<RecruiterJobDto> createJob(Map<String, dynamic> body);

  Future<RecruiterJobDto> patchJob(String id, Map<String, dynamic> body);

  Future<void> deleteJob(String id);

  Future<ApplicantsOfJobPageDto> listApplicants(
    String jobId, {
    String? cursor,
    int limit = 20,
  });

  Future<ResumeDownload> downloadResume(String applicationId);
}
