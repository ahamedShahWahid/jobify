import 'package:google_sign_in/google_sign_in.dart';

import 'package:kpa_app/core/config/env.dart';
import 'package:kpa_app/core/error/exceptions.dart';

abstract interface class GoogleSignInDataSource {
  /// Runs the platform-correct Google flow and returns the resulting
  /// ID token (JWT) suitable for POST /v1/auth/oauth/google.
  /// Throws AuthException if the user cancels or the SDK fails.
  Future<String> getIdToken();

  /// Best-effort sign-out from Google's side. Errors are swallowed.
  Future<void> signOut();
}

class GoogleSignInDataSourceImpl implements GoogleSignInDataSource {
  GoogleSignInDataSourceImpl([GoogleSignIn? sdk])
      : _sdk = sdk ??
            GoogleSignIn(
              serverClientId: Env.googleWebClientId,
              scopes: const ['email', 'profile', 'openid'],
            );

  final GoogleSignIn _sdk;

  @override
  Future<String> getIdToken() async {
    try {
      final account = await _sdk.signIn();
      if (account == null) {
        throw const AuthException(
          slug: 'google_sign_in_cancelled',
          detail: 'Sign-in was cancelled.',
        );
      }
      final auth = await account.authentication;
      final idToken = auth.idToken;
      if (idToken == null) {
        throw const AuthException(
          slug: 'google_id_token_missing',
          detail: 'Google returned no ID token.',
        );
      }
      return idToken;
    } on AuthException {
      rethrow;
    } catch (e) {
      throw AuthException(
        slug: 'google_sign_in_failed',
        detail: e.toString(),
        cause: e,
      );
    }
  }

  @override
  Future<void> signOut() async {
    try {
      await _sdk.signOut();
    } catch (_) {
      // swallow
    }
  }
}
