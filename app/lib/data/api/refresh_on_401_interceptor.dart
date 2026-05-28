import 'dart:async';

import 'package:dio/dio.dart';

import 'package:kpa_app/core/error/auth_slugs.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';

const String _kReplayedFlag = 'kpa.refreshReplayed';

typedef RefreshCallback = Future<String> Function();
typedef OnSignedOut = void Function();

class RefreshOn401Interceptor extends Interceptor {
  RefreshOn401Interceptor({
    required AccessTokenHolder holder,
    required RefreshCallback refresh,
    required Dio dio,
    OnSignedOut? onSignedOut,
  })  : _holder = holder,
        _refresh = refresh,
        _dio = dio,
        _onSignedOut = onSignedOut;

  final AccessTokenHolder _holder;
  final RefreshCallback _refresh;
  final Dio _dio;
  final OnSignedOut? _onSignedOut;

  Completer<String>? _inFlight;

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final response = err.response;
    if (response == null || response.statusCode != 401) {
      return handler.next(err);
    }

    // Backend emits RFC 7807 problem+json (`{detail, type, title, status,
    // request_id}`) via middleware/error_handler.py. There is NO `slug`
    // field — the slug value lives in `detail`. The AuthSlugs constants
    // are Dart-side names for the string values.
    final body = response.data;
    final detail = body is Map ? body['detail'] : null;
    if (detail != AuthSlugs.invalidAccessToken) {
      return handler.next(err);
    }

    if (err.requestOptions.extra[kSkipAuth] == true) {
      return handler.next(err);
    }

    if (err.requestOptions.extra[_kReplayedFlag] == true) {
      // Replay still 401 — give up.
      _holder.clear();
      _onSignedOut?.call();
      return handler.next(err);
    }

    try {
      final newAccess = await _runRefreshSingleFlight();
      _holder.set(newAccess);

      final cloned = _cloneRequestForReplay(err.requestOptions, newAccess);
      final replay = await _dio.fetch<dynamic>(cloned);
      return handler.resolve(replay);
    } on _RefreshFailed {
      _holder.clear();
      _onSignedOut?.call();
      return handler.next(err);
    } on DioException catch (replayErr) {
      return handler.next(replayErr);
    } catch (replayErr, st) {
      return handler.next(
        DioException(
          requestOptions: err.requestOptions,
          error: replayErr,
          stackTrace: st,
        ),
      );
    }
  }

  Future<String> _runRefreshSingleFlight() {
    final existing = _inFlight;
    if (existing != null) return existing.future;
    final c = Completer<String>();
    _inFlight = c;
    _refresh().then(
      (token) {
        _inFlight = null;
        c.complete(token);
      },
      onError: (Object e, StackTrace s) {
        _inFlight = null;
        c.completeError(_RefreshFailed(e), s);
      },
    );
    return c.future;
  }

  RequestOptions _cloneRequestForReplay(
    RequestOptions original,
    String newAccess,
  ) {
    return original.copyWith(
      headers: {
        ...original.headers,
        'Authorization': 'Bearer $newAccess',
      },
      extra: {
        ...original.extra,
        _kReplayedFlag: true,
      },
    );
  }
}

class _RefreshFailed implements Exception {
  _RefreshFailed(this.cause);
  final Object cause;
}
