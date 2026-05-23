// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/jobs/jobs_api.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/domain/jobs/jobs_repository.dart';

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
    String source = 'feed',
  }) async {
    try {
      return await _api.apply(jobId, source: source);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

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
