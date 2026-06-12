// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/jobs_api.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository.dart';

part 'jobs_repository_impl.g.dart';

class JobsRepositoryImpl implements JobsRepository {
  JobsRepositoryImpl(this._api);
  final JobsApi _api;

  @override
  Future<JobDetailDto> fetchById(String jobId) async {
    try {
      return await _api.getJob(jobId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<ApplicationDto> applyTo(
    String jobId, {
    ApplicationSource source = ApplicationSource.feed,
  }) async {
    try {
      return await _api.apply(jobId, source: _sourceToWire(source));
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  static String _sourceToWire(ApplicationSource s) => switch (s) {
        ApplicationSource.feed => 'feed',
        ApplicationSource.detail => 'detail',
        ApplicationSource.unknown => 'unknown',
      };

  @override
  Future<SavedJobDto> save(String jobId) async {
    try {
      return await _api.save(jobId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<void> unsave(String jobId) async {
    try {
      await _api.unsave(jobId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
JobsRepository jobsRepository(Ref ref) =>
    JobsRepositoryImpl(JobsApi(ref.read(dioProvider)));
