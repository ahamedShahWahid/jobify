import 'package:dio/dio.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/me/me_api.dart';
import 'package:kpa_app/domain/me/me_repository.dart';
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
}

@Riverpod(keepAlive: true)
MeRepository meRepository(Ref ref) =>
    MeRepositoryImpl(MeApi(ref.read(dioProvider)));
