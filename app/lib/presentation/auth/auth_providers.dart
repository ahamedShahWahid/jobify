import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'auth_providers.g.dart';

/// Current auth state — SignedOut on app start; mutated by the bootstrap
/// controller (Task 24), the sign-in controller (Task 25), the sign-out
/// controller (Task 30), and the refresh interceptor's onSignedOut callback.
@Riverpod(keepAlive: true)
class AuthStateNotifier extends _$AuthStateNotifier {
  @override
  AuthState build() => const SignedOut();

  // ignore: use_setters_to_change_properties
  void set(AuthState s) {
    state = s;
  }
}
