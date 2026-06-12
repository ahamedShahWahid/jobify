import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/presentation/auth/auth_providers.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'current_role_provider.g.dart';

/// The signed-in user's role, or null when not signed in.
@riverpod
UserRole? currentRole(Ref ref) {
  final auth = ref.watch(authStateProvider);
  return auth is SignedIn ? auth.role : null;
}
