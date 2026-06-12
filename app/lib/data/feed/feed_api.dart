import 'package:dio/dio.dart';

import 'package:jobify_app/data/feed/feed_dto.dart';

class FeedApi {
  FeedApi(this._dio);
  final Dio _dio;

  Future<FeedPageDto> getFeed({String? cursor, int limit = 20}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/v1/feed',
      queryParameters: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      },
    );
    return FeedPageDto.fromJson(res.data!);
  }
}
