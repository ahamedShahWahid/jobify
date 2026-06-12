// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/consents/consent_api.dart';
import 'package:jobify_app/data/consents/consent_dto.dart';
import 'package:jobify_app/data/consents/consents_repository.dart';

part 'consents_repository_impl.g.dart';

class ConsentsRepositoryImpl implements ConsentsRepository {
  ConsentsRepositoryImpl(this._api);
  final ConsentApi _api;

  @override
  Future<ConsentListResponse> list() async {
    try {
      return await _api.list();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<ConsentDto> patch(String scope, {required bool granted}) async {
    try {
      return await _api.patch(scope, granted: granted);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
ConsentsRepository consentsRepository(Ref ref) =>
    ConsentsRepositoryImpl(ConsentApi(ref.read(dioProvider)));
