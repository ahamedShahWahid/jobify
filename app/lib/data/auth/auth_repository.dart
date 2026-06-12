import 'package:jobify_app/data/auth/auth_state.dart';

abstract interface class AuthRepository {
  AuthState get current;
  Future<SignedIn> signInWithGoogle();
  Future<SignedIn> completeWebSignIn(String idToken);
  Future<SignedIn> refreshSession();
  Future<String> refreshAccessTokenForInterceptor();
  Future<void> signOut();
}
