import 'package:jobify_app/data/jobs/jobs_dto.dart';

abstract interface class ApplicationsRepository {
  Future<ApplicationsPageDto> fetchPage({String? cursor, int limit = 20});
  Future<ApplicationDto> withdraw(String applicationId);
}
