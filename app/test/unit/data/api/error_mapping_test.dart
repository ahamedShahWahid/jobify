import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/core/error/exceptions.dart';

DioException _dioErrWithResponse({
  required int status,
  required Map<String, dynamic> body,
  String? requestId,
}) {
  final requestOptions = RequestOptions(path: '/v1/feed');
  return DioException(
    requestOptions: requestOptions,
    response: Response<Map<String, dynamic>>(
      requestOptions: requestOptions,
      statusCode: status,
      data: body,
      headers: requestId == null
          ? Headers()
          : Headers.fromMap({'x-request-id': [requestId]}),
    ),
    type: DioExceptionType.badResponse,
  );
}

void main() {
  group('mapDioException', () {
    test('401 with invalid_access_token slug → AuthException', () {
      final e = _dioErrWithResponse(
        status: 401,
        body: {
          'type': 'about:blank',
          'title': 'Unauthorized',
          'status': 401,
          'slug': 'invalid_access_token',
          'detail': 'token invalid',
        },
        requestId: 'req-1',
      );
      final mapped = mapDioException(e);
      expect(mapped, isA<AuthException>());
      expect((mapped as AuthException).slug, equals('invalid_access_token'));
      expect(mapped.requestId, equals('req-1'));
    });

    test('403 not_an_applicant → ApiException with slug', () {
      final e = _dioErrWithResponse(
        status: 403,
        body: {
          'status': 403,
          'slug': 'not_an_applicant',
          'detail': 'recruiters cannot upload resumes',
        },
      );
      final mapped = mapDioException(e);
      expect(mapped, isA<ApiException>());
      expect((mapped as ApiException).statusCode, equals(403));
      expect(mapped.slug, equals('not_an_applicant'));
    });

    test('500 with empty body → ApiException with status only', () {
      final e = _dioErrWithResponse(status: 500, body: {});
      final mapped = mapDioException(e);
      expect(mapped, isA<ApiException>());
      expect((mapped as ApiException).slug, isNull);
    });

    test('connection error → NetworkException', () {
      final e = DioException(
        requestOptions: RequestOptions(path: '/v1/feed'),
        type: DioExceptionType.connectionError,
        message: 'connection refused',
      );
      final mapped = mapDioException(e);
      expect(mapped, isA<NetworkException>());
    });

    test('connection timeout → NetworkException', () {
      final e = DioException(
        requestOptions: RequestOptions(path: '/v1/feed'),
        type: DioExceptionType.connectionTimeout,
      );
      expect(mapDioException(e), isA<NetworkException>());
    });
  });
}
