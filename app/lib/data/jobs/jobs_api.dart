// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';

import 'package:jobify_app/data/feed/match_feedback_dto.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';

class JobsApi {
  JobsApi(this._dio);
  final Dio _dio;

  Future<JobDetailDto> getJob(String id) async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/jobs/$id');
    return JobDetailDto.fromJson(res.data!);
  }

  Future<ApplicationDto> apply(String jobId, {String source = 'feed'}) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/jobs/$jobId/apply',
      data: {'source': source},
    );
    return ApplicationDto.fromJson(res.data!);
  }

  Future<SavedJobDto> save(String jobId) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/jobs/$jobId/save',
    );
    return SavedJobDto.fromJson(res.data!);
  }

  Future<void> unsave(String jobId) async {
    await _dio.delete<dynamic>('/v1/jobs/$jobId/save');
  }

  Future<MatchFeedbackDto> rateMatch(String jobId, String rating) async {
    final res = await _dio.put<Map<String, dynamic>>(
      '/v1/jobs/$jobId/match-feedback',
      data: {'rating': rating},
    );
    return MatchFeedbackDto.fromJson(res.data!);
  }

  Future<void> clearMatchFeedback(String jobId) async {
    await _dio.delete<dynamic>('/v1/jobs/$jobId/match-feedback');
  }
}
