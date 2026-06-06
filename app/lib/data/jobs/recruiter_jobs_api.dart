import 'dart:typed_data';

import 'package:dio/dio.dart';

import 'package:kpa_app/data/jobs/applicant_of_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';

/// Parsed result of GET /v1/applications/{id}/resume (binary download).
class ResumeDownload {
  const ResumeDownload({
    required this.bytes,
    required this.filename,
    required this.contentType,
  });

  final Uint8List bytes;
  final String filename;
  final String contentType;
}

final _filenameRe = RegExp('filename="?([^";]+)"?', caseSensitive: false);

class RecruiterJobsApi {
  RecruiterJobsApi(this._dio);
  final Dio _dio;

  /// GET /v1/jobs/me — paginated list of the caller's jobs with counts.
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  }) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/jobs/me',
      queryParameters: {
        'limit': limit,
        if (status != null) 'status': status,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return RecruiterJobsPageDto.fromJson(res.data!);
  }

  /// POST /v1/jobs — create a new job posting.
  Future<RecruiterJobDto> createJob(Map<String, dynamic> body) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/jobs',
      data: body,
    );
    return RecruiterJobDto.fromJson(res.data!);
  }

  /// PATCH /v1/jobs/{id} — update a job posting.
  Future<RecruiterJobDto> patchJob(String id, Map<String, dynamic> body) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/jobs/$id',
      data: body,
    );
    return RecruiterJobDto.fromJson(res.data!);
  }

  /// DELETE /v1/jobs/{id} — soft-delete a job posting (204, no body).
  Future<void> deleteJob(String id) async {
    await _dio.delete<void>('/v1/jobs/$id');
  }

  /// GET /v1/jobs/{jobId}/applicants — paginated applicants for a job.
  Future<ApplicantsOfJobPageDto> listApplicants(
    String jobId, {
    String? cursor,
    int limit = 20,
  }) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/jobs/$jobId/applicants',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return ApplicantsOfJobPageDto.fromJson(res.data!);
  }

  /// GET /v1/applications/{applicationId}/resume — binary resume download.
  ///
  /// Parses the filename from the `content-disposition` response header
  /// (falls back to `'resume'`) and the content type from `content-type`
  /// (falls back to `'application/octet-stream'`).
  Future<ResumeDownload> downloadResume(String applicationId) async {
    final res = await _dio.get<List<int>>(
      '/v1/applications/$applicationId/resume',
      options: Options(responseType: ResponseType.bytes),
    );

    final headers = res.headers;
    final disposition = headers.value('content-disposition') ?? '';
    final match = _filenameRe.firstMatch(disposition);
    final filename = match?.group(1)?.trim() ?? 'resume';

    final contentType =
        headers.value('content-type') ?? 'application/octet-stream';

    final rawBytes = res.data ?? <int>[];
    return ResumeDownload(
      bytes: Uint8List.fromList(rawBytes),
      filename: filename,
      contentType: contentType,
    );
  }
}
