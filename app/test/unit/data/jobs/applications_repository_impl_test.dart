import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/jobs/applications_api.dart';
import 'package:kpa_app/data/jobs/applications_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _appsPage() => {
      'items': [
        {
          'application': {
            'id': 'a1',
            'applicant_id': 'ap1',
            'job_id': 'j1',
            'status': 'applied',
            'source': 'feed',
            'created_at': '2026-05-21T12:00:00Z',
            'withdrawn_at': null,
          },
          'job': {
            'id': 'j1',
            'title': 'Eng',
            'location': 'BLR',
            'status': 'open',
            'posted_at': '2026-05-18T00:00:00Z',
          },
          'employer': {'id': 'e1', 'name': 'Acme'},
        }
      ],
      'next_cursor': null,
    };

void main() {
  late Dio dio;
  late MockInterceptor mock;
  late ApplicationsRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    mock = MockInterceptor();
    dio.interceptors.add(mock);
    repo = ApplicationsRepositoryImpl(ApplicationsApi(dio));
  });

  test('fetchPage: 200 → ApplicationsPageDto', () async {
    mock.on('GET', '/v1/applications', 200, _appsPage());
    final page = await repo.fetchPage();
    expect(page.items.single.application.id, 'a1');
  });

  test('withdraw: 200 → ApplicationDto with withdrawn status', () async {
    mock.on('PATCH', '/v1/applications/a1', 200, {
      'id': 'a1',
      'applicant_id': 'ap1',
      'job_id': 'j1',
      'status': 'withdrawn',
      'source': 'feed',
      'created_at': '2026-05-21T12:00:00Z',
      'withdrawn_at': '2026-05-22T09:00:00Z',
    });
    final a = await repo.withdraw('a1');
    expect(a.status, 'withdrawn');
    expect(a.withdrawnAt, isNotNull);
  });

  test('withdraw: 400 invalid_transition → ApiException', () async {
    mock.on('PATCH', '/v1/applications/a1', 400, {
      'status': 400,
      'slug': 'invalid_transition',
    });
    await expectLater(repo.withdraw('a1'), throwsA(isA<ApiException>()));
  });
}
