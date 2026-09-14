// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/resume/resume_api.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/data/resume/resume_repository.dart';

part 'resume_repository_impl.g.dart';

class ResumeRepositoryImpl implements ResumeRepository {
  ResumeRepositoryImpl(this._api);
  final ResumeApi _api;

  @override
  Future<ResumeDto?> current() async {
    try {
      final list = await _api.list();
      if (list.isEmpty) return null;
      // The list row omits parsedJson (PERF-09) — every caller of `current()`
      // (e.g. the post-upload resume summary card) needs it, so fetch the
      // latest resume's own detail rather than returning the list row as-is.
      return await _api.get(list.first.id);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    try {
      return await _api.upload(
        bytes: bytes,
        filename: filename,
        contentType: contentType,
      );
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
ResumeRepository resumeRepository(Ref ref) =>
    ResumeRepositoryImpl(ResumeApi(ref.read(dioProvider)));
