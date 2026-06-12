import 'package:dio/dio.dart';
import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/me/me_api.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'me_repository_impl.g.dart';

class MeRepositoryImpl implements MeRepository {
  MeRepositoryImpl(this._api);
  final MeApi _api;

  @override
  Future<MeDto> fetch() async {
    try {
      return await _api.getMe();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    try {
      return await _api.updateProfile(update);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
MeRepository meRepository(Ref ref) =>
    MeRepositoryImpl(MeApi(ref.read(dioProvider)));
