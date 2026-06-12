import 'package:dio/dio.dart';

import 'package:jobify_app/data/jobs/jobs_dto.dart';

class SavedJobsApi {
  SavedJobsApi(this._dio);
  final Dio _dio;

  Future<SavedJobsPageDto> list({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/saved',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return SavedJobsPageDto.fromJson(res.data!);
  }
}
