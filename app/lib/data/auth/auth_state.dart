import 'package:kpa_app/data/auth/user_role.dart';

/// The three states the app's auth lifecycle can be in.
/// Watched by the router for redirect decisions and by every screen
/// that needs the current user.
sealed class AuthState {
  const AuthState();
}

class SignedOut extends AuthState {
  const SignedOut();
}

class Authenticating extends AuthState {
  const Authenticating();
}

class SignedIn extends AuthState {
  const SignedIn({
    required this.userId,
    required this.email,
    required this.role,
    this.displayName,
  });

  final String userId;
  final String email;
  final UserRole role;
  final String? displayName;
}
