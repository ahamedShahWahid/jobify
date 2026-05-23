import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';

class _TestHandler extends RequestInterceptorHandler {
  late RequestOptions capturedOptions;

  @override
  void next(RequestOptions options) {
    capturedOptions = options;
  }
}

void main() {
  late AccessTokenHolder holder;

  setUp(() {
    holder = AccessTokenHolder();
  });

  test('attaches Bearer token when present', () {
    holder.set('tok-123');
    final interceptor = AuthHeaderInterceptor(holder);
    final options = RequestOptions(path: '/foo');
    final handler = _TestHandler();

    interceptor.onRequest(options, handler);
    expect(
      handler.capturedOptions.headers['Authorization'],
      'Bearer tok-123',
    );
  });

  test('omits Authorization when no token', () {
    final interceptor = AuthHeaderInterceptor(holder);
    final options = RequestOptions(path: '/foo');
    final handler = _TestHandler();

    interceptor.onRequest(options, handler);
    expect(handler.capturedOptions.headers['Authorization'], isNull);
  });

  test('omits Authorization when kSkipAuth=true even with token', () {
    holder.set('tok-xyz');
    final interceptor = AuthHeaderInterceptor(holder);
    final options = RequestOptions(
      path: '/foo',
      extra: {kSkipAuth: true},
    );
    final handler = _TestHandler();

    interceptor.onRequest(options, handler);
    expect(handler.capturedOptions.headers['Authorization'], isNull);
  });
}
