import 'package:dio/dio.dart';

import 'package:jobify_app/data/consents/consent_dto.dart';

class ConsentApi {
  ConsentApi(this._dio);
  final Dio _dio;

  Future<ConsentListResponse> list() async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/me/consents');
    return ConsentListResponse.fromJson(res.data!);
  }

  Future<ConsentDto> patch(String scope, {required bool granted}) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/me/consents/$scope',
      data: {'granted': granted},
    );
    return ConsentDto.fromJson(res.data!);
  }
}
