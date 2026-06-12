import 'package:jobify_app/data/feed/feed_dto.dart';

abstract interface class FeedRepository {
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20});
}
