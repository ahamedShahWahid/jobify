import 'package:dio/dio.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/jobs/applicant_of_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_api.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_repository.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'recruiter_jobs_repository_impl.g.dart';

class RecruiterJobsRepositoryImpl implements RecruiterJobsRepository {
  RecruiterJobsRepositoryImpl(this._api);
  final RecruiterJobsApi _api;

  @override
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  }) async {
    try {
      return await _api.listMyJobs(
        status: status,
        cursor: cursor,
        limit: limit,
      );
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<RecruiterJobDto> createJob(Map<String, dynamic> body) async {
    try {
      return await _api.createJob(body);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<RecruiterJobDto> patchJob(String id, Map<String, dynamic> body) async {
    try {
      return await _api.patchJob(id, body);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<void> deleteJob(String id) async {
    try {
      await _api.deleteJob(id);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<ApplicantsOfJobPageDto> listApplicants(
    String jobId, {
    String? cursor,
    int limit = 20,
  }) async {
    try {
      return await _api.listApplicants(jobId, cursor: cursor, limit: limit);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<ResumeDownload> downloadResume(String applicationId) async {
    try {
      return await _api.downloadResume(applicationId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
RecruiterJobsRepository recruiterJobsRepository(Ref ref) =>
    RecruiterJobsRepositoryImpl(RecruiterJobsApi(ref.read(dioProvider)));
