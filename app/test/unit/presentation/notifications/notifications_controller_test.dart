import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';
import 'package:kpa_app/presentation/notifications/notifications_controller.dart';

NotificationDto _n(String id, {DateTime? readAt}) => NotificationDto(
      id: id,
      kind: 'application_received',
      channel: 'in_app',
      status: 'sent',
      payload: const {'job_id': 'j1'},
      sendAfter: DateTime(2026),
      readAt: readAt,
      createdAt: DateTime(2026),
    );

class _Repo implements NotificationsRepository {
  @override
  Future<NotificationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      NotificationsPageDto(
        items: [NotificationListItemDto(notification: _n('n1'))],
      );

  @override
  Future<NotificationDto> markRead(String id) async =>
      _n(id, readAt: DateTime(2026, 2));
}

void main() {
  test('markRead replaces the item in place with read_at set', () async {
    final c = ProviderContainer(
      overrides: [
        notificationsRepositoryProvider.overrideWithValue(_Repo()),
      ],
    );
    addTearDown(c.dispose);
    await c.read(notificationsControllerProvider.future);
    await c.read(notificationsControllerProvider.notifier).markRead('n1');
    final items = c.read(notificationsControllerProvider).value!.items;
    expect(items.single.readAt, isNotNull);
  });
}
