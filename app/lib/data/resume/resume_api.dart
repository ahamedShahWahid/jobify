import 'package:dio/dio.dart';

import 'package:jobify_app/data/resume/resume_dto.dart';

class ResumeApi {
  ResumeApi(this._dio);
  final Dio _dio;

  Future<List<ResumeDto>> list() async {
    final res = await _dio.get<List<dynamic>>('/v1/applicants/me/resumes');
    return (res.data ?? <dynamic>[])
        .map((e) => ResumeDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /v1/applicants/me/resumes/{id} — the one resume shape that carries
  /// parsedJson. List rows omit it (PERF-09; the extracted text can run to
  /// 64KB and no list/card view renders it).
  Future<ResumeDto> get(String id) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/applicants/me/resumes/$id',
    );
    return ResumeDto.fromJson(res.data!);
  }

  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: DioMediaType.parse(contentType),
      ),
    });
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/applicants/me/resumes',
      data: form,
    );
    return ResumeDto.fromJson(res.data!);
  }
}
