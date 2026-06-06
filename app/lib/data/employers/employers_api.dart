import 'package:dio/dio.dart';

import 'package:kpa_app/data/employers/employer_dto.dart';

class EmployersApi {
  EmployersApi(this._dio);
  final Dio _dio;

  Future<EmployerDto> create({required String name, String? gst}) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/employers',
      data: {'name': name, if (gst != null && gst.isNotEmpty) 'gst': gst},
    );
    return EmployerDto.fromJson(res.data!);
  }

  Future<List<EmployerDto>> listMine() async {
    final res = await _dio.get<List<dynamic>>('/v1/employers/me');
    return (res.data ?? [])
        .map((e) => EmployerDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
