import 'package:dio/dio.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository.dart';
import 'package:kpa_app/data/employers/employers_api.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'employer_repository_impl.g.dart';

class EmployerRepositoryImpl implements EmployerRepository {
  EmployerRepositoryImpl(this._api);
  final EmployersApi _api;

  @override
  Future<EmployerDto> createEmployer({
    required String name,
    String? gst,
  }) async {
    try {
      return await _api.create(name: name, gst: gst);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<List<EmployerDto>> listMyEmployers() async {
    try {
      return await _api.listMine();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
EmployerRepository employerRepository(Ref ref) =>
    EmployerRepositoryImpl(EmployersApi(ref.read(dioProvider)));
