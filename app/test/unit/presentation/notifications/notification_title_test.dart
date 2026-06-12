import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/notifications/notification_dto.dart';
import 'package:jobify_app/presentation/notifications/notification_title.dart';

NotificationDto _n(
  String kind,
  Map<String, dynamic> payload,
) =>
    NotificationDto(
      id: 'n1',
      kind: kind,
      channel: 'in_app',
      status: 'sent',
      payload: payload,
      sendAfter: DateTime(2026),
      createdAt: DateTime(2026),
    );

void main() {
  test('application_received with job + employer', () {
    expect(
      notificationTitle(
        _n(
          'application_received',
          {'job_title': 'Engineer', 'employer_name': 'Acme'},
        ),
      ),
      'Application received for Engineer at Acme',
    );
  });
  test('application_received missing payload keys → graceful', () {
    expect(
      notificationTitle(_n('application_received', {})),
      'Application received',
    );
  });
  test('unknown kind is humanized', () {
    expect(
      notificationTitle(_n('something_happened', {})),
      'Something happened',
    );
  });
}
