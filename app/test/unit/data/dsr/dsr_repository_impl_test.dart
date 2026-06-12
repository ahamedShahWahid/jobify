import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/dsr/dsr_api.dart';
import 'package:jobify_app/data/dsr/dsr_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

void main() {
  group('DsrRepositoryImpl', () {
    test('exportData() returns the raw response body as a String', () async {
      const payload = '{"version":"1","exported_at":"2026-05-29T00:00:00Z"}';
      // exportData uses ResponseType.plain — MockInterceptor only supports Map
      // bodies, so we use a raw InterceptorsWrapper that returns a String.
      final dio = Dio(BaseOptions(baseUrl: 'http://test.local'))
        ..interceptors.add(
          InterceptorsWrapper(
            onRequest: (options, handler) {
              handler.resolve(
                Response(
                  requestOptions: options,
                  statusCode: 200,
                  data: payload,
                ),
              );
            },
          ),
        );
      final repo = DsrRepositoryImpl(DsrApi(dio));
      final result = await repo.exportData();
      expect(result, payload);
    });

    test('deleteAccount() sends {confirmation: "DELETE_MY_ACCOUNT"}', () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
      final mock = MockInterceptor();
      dio.interceptors.add(mock);
      mock.on('DELETE', '/v1/me/dsr', 200, {
        'deleted_at': '2026-05-29T00:00:00Z',
        'section_counts': {'notifications': 0, 'user_tombstoned': 1},
        'warnings': <dynamic>[],
      });
      final repo = DsrRepositoryImpl(DsrApi(dio));
      await repo.deleteAccount();
      expect(
        mock.lastDataFor('DELETE', '/v1/me/dsr'),
        {'confirmation': 'DELETE_MY_ACCOUNT'},
      );
    });

    test('deleteAccount() parses sectionCounts + warnings from the response',
        () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
      final mock = MockInterceptor();
      dio.interceptors.add(mock);
      mock.on('DELETE', '/v1/me/dsr', 200, {
        'deleted_at': '2026-05-29T12:00:00Z',
        'section_counts': {'notifications': 5, 'user_tombstoned': 1},
        'warnings': [
          {
            'type': 'ownerless_employer',
            'employer_id': 'e1',
            'employer_name': 'Acme',
            'message': 'Employer has no other owners.',
          },
        ],
      });
      final repo = DsrRepositoryImpl(DsrApi(dio));
      final res = await repo.deleteAccount();
      expect(res.sectionCounts['notifications'], 5);
      expect(res.sectionCounts['user_tombstoned'], 1);
      expect(res.warnings.length, 1);
      expect(res.warnings.single.employerId, 'e1');
      expect(res.warnings.single.employerName, 'Acme');
      expect(res.deletedAt, DateTime.utc(2026, 5, 29, 12));
    });
  });
}
