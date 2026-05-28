import 'package:json_annotation/json_annotation.dart';

part 'notification_dto.g.dart';

/// Mirrors api `NotificationRead` (routes/notifications.py).
@JsonSerializable(createToJson: false)
class NotificationDto {
  const NotificationDto({
    required this.id,
    required this.kind,
    required this.channel,
    required this.status,
    required this.payload,
    required this.sendAfter,
    required this.createdAt,
    this.sentAt,
    this.readAt,
  });

  factory NotificationDto.fromJson(Map<String, dynamic> json) =>
      _$NotificationDtoFromJson(json);

  final String id;
  final String kind;
  final String channel;
  final String status;
  final Map<String, dynamic> payload;
  @JsonKey(name: 'send_after')
  final DateTime sendAfter;
  @JsonKey(name: 'sent_at')
  final DateTime? sentAt;
  @JsonKey(name: 'read_at')
  final DateTime? readAt;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
}

@JsonSerializable(createToJson: false)
class NotificationListItemDto {
  const NotificationListItemDto({required this.notification});

  factory NotificationListItemDto.fromJson(Map<String, dynamic> json) =>
      _$NotificationListItemDtoFromJson(json);

  final NotificationDto notification;
}

@JsonSerializable(createToJson: false)
class NotificationsPageDto {
  const NotificationsPageDto({required this.items, this.nextCursor});

  factory NotificationsPageDto.fromJson(Map<String, dynamic> json) =>
      _$NotificationsPageDtoFromJson(json);

  final List<NotificationListItemDto> items;
  @JsonKey(name: 'next_cursor')
  final String? nextCursor;
}
