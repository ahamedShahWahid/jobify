import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';
import 'package:kpa_app/data/api/refresh_on_401_interceptor.dart';

// ---------------------------------------------------------------------------
// Minimal queue-based mock HTTP adapter.
//
// Each registered [_MockResponse] is consumed in FIFO order. If a request
// arrives when the queue is empty it throws an [AssertionError].
// The [validateStatus] on BaseOptions must be set so that 4xx/5xx are NOT
// thrown before our interceptor sees them — we do this in _buildHarness.
// ---------------------------------------------------------------------------

class _MockResponse {
  _MockResponse(this.status, this.body, {this.captureHeaders});
  final int status;
  final Map<String, dynamic> body;

  /// If non-null this will be filled with the request headers by the adapter.
  final Map<String, String>? captureHeaders;
}

class _MockQueueAdapter implements HttpClientAdapter {
  final _queue = <_MockResponse>[];
  final List<Map<String, String>> capturedRequests = [];

  void enqueue(_MockResponse r) => _queue.add(r);

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<dynamic>? cancelFuture,
  ) async {
    if (_queue.isEmpty) {
      throw AssertionError(
        '_MockQueueAdapter: unexpected request to '
        '${options.method} ${options.path}',
      );
    }
    final mock = _queue.removeAt(0);

    // Capture flattened headers for verification.
    final flat = <String, String>{};
    options.headers.forEach((k, v) => flat[k] = '$v');
    capturedRequests.add(flat);
    if (mock.captureHeaders != null) {
      mock.captureHeaders!.addAll(flat);
    }

    final encoded = jsonEncode(mock.body);
    return ResponseBody.fromString(
      encoded,
      mock.status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

class _RefreshCounter {
  int calls = 0;
}

({
  Dio dio,
  _MockQueueAdapter adapter,
  AccessTokenHolder holder,
  _RefreshCounter counter,
}) _buildHarness({
  required Future<String> Function(int callNumber) onRefresh,
  void Function()? onSignedOut,
}) {
  final holder = AccessTokenHolder();
  final dio = Dio(
    BaseOptions(
      baseUrl: 'http://test.local',
      // Keep the default: 2xx is success, others throw DioException.
      // Our error interceptor catches the 401 DioException and handles it.
    ),
  );

  final adapter = _MockQueueAdapter();
  dio.httpClientAdapter = adapter;

  dio.interceptors.add(AuthHeaderInterceptor(holder));
  final counter = _RefreshCounter();
  dio.interceptors.add(
    RefreshOn401Interceptor(
      holder: holder,
      dio: dio,
      onSignedOut: onSignedOut,
      refresh: () async {
        final n = ++counter.calls;
        return onRefresh(n);
      },
    ),
  );

  return (dio: dio, adapter: adapter, holder: holder, counter: counter);
}

/// Real backend wire shape — RFC 7807 problem+json from
/// middleware/error_handler.py. The slug is encoded in `detail`; there is
/// NO separate `slug` field. Tests must mirror this so contract drift
/// (slug-key vs detail-key) cannot pass.
Map<String, dynamic> _invalidAccess() => {
      'type': 'about:blank',
      'title': 'Unauthorized',
      'status': 401,
      'detail': 'invalid_access_token',
      'request_id': 'test-req-id',
    };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('RefreshOn401Interceptor', () {
    test('401 → refresh → replay → 200', () async {
      final h = _buildHarness(onRefresh: (_) async => 'NEW_TOKEN');
      h.holder.set('OLD_TOKEN');

      // First call → 401.
      h.adapter.enqueue(_MockResponse(401, _invalidAccess()));
      // Replay after refresh → 200. Capture headers for verification.
      final replayHeaders = <String, String>{};
      h.adapter.enqueue(
        _MockResponse(
          200,
          {'items': <dynamic>[]},
          captureHeaders: replayHeaders,
        ),
      );

      final res = await h.dio.get<dynamic>('/v1/feed');
      expect(res.statusCode, 200);
      expect(h.holder.current, 'NEW_TOKEN');
      expect(h.counter.calls, 1);
      // Verify replay used the new token.
      expect(replayHeaders['Authorization'], 'Bearer NEW_TOKEN');
      // Two requests total: original + replay.
      expect(h.adapter.capturedRequests.length, 2);
    });

    test('401 → refresh fails → holder cleared + onSignedOut + throws',
        () async {
      var signedOut = false;
      final h = _buildHarness(
        onRefresh: (_) async => throw StateError('refresh-failed'),
        onSignedOut: () => signedOut = true,
      );
      h.holder.set('OLD_TOKEN');

      h.adapter.enqueue(_MockResponse(401, _invalidAccess()));

      await expectLater(
        h.dio.get<dynamic>('/v1/feed'),
        throwsA(isA<DioException>()),
      );
      expect(h.holder.current, isNull);
      expect(signedOut, isTrue);
    });

    test('two concurrent 401s → exactly one refresh call', () async {
      final completer = Completer<String>();
      final h = _buildHarness(onRefresh: (_) => completer.future);
      h.holder.set('OLD_TOKEN');

      // Two initial requests → both 401.
      h.adapter.enqueue(_MockResponse(401, _invalidAccess()));
      h.adapter.enqueue(_MockResponse(401, _invalidAccess()));
      // Two replays → both 200.
      h.adapter.enqueue(_MockResponse(200, {'items': <dynamic>[]}));
      h.adapter.enqueue(_MockResponse(200, {'items': <dynamic>[]}));

      final f1 = h.dio.get<dynamic>('/v1/feed');
      final f2 = h.dio.get<dynamic>('/v1/feed');

      // Let both reach the in-flight refresh.
      await Future<void>.delayed(const Duration(milliseconds: 50));
      completer.complete('NEW_TOKEN');

      final results = await Future.wait([f1, f2]);
      for (final r in results) {
        expect(r.statusCode, 200);
      }
      expect(h.counter.calls, 1, reason: 'refresh single-flight failed');
    });

    test('401 on kSkipAuth request → no refresh', () async {
      final h = _buildHarness(
        onRefresh: (_) async => fail('should not run'),
      );

      h.adapter.enqueue(_MockResponse(401, _invalidAccess()));

      await expectLater(
        h.dio.post<dynamic>(
          '/v1/auth/refresh',
          options: Options(extra: {kSkipAuth: true}),
        ),
        throwsA(isA<DioException>()),
      );
      expect(h.counter.calls, 0);
    });

    test('401 with non-invalid_access_token detail → no refresh, sign out',
        () async {
      // missing_bearer_token / user_not_found / unknown future slugs all
      // mean the session is structurally broken — refresh won't help, so
      // clear the holder and trigger sign-out so the router redirects to
      // /signin. (Pre-2026-05-29 behavior just fell through, which left
      // the caller rendering a misleading "Signed out" inline view while
      // the auth state stayed SignedIn.)
      var signedOut = false;
      final h = _buildHarness(
        onRefresh: (_) async => fail('should not run'),
        onSignedOut: () => signedOut = true,
      );
      h.holder.set('TOK');

      h.adapter.enqueue(
        _MockResponse(401, {
          'status': 401,
          'detail': 'missing_bearer_token',
        }),
      );

      await expectLater(
        h.dio.get<dynamic>('/v1/x'),
        throwsA(isA<DioException>()),
      );
      expect(h.counter.calls, 0);
      expect(h.holder.current, isNull, reason: 'holder cleared on sign-out');
      expect(signedOut, isTrue);
    });

    test('401 user_not_found → no refresh, sign out', () async {
      var signedOut = false;
      final h = _buildHarness(
        onRefresh: (_) async => fail('should not run'),
        onSignedOut: () => signedOut = true,
      );
      h.holder.set('TOK');

      h.adapter.enqueue(
        _MockResponse(401, {
          'status': 401,
          'detail': 'user_not_found',
        }),
      );

      await expectLater(
        h.dio.get<dynamic>('/v1/feed'),
        throwsA(isA<DioException>()),
      );
      expect(h.counter.calls, 0);
      expect(h.holder.current, isNull);
      expect(signedOut, isTrue);
    });

    test('401 on kSkipAuth refresh endpoint → no sign-out either', () async {
      // The refresh-endpoint call itself sets kSkipAuth. A 401 from refresh
      // is handled by the auth repo (which then triggers the dio's higher-
      // level sign-out path via _RefreshFailed inside the OTHER 401). The
      // interceptor must NOT also push SignedOut here — that would race
      // with the in-flight refresh's own error handling.
      var signedOut = false;
      final h = _buildHarness(
        onRefresh: (_) async => fail('should not run'),
        onSignedOut: () => signedOut = true,
      );
      h.holder.set('TOK');

      h.adapter.enqueue(
        _MockResponse(401, {
          'status': 401,
          'detail': 'invalid_refresh_token',
        }),
      );

      await expectLater(
        h.dio.post<dynamic>(
          '/v1/auth/refresh',
          options: Options(extra: {kSkipAuth: true}),
        ),
        throwsA(isA<DioException>()),
      );
      expect(h.counter.calls, 0);
      expect(signedOut, isFalse, reason: 'kSkipAuth path must not sign out');
      expect(h.holder.current, 'TOK', reason: 'holder untouched on kSkipAuth');
    });

    test('replay still 401 → give up, clear holder, signed out', () async {
      var signedOut = false;
      final h = _buildHarness(
        onRefresh: (_) async => 'STILL_BAD',
        onSignedOut: () => signedOut = true,
      );
      h.holder.set('OLD');

      // Original → 401.
      h.adapter.enqueue(_MockResponse(401, _invalidAccess()));
      // Replay → 401 again.
      h.adapter.enqueue(_MockResponse(401, _invalidAccess()));

      await expectLater(
        h.dio.get<dynamic>('/v1/feed'),
        throwsA(isA<DioException>()),
      );
      expect(h.holder.current, isNull);
      expect(signedOut, isTrue);
      expect(h.counter.calls, 1);
    });
  });
}
