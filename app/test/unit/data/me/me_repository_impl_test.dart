import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/me/me_api.dart';
import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';

import '../../../helpers/mock_interceptor.dart';

void main() {
  test('fetch: 200 → MeDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('GET', '/v1/me', 200, {
      'id': 'u1',
      'email': 'u@e.com',
      'role': 'applicant',
      'applicant': {
        'id': 'a1',
        'full_name': 'U',
        'locations': <String>[],
        'notice_period_days': null,
      },
    });
    final repo = MeRepositoryImpl(MeApi(dio));
    final me = await repo.fetch();
    expect(me.email, 'u@e.com');
    expect(me.applicant?.id, 'a1');
  });

  test('updateProfile: PATCH sends full set incl nulls → MeDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('PATCH', '/v1/applicants/me', 200, {
      'id': 'u1',
      'email': 'u@e.com',
      'role': 'applicant',
      'applicant': {
        'id': 'a1',
        'full_name': 'Alice Khan',
        'locations': ['Pune'],
        'notice_period_days': null,
      },
    });
    final repo = MeRepositoryImpl(MeApi(dio));
    final me = await repo.updateProfile(
      const ProfileUpdateDto(
        fullName: 'Alice Khan',
        locations: ['Pune'],
      ),
    );
    expect(me.applicant?.fullName, 'Alice Khan');
    final sent =
        mock.lastDataFor('PATCH', '/v1/applicants/me')! as Map<String, dynamic>;
    expect(sent['full_name'], 'Alice Khan');
    expect(sent['locations'], ['Pune']);
    expect(sent.containsKey('expected_ctc'), isTrue);
  });
}
