import 'package:kpa_app/data/notifications/notification_dto.dart';

abstract interface class NotificationsRepository {
  Future<NotificationsPageDto> fetchPage({String? cursor, int limit});
  Future<NotificationDto> markRead(String id);
}
