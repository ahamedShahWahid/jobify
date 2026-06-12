import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_repository_impl.dart';
import 'package:jobify_app/presentation/paging/paged_state.dart';
import 'package:jobify_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'feed_controller.g.dart';

typedef FeedState = PagedState<FeedItemDto>;

@riverpod
class FeedController extends _$FeedController {
  @override
  Future<FeedState> build() async {
    final page = await ref.read(feedRepositoryProvider).fetchPage();
    return PagedState(
      items: page.items,
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() => loadNextPage<FeedItemDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page =
              await ref.read(feedRepositoryProvider).fetchPage(cursor: cursor);
          return PagedState(
            items: page.items,
            cursor: page.nextCursor,
            hasMore: page.nextCursor != null,
          );
        },
        setState: (s) => state = s,
      );
}
