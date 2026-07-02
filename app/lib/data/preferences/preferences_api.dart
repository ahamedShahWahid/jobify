import 'package:dio/dio.dart';

import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';

class PreferencesApi {
  PreferencesApi(this._dio);
  final Dio _dio;

  Future<PreferencesDto> get() async {
    final res =
        await _dio.get<Map<String, dynamic>>('/v1/applicants/me/preferences');
    return PreferencesDto.fromJson(res.data!);
  }

  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/applicants/me/preferences',
      data: update.toJson(),
    );
    return PreferencesDto.fromJson(res.data!);
  }
}
