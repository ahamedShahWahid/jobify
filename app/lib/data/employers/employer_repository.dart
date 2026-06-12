import 'package:jobify_app/data/employers/employer_dto.dart';

abstract interface class EmployerRepository {
  Future<EmployerDto> createEmployer({required String name, String? gst});
  Future<List<EmployerDto>> listMyEmployers();
}
