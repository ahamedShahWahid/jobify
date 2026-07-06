import 'package:jobify_app/data/feed/feed_visit_repository.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'feed_visit_repository_impl.g.dart';

const _kFeedLastSeenAtKey = 'jobify_feed_last_seen_at';

class FeedVisitRepositoryImpl implements FeedVisitRepository {
  @override
  Future<DateTime?> getLastSeenAt() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_kFeedLastSeenAtKey);
    if (stored == null) return null;
    return DateTime.tryParse(stored);
  }

  @override
  Future<void> setLastSeenAt(DateTime at) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kFeedLastSeenAtKey, at.toIso8601String());
  }
}

@Riverpod(keepAlive: true)
FeedVisitRepository feedVisitRepository(Ref ref) => FeedVisitRepositoryImpl();
