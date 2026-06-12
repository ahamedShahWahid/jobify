import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/notifications/notification_dto.dart';

void main() {
  test('parses the NotificationListResponse wire shape', () {
    final page = NotificationsPageDto.fromJson(const {
      'items': [
        {
          'notification': {
            'id': 'n1',
            'kind': 'application_received',
            'channel': 'in_app',
            'status': 'sent',
            'payload': {
              'job_id': 'j1',
              'job_title': 'Engineer',
              'employer_name': 'Acme',
            },
            'send_after': '2026-05-01T00:00:00Z',
            'sent_at': '2026-05-01T00:00:01Z',
            'read_at': null,
            'created_at': '2026-05-01T00:00:00Z',
          },
        }
      ],
      'next_cursor': null,
    });
    expect(page.items.length, 1);
    final n = page.items.first.notification;
    expect(n.id, 'n1');
    expect(n.kind, 'application_received');
    expect(n.payload['job_id'], 'j1');
    expect(n.readAt, isNull);
    expect(page.nextCursor, isNull);
  });
}
