import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';
import 'package:kpa_app/presentation/paging/paged_state.dart';
import 'package:kpa_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'notifications_controller.g.dart';

typedef NotificationsState = PagedState<NotificationDto>;

@riverpod
class NotificationsController extends _$NotificationsController {
  @override
  Future<NotificationsState> build() async {
    final page = await ref.read(notificationsRepositoryProvider).fetchPage();
    return PagedState(
      items: [for (final it in page.items) it.notification],
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() => loadNextPage<NotificationDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page = await ref
              .read(notificationsRepositoryProvider)
              .fetchPage(cursor: cursor);
          return PagedState(
            items: [for (final it in page.items) it.notification],
            cursor: page.nextCursor,
            hasMore: page.nextCursor != null,
          );
        },
        setState: (s) => state = s,
      );

  /// Mark one notification read and replace it in the loaded list in place
  /// (no invalidate — that would refetch page 1 and reset scroll).
  Future<void> markRead(String id) async {
    final updated =
        await ref.read(notificationsRepositoryProvider).markRead(id);
    final current = state.value;
    if (current == null) return;
    state = AsyncValue.data(
      current.copyWith(
        items: [
          for (final n in current.items)
            if (n.id == id) updated else n,
        ],
      ),
    );
  }
}
