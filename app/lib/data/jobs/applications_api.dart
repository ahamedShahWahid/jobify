// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';

import 'package:jobify_app/data/jobs/jobs_dto.dart';

class ApplicationsApi {
  ApplicationsApi(this._dio);
  final Dio _dio;

  Future<ApplicationsPageDto> list({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/applications',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return ApplicationsPageDto.fromJson(res.data!);
  }

  Future<ApplicationDto> withdraw(String applicationId) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/applications/$applicationId',
      data: {'status': 'withdrawn'},
    );
    return ApplicationDto.fromJson(res.data!);
  }
}
