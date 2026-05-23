import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/jobs/saved_jobs_api.dart';
import 'package:kpa_app/data/jobs/saved_jobs_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

void main() {
  test('fetchPage: 200 → SavedJobsPageDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('GET', '/v1/saved', 200, {
      'items': [
        {
          'saved': {
            'id': 's1',
            'applicant_id': 'ap1',
            'job_id': 'j1',
            'created_at': '2026-05-21T12:00:00Z',
          },
          'job': {
            'id': 'j1',
            'title': 'Eng',
            'location': 'BLR',
            'status': 'open',
            'posted_at': '2026-05-18T00:00:00Z',
          },
          'employer': {'id': 'e1', 'name': 'Acme'},
          'match': null,
        }
      ],
      'next_cursor': null,
    });
    final repo = SavedJobsRepositoryImpl(SavedJobsApi(dio));
    final page = await repo.fetchPage();
    expect(page.items.single.saved.id, 's1');
  });
}
