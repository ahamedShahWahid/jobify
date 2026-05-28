// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/notifications/notification_api.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository.dart';

part 'notifications_repository_impl.g.dart';

class NotificationsRepositoryImpl implements NotificationsRepository {
  NotificationsRepositoryImpl(this._api);
  final NotificationApi _api;

  @override
  Future<NotificationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async {
    try {
      return await _api.list(cursor: cursor, limit: limit);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<NotificationDto> markRead(String id) async {
    try {
      return await _api.markRead(id);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
NotificationsRepository notificationsRepository(Ref ref) =>
    NotificationsRepositoryImpl(NotificationApi(ref.read(dioProvider)));
