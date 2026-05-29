/// Slug strings the backend returns in `application/problem+json` bodies.
/// Centralised so call sites compare against constants, not bare literals.
abstract final class AuthSlugs {
  static const invalidAccessToken = 'invalid_access_token';
  static const missingBearerToken = 'missing_bearer_token';
  static const userNotFound = 'user_not_found';
  static const userSuspended = 'user_suspended';
  static const invalidRefreshToken = 'invalid_refresh_token';
  static const noRefreshToken = 'no_refresh_token';
  static const unauthorized = 'unauthorized';
}

/// Slugs emitted by the client-side Google sign-in flow.
abstract final class GoogleSignInSlugs {
  static const cancelled = 'google_sign_in_cancelled';
  static const idTokenMissing = 'google_id_token_missing';
  static const failed = 'google_sign_in_failed';
}
