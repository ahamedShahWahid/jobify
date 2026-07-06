import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_visit_repository_impl.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('getLastSeenAt returns null when never set', () async {
    final repo = FeedVisitRepositoryImpl();
    expect(await repo.getLastSeenAt(), isNull);
  });

  test('setLastSeenAt then getLastSeenAt round-trips', () async {
    final repo = FeedVisitRepositoryImpl();
    final now = DateTime.parse('2026-07-06T10:00:00.000Z');
    await repo.setLastSeenAt(now);
    expect(await repo.getLastSeenAt(), now);
  });

  test('a later setLastSeenAt overwrites the earlier value', () async {
    final repo = FeedVisitRepositoryImpl();
    await repo.setLastSeenAt(DateTime.parse('2026-07-01T00:00:00.000Z'));
    await repo.setLastSeenAt(DateTime.parse('2026-07-06T00:00:00.000Z'));
    expect(
      await repo.getLastSeenAt(),
      DateTime.parse('2026-07-06T00:00:00.000Z'),
    );
  });
}
