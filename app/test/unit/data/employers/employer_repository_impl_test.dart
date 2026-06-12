import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/employers/employer_repository_impl.dart';
import 'package:jobify_app/data/employers/employers_api.dart';

import '../../../helpers/mock_interceptor.dart';

void main() {
  test('createEmployer: 201 → parsed EmployerDto (isVerified == false)',
      () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('POST', '/v1/employers', 201, {
      'id': 'emp-1',
      'name': 'Acme Corp',
      'gst': null,
      'verified_at': null,
      'created_at': '2024-01-01T00:00:00Z',
    });

    final repo = EmployerRepositoryImpl(EmployersApi(dio));
    final employer = await repo.createEmployer(name: 'Acme Corp');

    expect(employer.id, 'emp-1');
    expect(employer.name, 'Acme Corp');
    expect(employer.isVerified, isFalse);
    // Confirm the request body contained the name key.
    final sent =
        mock.lastDataFor('POST', '/v1/employers')! as Map<String, dynamic>;
    expect(sent['name'], 'Acme Corp');
    expect(sent.containsKey('gst'), isFalse);
  });

  test('createEmployer: 409 employer_name_taken → ApiException', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('POST', '/v1/employers', 409, {'detail': 'employer_name_taken'});

    final repo = EmployerRepositoryImpl(EmployersApi(dio));

    await expectLater(
      () => repo.createEmployer(name: 'Acme Corp'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 409)
            .having((e) => e.slug, 'slug', 'employer_name_taken'),
      ),
    );
  });
}
