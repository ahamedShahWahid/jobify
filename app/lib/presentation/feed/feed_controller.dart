import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'feed_controller.g.dart';
part 'feed_controller.freezed.dart';

@freezed
abstract class FeedState with _$FeedState {
  const factory FeedState({
    required List<FeedItemDto> items,
    required String? cursor,
    required bool hasMore,
    @Default(false) bool isLoadingMore,
  }) = _FeedState;
}

@riverpod
class FeedController extends _$FeedController {
  @override
  Future<FeedState> build() async {
    final page = await ref.read(feedRepositoryProvider).fetchPage();
    return FeedState(
      items: page.items,
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final next = await ref
          .read(feedRepositoryProvider)
          .fetchPage(cursor: current.cursor);
      state = AsyncValue.data(
        FeedState(
          items: [...current.items, ...next.items],
          cursor: next.nextCursor,
          hasMore: next.nextCursor != null,
        ),
      );
    } catch (e, st) {
      // ignore: invalid_use_of_internal_member
      state = AsyncValue<FeedState>.error(e, st).copyWithPrevious(
        AsyncValue.data(current.copyWith(isLoadingMore: false)),
      );
    }
  }
}
