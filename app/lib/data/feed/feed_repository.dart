// Single-method repo interfaces are this codebase's data-layer seam
// (fake implementations in test/helpers depend on them).
// ignore_for_file: one_member_abstracts
import 'package:jobify_app/data/feed/feed_dto.dart';

abstract interface class FeedRepository {
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20});
}
