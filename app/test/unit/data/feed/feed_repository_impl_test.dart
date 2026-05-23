import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/feed/feed_api.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _samplePage({String? next}) => {
      'items': [
        {
          'match': {
            'id': 'm1',
            'total_score': 0.81,
            'score_components': {'vec': 0.9, 'rules': 0.7},
            'explanation': {
              'fit': 'great',
              'caveat': null,
              'generator': 'templated',
              'generator_version': '1',
            },
            'surfaced_at': '2026-05-20T10:00:00Z',
          },
          'job': {
            'id': 'j1',
            'title': 'Eng',
            'location': 'Bangalore',
            'status': 'open',
            'posted_at': '2026-05-18T00:00:00Z',
          },
          'employer': {
            'id': 'e1',
            'name': 'Acme',
            'verified_at': '2026-01-01T00:00:00Z',
          },
        }
      ],
      'next_cursor': next,
    };

void main() {
  late Dio dio;
  late MockInterceptor mock;
  late FeedRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    mock = MockInterceptor();
    dio.interceptors.add(mock);
    repo = FeedRepositoryImpl(FeedApi(dio));
  });

  test('200 → FeedPageDto with parsed items', () async {
    mock.on('GET', '/v1/feed', 200, _samplePage(next: 'c1'));
    final page = await repo.fetchPage();
    expect(page.items.single.job.title, 'Eng');
    expect(page.items.single.match.totalScore, 0.81);
    expect(page.nextCursor, 'c1');
  });

  test('cursor passed through', () async {
    mock.on('GET', '/v1/feed', 200, _samplePage());
    final page = await repo.fetchPage(cursor: 'xyz');
    expect(page.nextCursor, isNull);
  });

  test('401 invalid_access_token → AuthException', () async {
    mock.on('GET', '/v1/feed', 401, {
      'status': 401,
      'slug': 'invalid_access_token',
    });
    await expectLater(repo.fetchPage(), throwsA(isA<AuthException>()));
  });

  test('500 → ApiException', () async {
    mock.on('GET', '/v1/feed', 500, {});
    await expectLater(repo.fetchPage(), throwsA(isA<ApiException>()));
  });
}
