import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/me/me_api.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

void main() {
  test('fetch: 200 → MeDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('GET', '/v1/me', 200, {
      'user': {
        'id': 'u1',
        'email': 'u@e.com',
        'display_name': 'U',
        'role': 'applicant',
        'created_at': '2026-05-21T12:00:00Z',
      },
      'applicant': {'id': 'a1', 'user_id': 'u1'},
    });
    final repo = MeRepositoryImpl(MeApi(dio));
    final me = await repo.fetch();
    expect(me.user.email, 'u@e.com');
    expect(me.applicant?.id, 'a1');
  });
}
