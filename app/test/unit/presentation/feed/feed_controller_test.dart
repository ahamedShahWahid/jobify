import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';
import 'package:kpa_app/presentation/feed/feed_controller.dart';

class _FakeFeedRepo implements FeedRepository {
  _FakeFeedRepo(this.pages);
  final List<FeedPageDto> pages;
  int call = 0;
  @override
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async {
    return pages[call++];
  }
}

FeedItemDto _item(String jobId) => FeedItemDto(
      match: MatchSummaryDto(
        id: 'm-$jobId',
        totalScore: 0.8,
        scoreComponents: const {},
      ),
      job: JobSummaryDto(
        id: jobId,
        title: 'T-$jobId',
        location: 'BLR',
        status: 'open',
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme'),
    );

void main() {
  test('initial build returns first page; hasMore tracks next_cursor',
      () async {
    final c = ProviderContainer(
      overrides: [
        feedRepositoryProvider.overrideWithValue(
          _FakeFeedRepo([
            FeedPageDto(items: [_item('j1'), _item('j2')], nextCursor: 'c1'),
          ]),
        ),
      ],
    );
    final s = await c.read(feedControllerProvider.future);
    expect(s.items, hasLength(2));
    expect(s.hasMore, isTrue);
    expect(s.cursor, 'c1');
  });

  test('loadMore appends items + updates cursor + flips hasMore', () async {
    final c = ProviderContainer(
      overrides: [
        feedRepositoryProvider.overrideWithValue(
          _FakeFeedRepo([
            FeedPageDto(items: [_item('j1')], nextCursor: 'c1'),
            FeedPageDto(
              items: [_item('j2'), _item('j3')],
              nextCursor: null,
            ),
          ]),
        ),
      ],
    );
    await c.read(feedControllerProvider.future);
    await c.read(feedControllerProvider.notifier).loadMore();
    final s = c.read(feedControllerProvider).value!;
    expect(s.items, hasLength(3));
    expect(s.hasMore, isFalse);
  });

  test('loadMore is a no-op when hasMore=false', () async {
    final c = ProviderContainer(
      overrides: [
        feedRepositoryProvider.overrideWithValue(
          _FakeFeedRepo([
            FeedPageDto(items: [_item('j1')], nextCursor: null),
          ]),
        ),
      ],
    );
    await c.read(feedControllerProvider.future);
    await c.read(feedControllerProvider.notifier).loadMore();
    expect(c.read(feedControllerProvider).value!.items, hasLength(1));
  });
}
