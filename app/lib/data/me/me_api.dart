import 'package:dio/dio.dart';

import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';

class MeApi {
  MeApi(this._dio);
  final Dio _dio;

  Future<MeDto> getMe() async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/me');
    return MeDto.fromJson(res.data!);
  }

  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/applicants/me',
      data: update.toJson(),
    );
    return MeDto.fromJson(res.data!);
  }
}
