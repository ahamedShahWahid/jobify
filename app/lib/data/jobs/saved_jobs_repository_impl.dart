// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/saved_jobs_api.dart';
import 'package:kpa_app/domain/jobs/saved_jobs_repository.dart';

part 'saved_jobs_repository_impl.g.dart';

class SavedJobsRepositoryImpl implements SavedJobsRepository {
  SavedJobsRepositoryImpl(this._api);
  final SavedJobsApi _api;

  @override
  Future<SavedJobsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async {
    try {
      return await _api.list(cursor: cursor, limit: limit);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
SavedJobsRepository savedJobsRepository(Ref ref) =>
    SavedJobsRepositoryImpl(SavedJobsApi(ref.read(dioProvider)));
