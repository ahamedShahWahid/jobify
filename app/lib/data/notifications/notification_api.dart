import 'package:dio/dio.dart';

import 'package:jobify_app/data/notifications/notification_dto.dart';

class NotificationApi {
  NotificationApi(this._dio);
  final Dio _dio;

  Future<NotificationsPageDto> list({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/notifications',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return NotificationsPageDto.fromJson(res.data!);
  }

  Future<NotificationDto> markRead(String id) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/notifications/$id/read',
    );
    return NotificationDto.fromJson(res.data!);
  }
}
