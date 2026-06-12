import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:jobify_app/presentation/paging/paged_state.dart';

/// Shape returned by `fetchPage` callbacks. Matches the conventional DTO shape
/// `{ items: List<T>, next_cursor: String? }` of every list endpoint.
typedef PageFetch<T> = Future<PagedState<T>> Function({String? cursor});

/// Append the next page. [setState] is invoked twice: once to mark loading,
/// once with the final result (data on success, error + previous-data on
/// failure). Returns early without calling [setState] if there is nothing more
/// to load.
Future<void> loadNextPage<T>({
  required AsyncValue<PagedState<T>> currentState,
  required PageFetch<T> fetch,
  required void Function(AsyncValue<PagedState<T>>) setState,
}) async {
  final current = currentState.value;
  if (current == null || !current.hasMore || current.isLoadingMore) return;

  setState(AsyncValue.data(current.copyWith(isLoadingMore: true)));
  try {
    final next = await fetch(cursor: current.cursor);
    setState(
      AsyncValue.data(
        PagedState(
          items: [...current.items, ...next.items],
          cursor: next.cursor,
          hasMore: next.hasMore,
        ),
      ),
    );
  } catch (e, st) {
    setState(
      // ignore: invalid_use_of_internal_member
      AsyncValue<PagedState<T>>.error(e, st).copyWithPrevious(
        AsyncValue.data(current.copyWith(isLoadingMore: false)),
      ),
    );
  }
}
