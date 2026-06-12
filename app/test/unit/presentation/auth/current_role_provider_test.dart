import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/presentation/auth/auth_providers.dart';
import 'package:jobify_app/presentation/auth/current_role_provider.dart';

void main() {
  test('null when signed out, role when signed in', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(container.read(currentRoleProvider), isNull);

    container.read(authStateProvider.notifier).set(
          const SignedIn(
            userId: 'u1',
            email: 'e@e.com',
            role: UserRole.recruiter,
          ),
        );
    expect(container.read(currentRoleProvider), UserRole.recruiter);
  });
}
