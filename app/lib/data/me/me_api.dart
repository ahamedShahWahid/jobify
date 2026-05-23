import 'package:dio/dio.dart';

import 'package:kpa_app/data/me/me_dto.dart';

class MeApi {
  MeApi(this._dio);
  final Dio _dio;
  Future<MeDto> getMe() async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/me');
    return MeDto.fromJson(res.data!);
  }
}
