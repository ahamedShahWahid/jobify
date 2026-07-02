import 'package:dio/dio.dart';
import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/preferences/preferences_api.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'preferences_repository_impl.g.dart';

class PreferencesRepositoryImpl implements PreferencesRepository {
  PreferencesRepositoryImpl(this._api);
  final PreferencesApi _api;

  @override
  Future<PreferencesDto> fetch() async {
    try {
      return await _api.get();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    try {
      return await _api.update(update);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
PreferencesRepository preferencesRepository(Ref ref) =>
    PreferencesRepositoryImpl(PreferencesApi(ref.read(dioProvider)));
