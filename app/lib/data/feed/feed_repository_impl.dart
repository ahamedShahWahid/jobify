// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/feed/feed_api.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';

part 'feed_repository_impl.g.dart';

class FeedRepositoryImpl implements FeedRepository {
  FeedRepositoryImpl(this._api);
  final FeedApi _api;

  @override
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async {
    try {
      return await _api.getFeed(cursor: cursor, limit: limit);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
FeedRepository feedRepository(Ref ref) =>
    FeedRepositoryImpl(FeedApi(ref.read(dioProvider)));
