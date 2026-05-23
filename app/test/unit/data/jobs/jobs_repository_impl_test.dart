import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/jobs/jobs_api.dart';
import 'package:kpa_app/data/jobs/jobs_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _jobDetail() => {
      'job': {
        'id': 'j1',
        'title': 'Eng',
        'location': 'Bangalore',
        'status': 'open',
        'posted_at': '2026-05-18T00:00:00Z',
      },
      'employer': {'id': 'e1', 'name': 'Acme'},
      'match': null,
      'application': null,
      'saved_job': null,
    };

void main() {
  late Dio dio;
  late MockInterceptor mock;
  late JobsRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    mock = MockInterceptor();
    dio.interceptors.add(mock);
    repo = JobsRepositoryImpl(JobsApi(dio));
  });

  test('fetchById: 200 → JobDetailDto', () async {
    mock.on('GET', '/v1/jobs/j1', 200, _jobDetail());
    final d = await repo.fetchById('j1');
    expect(d.job.title, 'Eng');
  });

  test('fetchById: 404 → ApiException', () async {
    mock.on('GET', '/v1/jobs/missing', 404, {
      'status': 404,
      'slug': 'not_found',
    });
    await expectLater(
      repo.fetchById('missing'),
      throwsA(isA<ApiException>()),
    );
  });

  test('applyTo: 201 → ApplicationDto', () async {
    mock.on('POST', '/v1/jobs/j1/apply', 201, {
      'id': 'a1',
      'applicant_id': 'ap1',
      'job_id': 'j1',
      'status': 'applied',
      'source': 'feed',
      'created_at': '2026-05-21T12:00:00Z',
      'withdrawn_at': null,
    });
    final a = await repo.applyTo('j1');
    expect(a.id, 'a1');
    expect(a.status, 'applied');
  });

  test('save: 201 → SavedJobDto', () async {
    mock.on('POST', '/v1/jobs/j1/save', 201, {
      'id': 's1',
      'applicant_id': 'ap1',
      'job_id': 'j1',
      'created_at': '2026-05-21T12:00:00Z',
    });
    final s = await repo.save('j1');
    expect(s.id, 's1');
  });

  test('unsave: 204 → returns', () async {
    mock.on('DELETE', '/v1/jobs/j1/save', 204, null);
    await repo.unsave('j1');
  });
}
