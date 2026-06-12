// Single-method repo interfaces are this codebase's data-layer seam
// (fake implementations in test/helpers depend on them).
// ignore_for_file: one_member_abstracts
import 'package:jobify_app/data/jobs/jobs_dto.dart';

abstract interface class SavedJobsRepository {
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20});
}
