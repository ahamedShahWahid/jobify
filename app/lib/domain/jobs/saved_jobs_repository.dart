import 'saved_jobs_page.dart';

abstract interface class SavedJobsRepository {
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20});
}
