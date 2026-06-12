import 'package:dio/dio.dart';

import 'package:jobify_app/data/api/access_token_holder.dart';

/// Extras flag — set `options.extra[kSkipAuth] = true` on requests that
/// must not carry an Authorization header (the sign-in and refresh
/// endpoints). The auth repo sets this when issuing those calls.
const String kSkipAuth = 'jobify.skipAuth';

class AuthHeaderInterceptor extends Interceptor {
  AuthHeaderInterceptor(this._holder);

  final AccessTokenHolder _holder;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    final skip = options.extra[kSkipAuth] == true;
    if (!skip) {
      final token = _holder.current;
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }
}
