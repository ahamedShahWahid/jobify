import 'auth_state.dart';

abstract interface class AuthRepository {
  AuthState get current;
  Future<SignedIn> signInWithGoogle();
  Future<SignedIn> refreshSession();
  Future<void> signOut();
}
