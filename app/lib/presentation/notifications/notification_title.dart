import 'package:jobify_app/data/notifications/notification_dto.dart';

/// Human-readable title for a notification, from its kind + payload. Every
/// payload read is null-guarded (payload is an untyped wire dict).
String notificationTitle(NotificationDto n) {
  final p = n.payload;
  switch (n.kind) {
    case 'application_received':
      final job = p['job_title'] as String?;
      final emp = p['employer_name'] as String?;
      if (job != null && emp != null) {
        return 'Application received for $job at $emp';
      }
      if (job != null) return 'Application received for $job';
      return 'Application received';
    case 'application_stage_changed':
      final job = p['job_title'] as String?;
      final stage = p['stage'] as String?;
      final line = switch (stage) {
        'shortlisted' => 'Shortlisted',
        'interview' => 'Interview stage',
        'offer' => 'You have an offer',
        'hired' => 'You were hired',
        'rejected' => 'Update on your application',
        _ => 'Application updated',
      };
      return job != null ? '$line for $job' : line;
    default:
      return _humanize(n.kind);
  }
}

String _humanize(String kind) {
  if (kind.isEmpty) return 'Notification';
  final words = kind.replaceAll('_', ' ');
  return words[0].toUpperCase() + words.substring(1);
}
