import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/api/request_id_interceptor.dart';

class _TestHandler extends RequestInterceptorHandler {
  late RequestOptions capturedOptions;

  @override
  void next(RequestOptions options) {
    capturedOptions = options;
  }
}

void main() {
  test('sets X-Request-Id header on request options', () {
    final interceptor = RequestIdInterceptor();
    final options = RequestOptions(path: '/foo');
    final handler = _TestHandler();

    interceptor.onRequest(options, handler);
    expect(handler.capturedOptions.headers['X-Request-Id'], isNotNull);
    expect(
      handler.capturedOptions.headers['X-Request-Id'],
      hasLength(36), // uuid4
    );
  });

  test('stashes request-id in options.extra', () {
    final interceptor = RequestIdInterceptor();
    final options = RequestOptions(path: '/foo');
    final handler = _TestHandler();

    interceptor.onRequest(options, handler);
    final id = requestIdFromOptions(handler.capturedOptions);
    expect(id, isNotNull);
    expect(id, hasLength(36)); // uuid4
  });

  test('generates different ids per request', () {
    final interceptor = RequestIdInterceptor();
    final ids = <String>[];

    for (var i = 0; i < 2; i++) {
      final options = RequestOptions(path: '/foo');
      final handler = _TestHandler();
      interceptor.onRequest(options, handler);
      ids.add(requestIdFromOptions(handler.capturedOptions) ?? '');
    }

    expect(ids.length, 2);
    expect(ids[0], isNot(ids[1]));
  });
}
