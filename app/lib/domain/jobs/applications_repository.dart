import 'applications_page.dart';

abstract interface class ApplicationsRepository {
  Future<ApplicationsPageDto> fetchPage({String? cursor, int limit = 20});
  Future<ApplicationDto> withdraw(String applicationId);
}
