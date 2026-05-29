import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/consents/consent_api.dart';
import 'package:kpa_app/data/consents/consents_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

void main() {
  group('ConsentsRepositoryImpl', () {
    test('list() decodes the wire shape', () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
      final mock = MockInterceptor();
      dio.interceptors.add(mock);
      mock.on('GET', '/v1/me/consents', 200, {
        'items': [
          {
            'scope': 'email_transactional',
            'granted': true,
            'updated_at': '2026-05-29T00:00:00Z',
          },
        ],
      });
      final repo = ConsentsRepositoryImpl(ConsentApi(dio));
      final res = await repo.list();
      expect(res.items.length, 1);
      expect(res.items.single.scope, 'email_transactional');
      expect(res.items.single.granted, isTrue);
      expect(res.items.single.updatedAt, DateTime.utc(2026, 5, 29));
    });

    test('patch() sends {granted: bool} in the request body', () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
      final mock = MockInterceptor();
      dio.interceptors.add(mock);
      mock.on('PATCH', '/v1/me/consents/email_marketing', 200, {
        'scope': 'email_marketing',
        'granted': true,
        'updated_at': '2026-05-29T00:00:00Z',
      });
      final repo = ConsentsRepositoryImpl(ConsentApi(dio));
      final res = await repo.patch('email_marketing', granted: true);
      expect(res.granted, isTrue);
      expect(res.scope, 'email_marketing');
      expect(
        mock.lastDataFor('PATCH', '/v1/me/consents/email_marketing'),
        {'granted': true},
      );
    });
  });
}
