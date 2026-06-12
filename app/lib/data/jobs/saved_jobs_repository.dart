import 'package:jobify_app/data/jobs/jobs_dto.dart';

abstract interface class SavedJobsRepository {
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20});
}
