import 'feed_page.dart';

abstract interface class FeedRepository {
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20});
}
