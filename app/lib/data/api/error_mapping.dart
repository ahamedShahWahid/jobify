import 'package:dio/dio.dart';
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
  final body = response.data;
  final slug = body is Map ? body['slug'] as String? : null;
  final detail = body is Map ? body['detail'] as String? : null;
  final status = response.statusCode ?? 0;

  if (status == 401 && slug == 'invalid_access_token') {
    return AuthException(
      slug: slug!,
      detail: detail,
      requestId: requestId,
      cause: cause,
    );
  }
  if (status == 401) {
    // Other 401 slugs (missing_bearer_token, user_not_found) are also
    // auth-y.
    return AuthException(
      slug: slug ?? 'unauthorized',
      detail: detail,
      requestId: requestId,
      cause: cause,
    );
  }
  return ApiException(
    statusCode: status,
    slug: slug,
    detail: detail,
    requestId: requestId,
    cause: cause,
  );
}
