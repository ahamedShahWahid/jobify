import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/notifications/notification_api.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _n(String id, {String? readAt}) => {
      'id': id,
      'kind': 'application_received',
      'channel': 'in_app',
      'status': 'sent',
      'payload': {'job_id': 'j1'},
      'send_after': '2026-05-01T00:00:00Z',
      'sent_at': '2026-05-01T00:00:01Z',
      'read_at': readAt,
      'created_at': '2026-05-01T00:00:00Z',
    };

void main() {
  test('fetchPage parses items + next_cursor', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('GET', '/v1/notifications', 200, {
      'items': [
        {'notification': _n('n1')},
      ],
      'next_cursor': 'CUR',
    });
    final repo = NotificationsRepositoryImpl(NotificationApi(dio));
    final page = await repo.fetchPage();
    expect(page.items.single.notification.id, 'n1');
    expect(page.nextCursor, 'CUR');
  });

  test('markRead POSTs to /{id}/read and parses NotificationDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on(
      'POST',
      '/v1/notifications/n1/read',
      200,
      _n('n1', readAt: '2026-05-02T00:00:00Z'),
    );
    final repo = NotificationsRepositoryImpl(NotificationApi(dio));
    final dto = await repo.markRead('n1');
    expect(dto.id, 'n1');
    expect(dto.readAt, isNotNull);
  });
}
