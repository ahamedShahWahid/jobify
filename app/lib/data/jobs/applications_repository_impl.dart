// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/jobs/applications_api.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';

part 'applications_repository_impl.g.dart';

class ApplicationsRepositoryImpl implements ApplicationsRepository {
  ApplicationsRepositoryImpl(this._api);
  final ApplicationsApi _api;

  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async {
    try {
      return await _api.list(cursor: cursor, limit: limit);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<ApplicationDto> withdraw(String applicationId) async {
    try {
      return await _api.withdraw(applicationId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
ApplicationsRepository applicationsRepository(Ref ref) =>
    ApplicationsRepositoryImpl(ApplicationsApi(ref.read(dioProvider)));
