// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/dsr/dsr_api.dart';
import 'package:jobify_app/data/dsr/dsr_dto.dart';
import 'package:jobify_app/data/dsr/dsr_repository.dart';

part 'dsr_repository_impl.g.dart';

class DsrRepositoryImpl implements DsrRepository {
  DsrRepositoryImpl(this._api);
  final DsrApi _api;

  @override
  Future<String> exportData() async {
    try {
      return await _api.exportData();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<DsrDeleteResponse> deleteAccount() async {
    try {
      return await _api.deleteAccount();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
DsrRepository dsrRepository(Ref ref) =>
    DsrRepositoryImpl(DsrApi(ref.read(dioProvider)));
