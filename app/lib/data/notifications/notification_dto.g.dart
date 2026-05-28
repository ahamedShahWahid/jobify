// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'notification_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

NotificationDto _$NotificationDtoFromJson(Map<String, dynamic> json) =>
    NotificationDto(
      id: json['id'] as String,
      kind: json['kind'] as String,
      channel: json['channel'] as String,
      status: json['status'] as String,
      payload: json['payload'] as Map<String, dynamic>,
      sendAfter: DateTime.parse(json['send_after'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      sentAt: json['sent_at'] == null
          ? null
          : DateTime.parse(json['sent_at'] as String),
      readAt: json['read_at'] == null
          ? null
          : DateTime.parse(json['read_at'] as String),
    );

NotificationListItemDto _$NotificationListItemDtoFromJson(
        Map<String, dynamic> json) =>
    NotificationListItemDto(
      notification: NotificationDto.fromJson(
          json['notification'] as Map<String, dynamic>),
    );

NotificationsPageDto _$NotificationsPageDtoFromJson(
        Map<String, dynamic> json) =>
    NotificationsPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) =>
              NotificationListItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );
