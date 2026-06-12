/// Base for all typed exceptions thrown from the data layer.
sealed class JobifyException implements Exception {
  const JobifyException({this.requestId, this.cause});

  /// X-Request-Id from the response (when present). Pair this with backend
  /// logs to chase a single request end-to-end.
  final String? requestId;

  /// The underlying exception that triggered this one (e.g., the original
  /// DioException for an [ApiException]). Useful for `error: e,
  /// stackTrace:` in structured logging.
  final Object? cause;
}

/// Authentication failures — bad token, expired session, missing bearer.
/// The refresh interceptor handles 401 → retry transparently; an
/// [AuthException] reaches the screen only after the refresh itself failed
/// (or the request was unauthenticated to begin with).
final class AuthException extends JobifyException {
  const AuthException({
    required this.slug,
    this.detail,
    super.requestId,
    super.cause,
  });

  final String slug; // e.g., invalid_access_token, missing_bearer_token
  final String? detail; // backend's user-facing detail (problem+json)

  @override
  String toString() => 'AuthException($slug'
      '${detail == null ? '' : ': $detail'})';
}

/// Any non-401 4xx/5xx response from the backend.
final class ApiException extends JobifyException {
  const ApiException({
    required this.statusCode,
    this.slug,
    this.detail,
    super.requestId,
    super.cause,
  });

  final int statusCode;
  final String? slug;
  final String? detail;

  @override
  String toString() => 'ApiException($statusCode'
      '${slug == null ? '' : ' $slug'}'
      '${detail == null ? '' : ': $detail'})';
}

/// Network-layer failure — DNS, connection refused, timeout.
final class NetworkException extends JobifyException {
  const NetworkException({this.message, super.cause});

  final String? message;

  @override
  String toString() => 'NetworkException(${message ?? 'unknown'})';
}
