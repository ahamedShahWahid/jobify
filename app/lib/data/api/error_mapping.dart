import 'package:dio/dio.dart';
import 'package:kpa_app/core/error/auth_slugs.dart';
import 'package:kpa_app/core/error/exceptions.dart';

/// Map a [DioException] into a typed [KpaException].
///
/// Call from dio's `onError` interceptor (or inside each repo's catch
/// block). 401 + slug `invalid_access_token` → [AuthException] so the
/// refresh-on-401 interceptor can be selective; other 4xx/5xx →
/// [ApiException]; transport errors → [NetworkException].
KpaException mapDioException(DioException e) {
  final response = e.response;
  final requestId = response?.headers.value('x-request-id');

  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.connectionError:
      return NetworkException(message: e.message, cause: e);

    case DioExceptionType.badCertificate:
    case DioExceptionType.cancel:
    case DioExceptionType.unknown:
      // Unknown / cancel — bucket into NetworkException so the UI shows a
      // recoverable error rather than a 500-style message.
      if (response == null) {
        return NetworkException(message: e.message, cause: e);
      }
      // fall through to badResponse handling
      return _mapResponse(response, requestId, e);

    case DioExceptionType.badResponse:
      if (response == null) {
        return ApiException(statusCode: 0, cause: e);
      }
      return _mapResponse(response, requestId, e);
  }
}

KpaException _mapResponse(
  Response<dynamic> response,
  String? requestId,
  DioException cause,
) {
  // Backend emits RFC 7807 problem+json (`{detail, type, title, status,
  // request_id}`) via middleware/error_handler.py. The "slug" value lives
  // in `detail`. `AuthSlugs` constants name the string values on the Dart
  // side. There is no separate `slug` wire field.
  final body = response.data;
  final detail = body is Map ? body['detail'] as String? : null;
  final status = response.statusCode ?? 0;

  if (status == 401 && detail == AuthSlugs.invalidAccessToken) {
    return AuthException(
      slug: detail!,
      detail: detail,
      requestId: requestId,
      cause: cause,
    );
  }
  if (status == 401) {
    // Other 401 details (missing_bearer_token, user_not_found) are also
    // auth-y.
    return AuthException(
      slug: detail ?? AuthSlugs.unauthorized,
      detail: detail,
      requestId: requestId,
      cause: cause,
    );
  }
  return ApiException(
    statusCode: status,
    slug: detail,
    detail: detail,
    requestId: requestId,
    cause: cause,
  );
}
